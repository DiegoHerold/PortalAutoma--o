"""Webhooks novos (13/11/2026) no PostgreSQL e pela API real: só acionam a automação, token no
cabeçalho, IPs, limite por minuto, idempotência, campos e itens conferidos pelo formulário, e o
histórico de chamadas. As rotas antigas respondem 410."""

from __future__ import annotations

from sqlalchemy import text

from tests.db.semente import automacao, publicar
from tests.db.test_fase4_acompanhar import como
from tests.db.test_fase6_notificacoes_retencao import _usuario
from tests.db.test_fase7_campos import COLUNAS, ENTRADA, _admin


def _preparar(cliente, sessao) -> int:
    _admin(cliente, sessao)
    automation_id, version_id = automacao(sessao)
    publicar(sessao, version_id)
    base = f"/api/v1/automations/{automation_id}"
    assert cliente.put(f"{base}/formulario", json={"entrada": ENTRADA, "colunas": COLUNAS, "versao": 0}).status_code == 200
    assert cliente.post(f"{base}/itens", json={"chave": "5081", "rotulo": "Matriz", "atributos": {"caminho_saida": "F:\\saida"}}).status_code == 201
    return automation_id


def _chamar(cliente, webhook_id: str, token: str | None, corpo=None, **kw):
    cabecalhos = {**({"Authorization": f"Bearer {token}"} if token else {}), **kw.pop("headers", {})}
    return cliente.post(f"/api/v1/webhooks/{webhook_id}", json=corpo, headers=cabecalhos, **kw)


