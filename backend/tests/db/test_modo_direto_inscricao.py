"""Modo direto, lado da instância: inscrição, sessão por desafio assinado e entrega do job.

Antecipado da Fase 6 para ligar a Integração Contábil. Chaves ECDSA P-256 de verdade.
"""

from __future__ import annotations

import base64
import threading
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import text

from modules.dispatch.api.fila import despachar_agora
from modules.fleet.domain.instancia_direta import mensagem_assinada
from tests.db.semente import Roteiro, automacao, maquina, publicar


class Instancia:
    """O que o SDK faz na máquina: guarda a chave privada e assina o desafio."""

    def __init__(self, cliente, curva=ec.SECP256R1()) -> None:
        self.cliente = cliente
        self.chave = ec.generate_private_key(curva)
        self.id: str | None = None

    @property
    def publica(self) -> str:
        return self.chave.public_key().public_bytes(serialization.Encoding.PEM,
                                                    serialization.PublicFormat.SubjectPublicKeyInfo).decode()

    def inscrever(self, codigo: str):
        r = self.cliente.post("/api/v1/direto/inscricao", json={"codigo": codigo, "chave_publica": self.publica,
                                                                "nome_maquina": "MAQ194", "versao_sdk": "1.0.0"})
        if r.status_code == 201:
            self.id = r.json()["instancia_id"]
        return r

    def sessao(self, assinar_com=None):
        d = self.cliente.post("/api/v1/direto/sessao/desafio", json={"instancia_id": self.id})
        if d.status_code != 200:
            return d
        desafio = d.json()
        chave = assinar_com or self.chave
        assinatura = chave.sign(mensagem_assinada(self.id, desafio["desafio_id"], desafio["nonce"]), ec.ECDSA(hashes.SHA256()))
        return self.cliente.post("/api/v1/direto/sessao", json={"instancia_id": self.id, "desafio_id": desafio["desafio_id"],
                                                                "assinatura": base64.b64encode(assinatura).decode()})


def _auditoria(sessao, acao: str) -> list[dict]:
    sessao.expire_all()
    return [dict(m or {}) for (m,) in sessao.execute(text("SELECT metadata FROM audit_events WHERE action = :a ORDER BY occurred_at"),
                                                    {"a": acao})]


@pytest.fixture
def admin(cliente, sessao):
    from modules.access.api.dependencies import get_current_user

    cliente.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, role=SimpleNamespace(slug="admin"), category_permissions=[], permissions=[])
    automation_id, version_id = automacao(sessao)
    publicar(sessao, version_id)
    return SimpleNamespace(automation_id=automation_id, version_id=version_id)


def _codigo(cliente, automation_id: int) -> str:
    r = cliente.post(f"/api/v1/automations/{automation_id}/instancias-diretas/codigos")
    assert r.status_code == 201, r.text
    return r.json()["codigo"]


