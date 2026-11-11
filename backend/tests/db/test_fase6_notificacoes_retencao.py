"""Fase 6 no PostgreSQL: notificações (quem recebe, nada repetido, aviso no portal, e-mail
desligado) e retenção por automação (imagens pelo Storage, só as linhas de log, auditoria)."""

from __future__ import annotations

import io
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from tests.db.semente import Roteiro, agente, automacao, execucao, instancia_direta, maquina, tentativa_direta
from tests.db.test_fase4_acompanhar import como, jpeg


@pytest.fixture(autouse=True)
def _storage_temporario(tmp_path, monkeypatch):
    from infrastructure.config import get_settings

    monkeypatch.setattr(get_settings(), "local_storage_path", str(tmp_path / "storage"))
    monkeypatch.setattr(get_settings(), "storage_backend", "local")


def _usuario(sessao, papel: str) -> tuple[int, str]:
    role = sessao.execute(text("SELECT id FROM roles WHERE slug = :s ORDER BY id LIMIT 1"), {"s": papel}).scalar()
    if role is None:
        role = sessao.execute(text("INSERT INTO roles (name, slug, status, is_system) VALUES (:n, :s, 'active', true) RETURNING id"),
                              {"n": papel.title(), "s": papel}).scalar_one()
    email = f"{uuid.uuid4().hex[:10]}@teste.invalid"
    uid = sessao.execute(text("INSERT INTO users (name, email, password_hash, role_id, status, is_active) "
                              "VALUES (:n, :e, 'x', :r, 'active', true) RETURNING id"),
                         {"n": f"Pessoa {papel}", "e": email, "r": role}).scalar_one()
    sessao.commit()
    return uid, email


def _conceder(sessao, automation_id: int, user_id: int, acoes: list[str]) -> None:
    sessao.execute(text("INSERT INTO automation_grants (id, automation_id, user_id, acoes) VALUES (:i, :a, :u, CAST(:c AS jsonb))"),
                   {"i": f"agr_{uuid.uuid4().hex}", "a": automation_id, "u": user_id, "c": json.dumps(acoes)})
    sessao.commit()


def _job_direto(sessao, automation_id: int, version_id: int):
    mch = maquina(sessao, f"FOLHA-{uuid.uuid4().hex[:4]}")
    instancia = instancia_direta(sessao, automation_id, mch)
    execution_id, job_id = execucao(sessao, version_id, datetime.now(UTC) - timedelta(minutes=5))
    attempt_id, token = tentativa_direta(sessao, job_id, instancia, mch)
    return SimpleNamespace(execution_id=execution_id, job_id=job_id, attempt_id=attempt_id, token=token, machine=mch)


def _eventos(cliente, job, roteiro: Roteiro) -> None:
    r = cliente.post(f"/api/v1/direto/jobs/{job.job_id}/eventos", json={"eventos": roteiro.eventos},
                     headers={"Authorization": f"Bearer {job.token}"})
    assert r.status_code == 200 and r.json()["recusados"] == [], r.text


def _avisos(sessao, chave: str) -> list[tuple[str, str]]:
    return sorted(sessao.execute(text(
        "SELECT d.email, d.email_status FROM notification_deliveries d JOIN notifications n ON n.id = d.notification_id"
        " WHERE n.chave = :c"), {"c": chave}).all())


# -- Notificações ----------------------------------------------------------------------------

