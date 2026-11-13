"""Segredos entregues à automação e contas de serviço (13/11/2026), no PostgreSQL e pela API real.

Segredos: o valor só sai pelo token do job, durante a execução, se o segredo está ativo e ligado
àquela automação; o valor nunca aparece em log, auditoria ou resposta de gestão.

Contas de serviço: credencial psa_ no cabeçalho, papel e times como uma pessoa, sem login por
senha, recusas na auditoria, credencial trocada invalida a anterior.
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import text

from tests.db.semente import Roteiro
from tests.db.test_comunicacao import _rodando
from tests.db.test_modo_direto_inscricao import admin  # noqa: F401 - fixture

VALOR = "S3nh@-do-Banco-Folha-2026"


def _auditoria(sessao, acao: str, recurso: str | None = None) -> list[dict]:
    sessao.expire_all()
    consulta = "SELECT actor_type, actor_id, resource_id, metadata FROM audit_events WHERE action = :a"
    dados = {"a": acao}
    if recurso:
        consulta += " AND resource_id = :r"
        dados["r"] = recurso
    return [dict(zip(("tipo", "quem", "recurso", "meta"), linha)) for linha in sessao.execute(text(consulta + " ORDER BY occurred_at"), dados)]


def _pedir(cliente, job_id: str, cab_job: dict, *chaves: str):
    return cliente.post(f"/api/v1/direto/jobs/{job_id}/segredos", json={"chaves": list(chaves)}, headers=cab_job)


def test_segredo_so_sai_para_a_automacao_ligada_durante_a_execucao(cliente, sessao, admin) -> None:
    chave = f"dominio.senha_{uuid.uuid4().hex[:6]}"
    assert cliente.post("/api/v1/secrets", json={"key": "com espaço!", "name": "x", "value": "y"}).status_code == 422
    criado = cliente.post("/api/v1/secrets", json={"key": chave.upper(), "name": "Senha do banco da Domínio", "value": VALOR})
    assert criado.status_code == 201, criado.text
    segredo = criado.json()["secret"]
    assert segredo["key"] == chave and "value" not in json.dumps(criado.json())  # chave normalizada, valor não volta
    sid = segredo["id"]

    instancia, _, execution_id, job_id, tentativa, cab_job = _rodando(cliente, sessao, admin, "8101")

    # Sem ligar à automação: não sai (e não diz se a chave existe).
    r = _pedir(cliente, job_id, cab_job, chave, "nao.existe")
    assert r.status_code == 200 and r.json()["segredos"] == {}
    assert set(r.json()["negados"]) == {chave, "nao.existe"}
    assert r.json()["negados"][chave] == r.json()["negados"]["nao.existe"]
    assert _pedir(cliente, job_id, {"Authorization": "Bearer jbt_errado"}, chave).status_code == 401
    assert _pedir(cliente, job_id, cab_job).status_code == 400  # sem chaves

    # Liga na aba Técnico da automação.
    assert cliente.post(f"/api/v1/segredos/da-automacao/{admin.automation_id}/{sid}").status_code == 204
    assert cliente.post(f"/api/v1/segredos/da-automacao/{admin.automation_id}/{sid}").status_code == 204  # de novo: nada muda
    da_automacao = cliente.get(f"/api/v1/segredos/da-automacao/{admin.automation_id}").json()["segredos"]
    assert [(s["chave"], s["ultimo_uso"]) for s in da_automacao] == [(chave, None)]
    assert cliente.post(f"/api/v1/segredos/da-automacao/999999/{sid}").status_code == 404

    r = _pedir(cliente, job_id, cab_job, chave, "nao.existe")
    assert r.json()["segredos"] == {chave: {"campos": {"valor": VALOR}, "ocultos": ["valor"]}}  # segredo de um campo
    assert list(r.json()["negados"]) == ["nao.existe"]
    assert r.headers["cache-control"] == "no-store"

    # A automação escreveu a senha no log: o Portal grava ***.
    roteiro = Roteiro(datetime.now(UTC)).emitir("execucao.iniciada").emitir("item.iniciado", item="8101")
    roteiro.emitir("log", nivel="info", texto=f"conectando com senha={VALOR} e usuario folha")
    assert cliente.post(f"/api/v1/direto/jobs/{job_id}/eventos", json={"eventos": roteiro.eventos[2:]}, headers=cab_job).status_code == 200
    textos = [l["texto"] for l in cliente.get(f"/api/v1/execucoes/{execution_id}/logs").json()["logs"]]
    assert any("usuario folha" in t for t in textos) and not any(VALOR in t for t in textos)

    # Trocar o valor: a próxima entrega já é a nova.
    assert cliente.post(f"/api/v1/secrets/{sid}/rotate", json={"value": "Nova-Senha-2027"}).status_code == 200
    assert _pedir(cliente, job_id, cab_job, chave).json()["segredos"][chave]["campos"] == {"valor": "Nova-Senha-2027"}
    versoes = cliente.get(f"/api/v1/segredos/{sid}/versoes").json()["versoes"]
    assert [(v["versao"], v["atual"]) for v in versoes] == [(2, True), (1, False)]

    # Desativado: não sai, com o motivo.
    assert cliente.put(f"/api/v1/segredos/{sid}", json={"situacao": "disabled"}).status_code == 204
    assert "desativado" in _pedir(cliente, job_id, cab_job, chave).json()["negados"][chave]
    assert cliente.put(f"/api/v1/segredos/{sid}", json={"situacao": "active"}).status_code == 204

    # A lista mostra quem usa e o último uso.
    lista = {s["id"]: s for s in cliente.get("/api/v1/segredos").json()["segredos"]}
    assert [a["id"] for a in lista[sid]["automacoes"]] == [admin.automation_id]
    assert lista[sid]["ultimo_uso"] and lista[sid]["versao"] == 2 and "valor" not in lista[sid]

    # Concessão para pessoa não tem efeito, então é recusada.
    assert cliente.post(f"/api/v1/secrets/{sid}/grants", json={"grantee_type": "user", "grantee_id": "1", "permission": "use"}).status_code == 422

    # Desligado: não sai mais.
    assert cliente.delete(f"/api/v1/segredos/da-automacao/{admin.automation_id}/{sid}").status_code == 204
    assert _pedir(cliente, job_id, cab_job, chave).json()["segredos"] == {}

    # Execução encerrada: nenhuma entrega, mesmo ligado de novo.
    assert cliente.put(f"/api/v1/segredos/{sid}/automacoes", json={"automacoes": [admin.automation_id]}).status_code == 204
    sessao.execute(text("UPDATE execution_attempts SET status = 'succeeded' WHERE id = :a"), {"a": tentativa})
    sessao.commit()
    assert _pedir(cliente, job_id, cab_job, chave).status_code == 409

    entregas = _auditoria(sessao, "segredo.entregue", sid)
    assert len(entregas) == 2 and entregas[0]["tipo"] == "direct_instance" and entregas[0]["quem"] == instancia.id
    assert entregas[0]["meta"]["execucao"] == execution_id and entregas[0]["meta"]["automacao"] == str(admin.automation_id)
    assert {e["meta"]["versao"] for e in entregas} == {1, 2}
    assert len(_auditoria(sessao, "segredo.negado", sid)) >= 3
    assert [len(_auditoria(sessao, a, sid)) for a in ("segredo.ligado", "segredo.desligado")] == [2, 1]
    tudo = sessao.execute(text("SELECT string_agg(coalesce(metadata::text,'') || coalesce(after::text,'') || "
                               "coalesce(before::text,''), ' ') FROM audit_events")).scalar()
    assert VALOR not in tudo and "Nova-Senha-2027" not in tudo
    print("\nsegredos: só com o token do job e ligado; log com ***; troca de valor vale na hora; desativado, desligado e "
          "execução encerrada recusam; tudo na auditoria sem o valor")


def test_segredo_com_campos_visiveis_e_ocultos(cliente, sessao, admin) -> None:
    chave = f"dominio.{uuid.uuid4().hex[:6]}"
    senha = "Senha-Da-Dominio-2026"
    campos = [{"nome": "usuario", "oculto": False, "valor": "folha"},
              {"nome": "senha", "oculto": True, "valor": senha},
              {"nome": "banco", "oculto": False, "valor": "contabil"}]
    assert cliente.post("/api/v1/segredos", json={"chave": chave, "nome": "D", "campos": []}).status_code == 422
    assert cliente.post("/api/v1/segredos", json={"chave": chave, "nome": "D", "campos": [
        {"nome": "Senha Nova", "valor": "x"}]}).status_code == 422  # nome de campo inválido
    assert cliente.post("/api/v1/segredos", json={"chave": chave, "nome": "D", "campos": [
        {"nome": "a", "valor": "x"}, {"nome": "a", "valor": "y"}]}).status_code == 422  # repetido
    criado = cliente.post("/api/v1/segredos", json={"chave": chave, "nome": "Acesso à Domínio", "campos": campos})
    assert criado.status_code == 201, criado.text
    sid = criado.json()["id"]
    assert cliente.post("/api/v1/segredos", json={"chave": chave, "nome": "outro", "campos": campos}).status_code == 422

    def na_lista() -> dict:
        return next(s for s in cliente.get("/api/v1/segredos").json()["segredos"] if s["id"] == sid)

    # Visíveis aparecem com o valor; oculto, nunca.
    assert na_lista()["campos"] == [{"nome": "usuario", "oculto": False, "valor": "folha"},
                                    {"nome": "senha", "oculto": True, "valor": None},
                                    {"nome": "banco", "oculto": False, "valor": "contabil"}]
    assert senha not in json.dumps(cliente.get("/api/v1/segredos").json())

    _, _, execution_id, job_id, _, cab_job = _rodando(cliente, sessao, admin, "8201")
    assert cliente.post(f"/api/v1/segredos/da-automacao/{admin.automation_id}/{sid}").status_code == 204
    assert cliente.get(f"/api/v1/segredos/da-automacao/{admin.automation_id}").json()["segredos"][0]["campos"] == ["usuario", "senha", "banco"]
    entregue = _pedir(cliente, job_id, cab_job, chave).json()["segredos"][chave]
    assert entregue == {"campos": {"usuario": "folha", "senha": senha, "banco": "contabil"}, "ocultos": ["senha"]}

    # No log, só o oculto vira ***.
    roteiro = Roteiro(datetime.now(UTC)).emitir("execucao.iniciada").emitir("item.iniciado", item="8201")
    roteiro.emitir("log", nivel="info", texto=f"login folha / {senha} no banco contabil")
    assert cliente.post(f"/api/v1/direto/jobs/{job_id}/eventos", json={"eventos": roteiro.eventos[2:]}, headers=cab_job).status_code == 200
    textos = [l["texto"] for l in cliente.get(f"/api/v1/execucoes/{execution_id}/logs").json()["logs"]]
    assert "login folha / *** no banco contabil" in textos

    # Mudar só o banco: senha em branco mantém a atual; versão nova.
    novos = [{**campos[0]}, {"nome": "senha", "oculto": True, "valor": ""}, {"nome": "banco", "oculto": False, "valor": "folha2026"}]
    assert cliente.put(f"/api/v1/segredos/{sid}/campos", json={"campos": novos}).status_code == 204
    entregue = _pedir(cliente, job_id, cab_job, chave).json()["segredos"][chave]["campos"]
    assert entregue == {"usuario": "folha", "senha": senha, "banco": "folha2026"}
    assert na_lista()["versao"] == 2

    # Só ocultar o usuário: sem versão nova; tirar um campo: versão nova sem ele.
    novos[0] = {"nome": "usuario", "oculto": True, "valor": ""}
    assert cliente.put(f"/api/v1/segredos/{sid}/campos", json={"campos": novos}).status_code == 204
    assert na_lista()["versao"] == 2 and na_lista()["campos"][0] == {"nome": "usuario", "oculto": True, "valor": None}
    assert cliente.put(f"/api/v1/segredos/{sid}/campos", json={"campos": novos[:2]}).status_code == 204
    assert _pedir(cliente, job_id, cab_job, chave).json()["segredos"][chave]["campos"] == {"usuario": "folha", "senha": senha}
    assert na_lista()["versao"] == 3
    novo_sem_valor = [*novos[:2], {"nome": "porta", "oculto": False, "valor": ""}]
    assert cliente.put(f"/api/v1/segredos/{sid}/campos", json={"campos": novo_sem_valor}).status_code == 422
    # A rota antiga de um valor só não serve para segredo de vários campos.
    assert cliente.post(f"/api/v1/secrets/{sid}/rotate", json={"value": "x"}).status_code == 422

    alteracoes = _auditoria(sessao, "segredo.campos_alterados", sid)
    assert len(alteracoes) == 3
    tudo = sessao.execute(text("SELECT string_agg(coalesce(metadata::text,'') || coalesce(after::text,'') || "
                               "coalesce(before::text,''), ' ') FROM audit_events")).scalar()
    assert senha not in tudo
    print("\nsegredo com campos: visíveis aparecem, oculto nunca; entrega o objeto; só o oculto vira *** no log; "
          "valor em branco mantém; ocultar não cria versão; tirar campo cria")


# -- contas de serviço -------------------------------------------------------------------------
@contextmanager
def _sem_usuario_injetado(cliente):
    from modules.access.api.dependencies import get_current_user

    anterior = cliente.app.dependency_overrides.pop(get_current_user)
    try:
        yield
    finally:
        cliente.app.dependency_overrides[get_current_user] = anterior


def test_conta_de_servico_entra_pela_credencial_com_papel_e_times(cliente, sessao) -> None:
    sufixo = uuid.uuid4().hex[:6]
    papel = cliente.post("/api/v1/papeis", json={"nome": f"Integração ERP {sufixo}",
                                                 "funcionalidades": {"historico": "ver", "maquinas": "gerenciar"}}).json()
    org = sessao.execute(text("INSERT INTO access_organizations (key, name) VALUES (:k, 'Org contas') RETURNING id"),
                         {"k": f"org-{sufixo}"}).scalar_one()
    sessao.commit()
    time = cliente.post("/api/v1/teams", json={"organization_id": org, "key": f"erp-{sufixo}", "name": f"ERP {sufixo}"}).json()
    admin_id = sessao.execute(text("SELECT id FROM roles WHERE slug = 'admin'")).scalar_one()

    assert cliente.post("/api/v1/contas-de-servico", json={"nome": "X", "papel_id": admin_id}).status_code == 422
    assert cliente.post("/api/v1/contas-de-servico", json={"nome": "", "papel_id": papel["id"]}).status_code == 422
    assert cliente.post("/api/v1/contas-de-servico", json={"nome": "Y", "papel_id": papel["id"], "times": [999999]}).status_code == 404
    criada = cliente.post("/api/v1/contas-de-servico", json={"nome": f"ERP Protheus {sufixo}", "descricao": "Lê o histórico",
                                                            "papel_id": papel["id"], "times": [time["id"]]})
    assert criada.status_code == 201, criada.text
    assert criada.headers["cache-control"] == "no-store"
    credencial, conta = criada.json()["credencial"], criada.json()["conta"]
    assert credencial.startswith("psa_") and len(credencial) > 40 and conta["credencial_final"] == credencial[-4:]
    assert conta["papel"]["id"] == papel["id"] and [t["id"] for t in conta["times"]] == [time["id"]]
    assert cliente.post("/api/v1/contas-de-servico", json={"nome": f"erp protheus {sufixo}", "papel_id": papel["id"]}).status_code == 422
    tecnico = conta["usuario_id"]
    email_tecnico = sessao.execute(text("SELECT email FROM users WHERE id = :u"), {"u": tecnico}).scalar_one()

    # Não aparece em Usuários e não se muda por lá.
    assert tecnico not in [u["id"] for u in cliente.get("/api/v1/users").json()]
    assert cliente.put(f"/api/v1/users/{tecnico}", json={"name": "x", "email": "x@teste.invalid", "role_id": papel["id"],
                                                         "password": "Senha-Forte-123"}).status_code == 409
    assert cliente.delete(f"/api/v1/users/{tecnico}").status_code == 409
    assert cliente.get("/api/v1/service-accounts").status_code == 410

    cab = {"Authorization": f"Bearer {credencial}"}
    with _sem_usuario_injetado(cliente):
        eu = cliente.get("/api/v1/auth/me", headers=cab)
        assert eu.status_code == 200 and eu.json()["id"] == tecnico and "historico.ver" in eu.json()["rbac_permissions"]
        assert cliente.get("/api/v1/historico", headers=cab).status_code == 200
        assert cliente.get("/api/v1/fila", headers=cab).status_code == 403  # o papel não dá a Fila
        assert cliente.get("/api/v1/contas-de-servico", headers=cab).status_code == 403
        nova_maquina = cliente.post("/api/v1/maquinas", json={"nome": f"ERP-MAQ-{sufixo}"}, headers={**cab, "x-request-id": f"req_{sufixo}"})
        assert nova_maquina.status_code == 201, nova_maquina.text
        assert cliente.get("/api/v1/historico", headers={"Authorization": "Bearer psa_inventada"}).status_code == 401
        assert cliente.get("/api/v1/historico", params={"token": credencial}).status_code == 401  # na URL não vale
        # Pela tela de login, nunca.
        assert cliente.post("/api/v1/auth/login", json={"email": email_tecnico, "password": "qualquer"}).status_code == 401

    sessao.expire_all()
    assert sessao.execute(text("SELECT last_used_at FROM service_accounts WHERE id = :c"), {"c": conta["id"]}).scalar() is not None
    requisicao = sessao.execute(text("SELECT actor_id, metadata FROM audit_events WHERE correlation_id = :c AND action = 'api.post'"),
                                {"c": f"req_{sufixo}"}).first()
    assert requisicao is not None and requisicao[0] == str(tecnico) and requisicao[1]["conta_de_servico"] == conta["id"]

    # Nova credencial: a anterior para na hora.
    nova = cliente.post(f"/api/v1/contas-de-servico/{conta['id']}/credencial").json()["credencial"]
    with _sem_usuario_injetado(cliente):
        assert cliente.get("/api/v1/historico", headers=cab).status_code == 401
        assert cliente.get("/api/v1/historico", headers={"Authorization": f"Bearer {nova}"}).status_code == 200
    cab = {"Authorization": f"Bearer {nova}"}

    # Desativada e vencida: recusa.
    assert cliente.put(f"/api/v1/contas-de-servico/{conta['id']}", json={"situacao": "disabled"}).status_code == 200
    with _sem_usuario_injetado(cliente):
        assert cliente.get("/api/v1/historico", headers=cab).status_code == 401
    assert cliente.put(f"/api/v1/contas-de-servico/{conta['id']}", json={"situacao": "active", "times": []}).json()["conta"]["times"] == []
    assert cliente.put(f"/api/v1/contas-de-servico/{conta['id']}", json={"expira_em": "2020-01-01T00:00:00Z"}).status_code == 422
    sessao.execute(text("UPDATE service_accounts SET expires_at = now() - interval '1 minute' WHERE id = :c"), {"c": conta["id"]})
    sessao.commit()
    with _sem_usuario_injetado(cliente):
        assert cliente.get("/api/v1/historico", headers=cab).status_code == 401

    motivos = [a["meta"]["motivo"] for a in _auditoria(sessao, "conta_de_servico.recusada", conta["id"])]
    assert motivos == ["conta_desativada", "conta_vencida"]
    assert [a["meta"]["motivo"] for a in _auditoria(sessao, "conta_de_servico.recusada", "desconhecida")][-1] == "credencial_desconhecida"
    tudo = sessao.execute(text("SELECT string_agg(coalesce(metadata::text,'') || coalesce(after::text,''), ' ') FROM audit_events")).scalar()
    assert credencial not in tudo and nova not in tudo
    acoes = [a["recurso"] for a in _auditoria(sessao, "conta_de_servico.criada")]
    assert conta["id"] in acoes

    assert cliente.delete(f"/api/v1/contas-de-servico/{conta['id']}").status_code == 204
    sessao.expire_all()
    assert sessao.execute(text("SELECT count(*) FROM users WHERE id = :u"), {"u": tecnico}).scalar() == 0
    print("\ncontas de serviço: credencial no cabeçalho com o papel e os times; fora de Usuários e sem login; trocar, "
          "desativar e vencer recusam; requisição auditada no nome da conta; apagar leva o usuário técnico")