def test_ciclo_completo_inscricao_aprovacao_job_e_eventos(cliente, sessao, admin) -> None:
    instancia = Instancia(cliente)
    codigo = _codigo(cliente, admin.automation_id)
    assert instancia.inscrever(codigo.lower().replace("-", "")).status_code == 201  # digitado sem hífen e minúsculo

    pendente = instancia.sessao()
    assert pendente.status_code == 200 and pendente.json()["status"] == "pendente"
    token_sessao = pendente.json()["token"]
    cab = {"Authorization": f"Bearer {token_sessao}"}
    assert cliente.get("/api/v1/direto/jobs/proximo", headers=cab).json() == {"job": None, "status": "pendente"}

    # O administrador cadastra a máquina e aprova a instância nela.
    mch = cliente.post("/api/v1/maquinas", json={"nome": f"MAQ194-{uuid.uuid4().hex[:4]}"}).json()["id"]
    assert cliente.post(f"/api/v1/instancias-diretas/{instancia.id}/aprovar", json={}).status_code == 409  # sem máquina
    aprovada = cliente.post(f"/api/v1/instancias-diretas/{instancia.id}/aprovar", json={"maquina_id": mch})
    assert aprovada.json() == {"id": instancia.id, "status": "aprovada", "maquina_id": mch}

    # Pedido na fila -> despacho reserva para a instância (ela tem sinal pela sessão).
    sessao.execute(text("UPDATE machines SET status = 'inativa' WHERE status = 'ativa' AND id <> :m"), {"m": mch})
    sessao.commit()
    pedido = cliente.post("/api/v1/fila/execucoes", json={"automation_version_id": admin.version_id,
                                                         "itens": [{"chave": "5066", "rotulo": "Empresa 5066"}],
                                                         "parametros": {"competencia": "10/2026"}})
    job_id = pedido.json()["jobs"][0]["job_id"]
    assert [e["job_id"] for e in despachar_agora(sessao)["entregues"]] == [job_id]

    primeiro = cliente.get("/api/v1/direto/jobs/proximo", headers=cab).json()["job"]
    assert primeiro["job_id"] == job_id and primeiro["parametros"] == {"competencia": "10/2026"}
    assert [i["chave"] for i in primeiro["itens"]] == ["5066"]
    # A instância reiniciou antes de começar: pede de novo, recebe outro token e o anterior morre.
    segundo = cliente.get("/api/v1/direto/jobs/proximo", headers=cab).json()["job"]
    assert segundo["job_id"] == job_id and segundo["token"] != primeiro["token"]

    eventos = Roteiro(datetime.now(UTC)).emitir("execucao.iniciada").eventos
    url = f"/api/v1/direto/jobs/{job_id}/eventos"
    assert cliente.post(url, json={"eventos": eventos}, headers={"Authorization": f"Bearer {primeiro['token']}"}).status_code == 401
    assert cliente.post(url, json={"eventos": eventos}, headers={"Authorization": f"Bearer {segundo['token']}"}).status_code == 200
    # Começou: ninguém recebe o mesmo job de novo.
    assert cliente.get("/api/v1/direto/jobs/proximo", headers=cab).json()["job"] is None
    acoes = [a for (a,) in sessao.execute(text(
        "SELECT action FROM audit_events WHERE resource_id = :i ORDER BY occurred_at"), {"i": instancia.id})]
    assert acoes[:3] == ["direto.inscricao", "direto.sessao.aberta", "direto.instancia.aprovar"]
    print(f"\nmodo direto: código -> inscrição pendente -> sessão -> aprovada em {mch} -> job {job_id} entregue; "
          f"token trocado na 2ª entrega (o 1º dá 401); depois do 1º evento o job não sai de novo")


def test_recusas_sao_401_e_ficam_na_auditoria(cliente, sessao, admin) -> None:
    codigo = _codigo(cliente, admin.automation_id)
    a, b = Instancia(cliente), Instancia(cliente)
    assert a.inscrever(codigo).status_code == 201
    assert b.inscrever(codigo).status_code == 401                            # código já usado
    assert b.inscrever("AAAA-BBBB-CCCC-DDDD").status_code == 401             # código que não existe
    assert Instancia(cliente, ec.SECP384R1()).inscrever(_codigo(cliente, admin.automation_id)).status_code == 422  # outra curva
    b.id = a.id
    assert a.sessao(assinar_com=b.chave).status_code == 401                  # assinatura de outra chave
    assert cliente.get("/api/v1/direto/status", headers={"Authorization": "Bearer dst_falso"}).status_code == 401
    motivos = [m.get("motivo") for m in _auditoria(sessao, "direto.sessao.recusada")]
    assert "assinatura_invalida" in motivos and "sessao_invalida" in motivos
    assert {m.get("motivo") for m in _auditoria(sessao, "direto.inscricao.recusada")} == {"codigo_invalido_vencido_ou_usado"}