def test_webhook_aciona_so_a_automacao_com_seguranca(cliente, sessao) -> None:
    automation_id = _preparar(cliente, sessao)
    assert cliente.post("/api/v1/webhooks", json={"automation_id": automation_id, "nome": ""}).status_code == 422
    assert cliente.post("/api/v1/webhooks", json={"automation_id": automation_id, "nome": "ERP",
                                                  "ips_permitidos": ["10.0.0.300"]}).status_code == 422
    criado = cliente.post("/api/v1/webhooks", json={"automation_id": automation_id, "nome": "ERP Protheus",
                                                    "descricao": "Fecha a folha", "limite_por_minuto": 600})
    assert criado.status_code == 201, criado.text
    assert criado.headers["cache-control"] == "no-store"
    token, webhook = criado.json()["token"], criado.json()["webhook"]
    wid = webhook["id"]
    assert token.startswith("wht_") and webhook["token_final"] == token[-4:] and webhook["ativo"] is True
    assert webhook["url"].endswith(f"/api/v1/webhooks/{wid}") and "token" not in cliente.get(f"/api/v1/webhooks/{wid}").json()["webhook"]

    pedido = {"parametros": {"competencia": "102026"}, "itens": ["5081"]}
    # Credencial: sem token, errado e webhook inexistente dão a mesma resposta.
    assert _chamar(cliente, wid, None, pedido).status_code == 401
    errado = _chamar(cliente, wid, "wht_errado", pedido)
    inexistente = _chamar(cliente, "whk_0000000000000000", token, pedido)
    assert errado.status_code == inexistente.status_code == 401 and errado.json() == inexistente.json()
    assert _chamar(cliente, wid, None, pedido, headers={"X-Trigger-Secret": token}).status_code == 401  # cabeçalho antigo não vale
    assert _chamar(cliente, wid, token, pedido, params={"token": token}).status_code == 400  # na URL, nunca
    assert _chamar(cliente, wid, token, {**pedido, "token": token}).status_code == 400  # no corpo, nunca
    # Corpo.
    assert _chamar(cliente, wid, token, {**pedido, "prioridade": 100}).status_code == 422  # só parametros, itens, com_filiais
    assert cliente.post(f"/api/v1/webhooks/{wid}", content=b"competencia=10", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "text/plain"}).status_code == 415
    sem_competencia = _chamar(cliente, wid, token, {"itens": ["5081"]})
    assert sem_competencia.status_code == 422 and sem_competencia.json()["detalhe"] == {"competencia": "obrigatório"}
    assert _chamar(cliente, wid, token, {"parametros": {"competencia": "102026"}, "itens": ["9999"]}).status_code == 422

    aceito = _chamar(cliente, wid, token, pedido, headers={"Idempotency-Key": "folha-10-2026"})
    assert aceito.status_code == 202, aceito.text
    execucao = aceito.json()["execucao_id"]
    assert aceito.json()["itens"] == ["5081"] and aceito.json()["situacao"] == "na_fila"
    linha = sessao.execute(text("SELECT origin, requested_by FROM orchestration_executions WHERE id = :e"), {"e": execucao}).one()
    assert tuple(linha) == ("webhook", f"webhook:{wid}")
    parametros = sessao.execute(text("SELECT parameters FROM task_executions WHERE execution_id = :e"), {"e": execucao}).scalar_one()
    assert parametros == {"competencia": "10/2026", "modo": "completo"}
    # A mesma chave de idempotência: a mesma execução, nada novo.
    repetido = _chamar(cliente, wid, token, pedido, headers={"Idempotency-Key": "folha-10-2026"})
    assert repetido.status_code == 200 and repetido.json()["execucao_id"] == execucao
    assert sessao.execute(text("SELECT count(*) FROM orchestration_executions WHERE requested_by = :r"),
                          {"r": f"webhook:{wid}"}).scalar() == 1

    # Desligado, fora dos IPs, acima do limite: recusa.
    assert cliente.put(f"/api/v1/webhooks/{wid}", json={"ativo": False}).status_code == 200
    assert _chamar(cliente, wid, token, pedido).status_code == 403
    assert cliente.put(f"/api/v1/webhooks/{wid}", json={"ativo": True, "ips_permitidos": "10.9.9.9, 192.168.0.0/24"}).json()[
        "webhook"]["ips_permitidos"] == ["10.9.9.9/32", "192.168.0.0/24"]
    origem = _chamar(cliente, wid, token, pedido)
    assert origem.status_code == 403 and "origem" in origem.json()["erro"]
    assert cliente.put(f"/api/v1/webhooks/{wid}", json={"ips_permitidos": [], "limite_por_minuto": 1}).status_code == 200
    assert _chamar(cliente, wid, token, pedido).status_code == 429

    # Token novo: o anterior para na hora.
    novo = cliente.post(f"/api/v1/webhooks/{wid}/token").json()["token"]
    assert cliente.put(f"/api/v1/webhooks/{wid}", json={"limite_por_minuto": 600}).status_code == 200
    assert _chamar(cliente, wid, token, pedido).status_code == 401
    assert _chamar(cliente, wid, novo, {"parametros": {"competencia": "112026"}, "itens": ["5081"]}).status_code == 202

    chamadas = cliente.get(f"/api/v1/webhooks/{wid}/chamadas").json()["chamadas"]
    situacoes = [c["situacao"] for c in chamadas]
    assert situacoes.count("aceita") == 2 and situacoes.count("repetida") == 1 and "recusada" in situacoes
    motivos = {c["motivo"] for c in chamadas if c["situacao"] == "recusada"}
    assert {"webhook desligado no Portal", "origem não permitida para este webhook", "limite de 1 chamadas por minuto",
            "credencial inválida para este webhook"} <= motivos
    lista = cliente.get("/api/v1/webhooks", params={"automacao": automation_id}).json()["webhooks"]
    assert [w["id"] for w in lista] == [wid] and lista[0]["chamadas_24h"]["aceitas"] == 3
    tudo = sessao.execute(text("SELECT coalesce(string_agg(coalesce(motivo,'') || coalesce(chave_idempotencia,''), ' '), '') "
                               "FROM webhook_chamadas")).scalar()
    tudo += sessao.execute(text("SELECT string_agg(coalesce(after::text,'') || coalesce(before::text,''), ' ') FROM audit_events")).scalar()
    assert token not in tudo and novo not in tudo
    acoes = [a for (a,) in sessao.execute(text("SELECT action FROM audit_events WHERE resource_type = 'webhook' AND resource_id = :w "
                                               "ORDER BY occurred_at"), {"w": wid})]
    assert acoes[0] == "webhook.criado" and "webhook.token_gerado" in acoes

    # Quem não pode executar a automação não cria nem muda.
    pessoa, _ = _usuario(sessao, "sem_permissao")
    with como(cliente, pessoa, "sem_permissao"):
        assert cliente.post("/api/v1/webhooks", json={"automation_id": automation_id, "nome": "x"}).status_code == 403
        assert cliente.get("/api/v1/webhooks").status_code == 403

    # Rotas antigas: 410. O webhook do GitHub continua sendo outra coisa.
    assert cliente.post("/api/v1/webhooks/trigger/qualquer", json={}).status_code == 410
    assert cliente.get("/api/v1/triggers").status_code == 410
    assert cliente.post("/api/v1/triggers/invoke/qualquer", json={}).status_code == 410
    assert cliente.post("/api/v1/webhooks/github", json={}).status_code != 410

    assert cliente.delete(f"/api/v1/webhooks/{wid}").status_code == 204
    assert _chamar(cliente, wid, novo, pedido).status_code == 401
    print("\nwebhook: token só no cabeçalho; inexistente = token errado; corpo e campos conferidos; idempotência; "
          "desligado, IP e limite recusam; token novo corta o antigo; histórico sem o token; antigas 410")


def test_ip_permitido_e_redes() -> None:
    from modules.orchestration.webhooks.aplicacao import WebhookInvalido, ip_permitido, validar_redes

    redes = validar_redes(["10.0.8.0/24", "10.0.8.15", " ", "2001:db8::/32", "10.0.8.0/24"])
    assert redes == ["10.0.8.0/24", "10.0.8.15/32", "2001:db8::/32"]
    assert ip_permitido("10.0.8.200", redes) and ip_permitido("2001:db8::1", redes)
    assert not ip_permitido("10.0.9.1", redes) and not ip_permitido("testclient", redes) and not ip_permitido(None, redes)
    assert ip_permitido("qualquer", [])  # sem lista: qualquer origem
    try:
        validar_redes(["meu-servidor"])
    except WebhookInvalido:
        pass
    else:
        raise AssertionError("nome de host não é IP")