def test_notificacoes_quem_recebe_sem_repetir_aviso_no_portal_e_email_desligado(cliente, sessao) -> None:
    from modules.telemetry.infrastructure.adapters.notificacoes import build_detectar, build_enviar

    automation_id, version_id = automacao(sessao)
    gestor, email_gestor = _usuario(sessao, "admin")
    operador, email_operador = _usuario(sessao, "operator")
    sem_acesso, _ = _usuario(sessao, "sem_permissao")  # papel sem nenhuma permissão (o "operator" padrão vê por categoria)
    _conceder(sessao, automation_id, operador, ["ver_execucoes"])

    with como(cliente, operador, "operator"):
        recusa = cliente.put("/api/v1/notificacoes/preferencias", json={"tipos": ["maquina_offline"], "fila_minutos": 30})
        assert recusa.status_code == 422 and "administradores e gestores" in recusa.text
        pref = cliente.put("/api/v1/notificacoes/preferencias", json={"tipos": ["termino", "erro"], "fila_minutos": 30}).json()
        assert pref["tipos"] == ["erro", "termino"] and pref["envio_por_email"] == "desligado"
        assert [d["tipo"] for d in pref["disponiveis"]] == ["erro", "atencao", "termino"]
    with como(cliente, sem_acesso, "sem_permissao"):
        assert cliente.put("/api/v1/notificacoes/preferencias", json={"tipos": ["termino"]}).status_code == 200
    with como(cliente, gestor, "admin"):
        pref = cliente.put("/api/v1/notificacoes/preferencias", json={"tipos": ["erro", "maquina_offline"], "fila_minutos": 45}).json()
        assert [d["tipo"] for d in pref["disponiveis"]] == ["erro", "atencao", "maquina_offline", "fila_parada", "termino"]
        assert pref["fila_minutos"] == 45

    # execução que falhou, item aguardando uma pessoa e máquina que parou de dar sinal
    falhou, _ = execucao(sessao, version_id, datetime.now(UTC) - timedelta(minutes=10))
    sessao.execute(text("UPDATE orchestration_executions SET status = 'failed', completed_at = now(),"
                        " failure_summary = 'O Total não bateu' WHERE id = :i"), {"i": falhou})
    sessao.commit()
    job = _job_direto(sessao, automation_id, version_id)
    _eventos(cliente, job, Roteiro(datetime.now(UTC) - timedelta(seconds=20))
             .emitir("atencao", item="5081", motivo="Rubrica 0450 sem conta contábil")
             .emitir("atencao", item="5081", motivo="de novo, mesmo item"))
    caida = maquina(sessao, "FISCAL-09")
    ag = agente(sessao, caida)
    sinal = datetime.now(UTC) - timedelta(minutes=3)
    sessao.execute(text("UPDATE agents SET connectivity_status = 'offline', last_seen_at = :q WHERE id = :i"),
                   {"q": sinal, "i": ag.agent_id})
    sessao.commit()

    primeira = build_detectar(sessao).execute()
    fim = f"fim:{falhou}"
    assert _avisos(sessao, fim) == sorted([(email_gestor, "pendente"), (email_operador, "pendente")])  # sem_acesso não
    assert _avisos(sessao, f"atencao:{job.execution_id}:5081") == []  # ninguém escolheu "atenção": registrada sem aviso
    offline = sessao.execute(text("SELECT chave FROM notifications WHERE chave LIKE :c"), {"c": f"offline:{caida}:%"}).scalars().all()
    assert len(offline) == 1 and _avisos(sessao, offline[0]) == [(email_gestor, "pendente")]

    segunda = build_detectar(sessao).execute()
    contagem = sessao.execute(text("SELECT count(*) FROM notifications WHERE chave IN (:a, :b, :c)"),
                              {"a": fim, "b": f"atencao:{job.execution_id}:5081", "c": offline[0]}).scalar_one()
    assert contagem == 3 and segunda == {"ocorrencias": 0, "avisos": 0}
    assert len(_avisos(sessao, fim)) == 2

    with como(cliente, operador, "operator"):
        caixa = cliente.get("/api/v1/notificacoes").json()
        meu = next(a for a in caixa["avisos"] if a["link"] == f"/execucoes/{falhou}")
        assert meu["titulo"].endswith(": terminou com erro") and "O Total não bateu" in meu["texto"]
        assert meu["lida"] is False and set(meu["tipos"]) == {"erro", "termino"} and caixa["nao_lidas"] >= 1
        assert cliente.post("/api/v1/notificacoes/lidas", json={}).json()["marcadas"] >= 1
        assert cliente.get("/api/v1/notificacoes").json()["nao_lidas"] == 0

    # e-mail desligado: nada sai, tudo segue pendente
    assert build_enviar(sessao).execute() == {"ligado": 0}
    assert _avisos(sessao, fim) == sorted([(email_gestor, "pendente"), (email_operador, "pendente")])

    # com um carteiro (aqui, um dublê de teste no lugar do Graph): um e-mail por endereço
    class Carteiro:
        def __init__(self) -> None:
            self.enviados: list[tuple[str, str]] = []

        def enviar(self, para, assunto, texto):
            self.enviados.append((para, assunto))

    carteiro = Carteiro()
    resultado = build_enviar(sessao, carteiro=carteiro).execute()
    assert _avisos(sessao, fim) == sorted([(email_gestor, "enviado"), (email_operador, "enviado")])
    print(f"\nnotificações: 1ª detecção {primeira}, 2ª {segunda}; fim -> gestor e operador (sem_acesso não);"
          f" offline -> só gestor; envio desligado mantém pendente; com carteiro {resultado}")


# -- Retenção ---------------------------------------------------------------------------------