def test_desafio_vale_uma_vez_e_vence(cliente, sessao, admin) -> None:
    i = Instancia(cliente)
    i.inscrever(_codigo(cliente, admin.automation_id))
    d = cliente.post("/api/v1/direto/sessao/desafio", json={"instancia_id": i.id}).json()
    assinatura = base64.b64encode(i.chave.sign(mensagem_assinada(i.id, d["desafio_id"], d["nonce"]),
                                               ec.ECDSA(hashes.SHA256()))).decode()
    corpo = {"instancia_id": i.id, "desafio_id": d["desafio_id"], "assinatura": assinatura}
    assert cliente.post("/api/v1/direto/sessao", json=corpo).status_code == 200
    assert cliente.post("/api/v1/direto/sessao", json=corpo).status_code == 401  # reaproveitar o desafio
    d2 = cliente.post("/api/v1/direto/sessao/desafio", json={"instancia_id": i.id}).json()
    sessao.execute(text("UPDATE direct_challenges SET expires_at = now() - interval '1 second' WHERE id = :d"),
                   {"d": d2["desafio_id"]})
    sessao.commit()
    assinatura2 = base64.b64encode(i.chave.sign(mensagem_assinada(i.id, d2["desafio_id"], d2["nonce"]),
                                                ec.ECDSA(hashes.SHA256()))).decode()
    assert cliente.post("/api/v1/direto/sessao", json={"instancia_id": i.id, "desafio_id": d2["desafio_id"],
                                                       "assinatura": assinatura2}).status_code == 401


def test_mesmo_codigo_em_duas_inscricoes_simultaneas_so_uma_passa(cliente, sessao, admin) -> None:
    codigo = _codigo(cliente, admin.automation_id)
    resultados: list[int] = []
    barreira = threading.Barrier(2)

    def tentar() -> None:
        inst = Instancia(cliente)
        barreira.wait()
        resultados.append(inst.inscrever(codigo).status_code)

    linhas = [threading.Thread(target=tentar) for _ in range(2)]
    for t in linhas:
        t.start()
    for t in linhas:
        t.join()
    assert sorted(resultados) == [201, 401]


def test_quarentena_nao_recebe_jobs_e_revogada_perde_tudo(cliente, sessao, admin) -> None:
    i = Instancia(cliente)
    i.inscrever(_codigo(cliente, admin.automation_id))
    mch = maquina(sessao, f"Q-{uuid.uuid4().hex[:4]}")
    cliente.post(f"/api/v1/instancias-diretas/{i.id}/aprovar", json={"maquina_id": mch})
    assert cliente.post(f"/api/v1/instancias-diretas/{i.id}/quarentena").json()["status"] == "quarentena"
    cab = {"Authorization": f"Bearer {i.sessao().json()['token']}"}
    assert cliente.get("/api/v1/direto/jobs/proximo", headers=cab).json() == {"job": None, "status": "quarentena"}
    assert cliente.post(f"/api/v1/instancias-diretas/{i.id}/revogar").json()["status"] == "revogada"
    assert cliente.get("/api/v1/direto/status", headers=cab).status_code == 401      # sessão aberta antes morre
    assert i.sessao().status_code == 401                                             # nem desafio
    assert cliente.post(f"/api/v1/instancias-diretas/{i.id}/aprovar", json={"maquina_id": mch}).status_code == 409


def test_so_admin_ou_gestor_gera_codigo_e_aprova(cliente, sessao, admin) -> None:
    from modules.access.api.dependencies import get_current_user

    cliente.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=2, role=SimpleNamespace(slug="viewer"), category_permissions=[], permissions=[])
    assert cliente.post(f"/api/v1/automations/{admin.automation_id}/instancias-diretas/codigos").status_code == 403
    assert cliente.post("/api/v1/maquinas", json={"nome": "X"}).status_code == 403
    assert cliente.post("/api/v1/instancias-diretas/dri_x/aprovar", json={"maquina_id": "m"}).status_code == 403
    assert datetime.now(UTC) - timedelta(seconds=1) < datetime.now(UTC)