def test_retencao_apaga_imagens_pelo_storage_e_so_os_logs(cliente, sessao, tmp_path) -> None:
    from modules.telemetry.infrastructure.adapters.notificacoes import build_aplicar_retencao

    admin, _ = _usuario(sessao, "admin")
    automation_id, version_id = automacao(sessao)
    job = _job_direto(sessao, automation_id, version_id)
    sessao.execute(text("UPDATE task_executions SET status = 'running' WHERE id = :j"), {"j": job.job_id})
    sessao.commit()
    with como(cliente, admin, "admin"):
        for imagem_id in ("img_velha", "img_nova"):
            r = cliente.put(f"/api/v1/direto/jobs/{job.job_id}/imagens/{imagem_id}", content=jpeg(),
                            headers={"Content-Type": "image/jpeg", "Authorization": f"Bearer {job.token}"})
            assert r.status_code == 201, r.text
        _eventos(cliente, job, Roteiro(datetime.now(UTC) - timedelta(seconds=30))
                 .emitir("etapa.iniciada", etapa="rubricas", item="5081")
                 .emitir("log", nivel="info", texto="Centro 1 de 50 conferido")
                 .emitir("log", nivel="aviso", texto="Centro 2 de 50 conferido"))
        quarenta_dias = datetime.now(UTC) - timedelta(days=40)
        sessao.execute(text("UPDATE step_images SET created_at = :q WHERE execution_id = :e AND imagem_id = 'img_velha'"),
                       {"q": quarenta_dias, "e": job.execution_id})
        sessao.execute(text("UPDATE execution_events SET received_at = :q WHERE execution_id = :e"),
                       {"q": quarenta_dias, "e": job.execution_id})
        sessao.commit()
        objetos = sessao.execute(text("SELECT o.id, o.bucket, o.object_key FROM step_images s JOIN stored_objects o"
                                      " ON o.id IN (s.cheia_id, s.media_id, s.miniatura_id)"
                                      " WHERE s.execution_id = :e AND s.imagem_id = 'img_velha'"), {"e": job.execution_id}).all()
        from infrastructure.storage import get_package_storage

        raiz = get_package_storage().root  # onde o armazenamento de fato gravou (nunca a pasta real)
        assert "PortalAutomacoes" not in str(raiz)
        assert len(objetos) == 3 and all((raiz / b / k).is_file() for _, b, k in objetos)

        # sem prazo: nada sai
        assert [f for f in build_aplicar_retencao(sessao).execute() if f["automation_id"] == automation_id] == []
        base = f"/api/v1/execucoes/{job.execution_id}/imagens"
        assert cliente.get(f"{base}/img_velha?tamanho=miniatura").status_code == 200

        url = f"/api/v1/governance/retencao-por-automacao/{automation_id}"
        assert cliente.put(url, json={"imagens_dias": 0}).status_code == 422
        assert cliente.put(url, json={"imagens_dias": 30, "logs_dias": 30}).json() == {
            "automation_id": automation_id, "imagens_dias": 30, "logs_dias": 30}
        lista = cliente.get("/api/v1/governance/retencao-por-automacao").json()
        assert {"automation_id": automation_id, "imagens_dias": 30, "logs_dias": 30} == {
            k: v for k, v in next(a for a in lista["automacoes"] if a["automation_id"] == automation_id).items() if k != "automacao"}
        assert lista["limites"] == {"minimo": 1, "maximo": 3650}
        with como(cliente, _usuario(sessao, "operator")[0], "operator"):
            assert cliente.put(url, json={"imagens_dias": 5}).status_code == 403

        feito = [f for f in build_aplicar_retencao(sessao).execute() if f["automation_id"] == automation_id]
        assert [(f["imagens"], f["linhas_de_log"]) for f in feito] == [(1, 2)]

        velha = sessao.execute(text("SELECT apagada_em, cheia_id, media_id, miniatura_id FROM step_images"
                                    " WHERE execution_id = :e AND imagem_id = 'img_velha'"), {"e": job.execution_id}).one()
        assert velha[0] is not None and velha[1:] == (None, None, None)
        assert not any((raiz / b / k).exists() for _, b, k in objetos)
        situacoes = sessao.execute(text("SELECT status FROM stored_objects WHERE id IN :i").bindparams(
            __import__("sqlalchemy").bindparam("i", expanding=True)), {"i": [o for o, _, _ in objetos]}).scalars().all()
        assert situacoes == ["deleted"] * 3
        assert cliente.get(f"{base}/img_velha?tamanho=media").status_code == 410
        assert cliente.get(f"{base}/img_nova?tamanho=media").status_code == 200
        tipos = sessao.execute(text("SELECT payload->>'type' FROM execution_events WHERE execution_id = :e"),
                               {"e": job.execution_id}).scalars().all()
        assert "log" not in tipos and "etapa.iniciada" in tipos  # só os logs saíram
        visao = cliente.get(f"/api/v1/execucoes/{job.execution_id}/acompanhar").json()
        assert cliente.get(f"/api/v1/execucoes/{job.execution_id}/logs").json()["logs"] == []
        acoes = sessao.execute(text("SELECT action, actor_type FROM audit_events WHERE resource_type = 'automation'"
                                    " AND resource_id = :a ORDER BY occurred_at"), {"a": str(automation_id)}).all()
        assert [tuple(a) for a in acoes] == [("retencao.definida", "user"), ("retencao.aplicada", "system")]
        # de novo: nada mais para apagar, nada a auditar
        assert [f for f in build_aplicar_retencao(sessao).execute() if f["automation_id"] == automation_id] == []
    print(f"\nretenção: sem prazo nada sai; com 30 dias -> 1 imagem (3 medidas apagadas no Storage, 410) e 2 linhas de log;"
          f" etapa fica; auditoria {[a[0] for a in acoes]}; visão ok={bool(visao)}")
