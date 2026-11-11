"""Fase 7 no PostgreSQL: campos da automação editados no Portal, valores conferidos nos itens
e no pedido de execução, e quem pode editar."""

from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import text

from tests.db.semente import automacao, publicar
from tests.db.test_fase4_acompanhar import como
from tests.db.test_fase6_notificacoes_retencao import _conceder, _usuario

ENTRADA = [
    {"chave": "competencia", "rotulo": "Competência", "tipo": "mes_ano", "obrigatorio": True},
    {"chave": "modo", "rotulo": "O que fazer", "tipo": "lista", "obrigatorio": True, "padrao": "completo",
     "opcoes": ["completo", "rubricas", "integracao"]},
]
COLUNAS = [
    {"chave": "separar_por_custo", "rotulo": "Separar por custo", "tipo": "sim_nao", "padrao": False, "afeta_trabalho": True},
    {"chave": "caminho_saida", "rotulo": "Pasta de destino", "tipo": "pasta", "obrigatorio": True},
    {"chave": "email", "rotulo": "E-mail", "tipo": "email"},
]


def _admin(cliente, sessao):
    from modules.access.api.dependencies import get_current_user

    uid, _ = _usuario(sessao, "admin")
    cliente.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=uid, email="adm@teste.invalid", role=SimpleNamespace(slug="admin"), category_permissions=[], permissions=[])
    return uid


def test_campos_editados_no_portal_valem_nos_itens_e_no_pedido(cliente, sessao) -> None:
    _admin(cliente, sessao)
    automation_id, version_id = automacao(sessao)
    publicar(sessao, version_id)
    base = f"/api/v1/automations/{automation_id}"

    # Antes de editar: o que o manifesto sugere.
    inicio = cliente.get(f"{base}/formulario").json()
    assert inicio["origem"] == "manifesto" and inicio["versao"] == 0 and inicio["entrada"] == []
    assert [c["chave"] for c in inicio["colunas"]] == ["codigo", "matriz_codigo", "separar_por_custo"]
    assert inicio["item"] == {"nome": "Empresa", "chave": "codigo", "grupo": "matriz_codigo"} and inicio["pode_editar"]

    # Campo inválido: diz qual e por quê, e não grava nada.
    ruim = cliente.put(f"{base}/formulario", json={"entrada": [{"chave": "Comp", "rotulo": ""}], "colunas": []})
    assert ruim.status_code == 422
    assert set(ruim.json()["error"]["details"]["campos"]) == {"entrada.campos[0].chave", "entrada.campos[0].rotulo"}

    salvo = cliente.put(f"{base}/formulario", json={"entrada": ENTRADA, "colunas": COLUNAS, "versao": 0}).json()
    assert salvo["origem"] == "portal" and salvo["versao"] == 1
    assert [c["chave"] for c in salvo["colunas"]] == ["separar_por_custo", "caminho_saida", "email"]
    velho = cliente.put(f"{base}/formulario", json={"entrada": ENTRADA, "colunas": COLUNAS, "versao": 0})
    assert velho.status_code == 409  # alguém gravou antes: não sobrescreve
    auditoria = sessao.execute(text("SELECT before->>'origem', after->>'versao' FROM audit_events"
                                    " WHERE action = 'automacao.campos.alterados' AND resource_id = :a"),
                               {"a": str(automation_id)}).all()
    assert [tuple(r) for r in auditoria] == [("manifesto", "1")]

    # Itens: obrigatório, tipo e padrão das colunas novas.
    sem_pasta = cliente.post(f"{base}/itens", json={"chave": "5081", "rotulo": "Matriz", "atributos": {}})
    assert sem_pasta.status_code == 422 and "atributos.caminho_saida" in sem_pasta.json()["error"]["details"]["campos"]
    criado = cliente.post(f"{base}/itens", json={"chave": "5081", "rotulo": "Matriz", "atributos": {
        "caminho_saida": r" F:\saida ", "separar_por_custo": "sim", "rubricas_ignoradas": [{"codigo": 450}]}}).json()
    assert criado["atributos"] == {"caminho_saida": r"F:\saida", "separar_por_custo": True,
                                   "rubricas_ignoradas": [{"codigo": 450}]}  # o que não é coluna fica guardado
    email_ruim = cliente.put(f"{base}/itens/5081", json={"rotulo": "Matriz", "atributos": {
        "caminho_saida": "F:\\x", "email": "folha"}})
    assert email_ruim.status_code == 422

    # Pedido: as informações conferidas pelos campos de entrada.
    sem_competencia = cliente.post(f"{base}/itens/pedir-execucao", json={"chaves": ["5081"]})
    assert sem_competencia.status_code == 422
    assert sem_competencia.json()["error"]["details"]["campos"] == {"competencia": "obrigatório"}
    estranho = cliente.post(f"{base}/itens/pedir-execucao", json={"chaves": ["5081"],
                                                                   "parametros": {"competencia": "10/2026", "senha": "x"}})
    assert estranho.status_code == 422 and "senha" in estranho.json()["error"]["details"]["campos"]
    pedido = cliente.post(f"{base}/itens/pedir-execucao", json={"chaves": ["5081"], "parametros": {"competencia": "102026"}})
    assert pedido.status_code == 201, pedido.text
    job = pedido.json()["jobs"][0]["job_id"]
    parametros = sessao.execute(text("SELECT parameters FROM task_executions WHERE id = :j"), {"j": job}).scalar_one()
    assert parametros == {"competencia": "10/2026", "modo": "completo"}
    print(f"\ncampos: manifesto -> portal (v1, auditado); item exige a pasta e guarda o resto;"
          f" pedido sem competência 422, com '102026' -> {parametros}")


def test_quem_so_executa_ve_mas_nao_edita_os_campos(cliente, sessao) -> None:
    _admin(cliente, sessao)
    automation_id, version_id = automacao(sessao)
    publicar(sessao, version_id)
    operador, _ = _usuario(sessao, "operator")
    _conceder(sessao, automation_id, operador, ["executar"])
    with como(cliente, operador, "operator"):
        visto = cliente.get(f"/api/v1/automations/{automation_id}/formulario")
        assert visto.status_code == 200 and visto.json()["pode_editar"] is False
        assert cliente.put(f"/api/v1/automations/{automation_id}/formulario",
                           json={"entrada": ENTRADA, "colunas": []}).status_code == 403
    outro, _ = _usuario(sessao, "operator")
    with como(cliente, outro, "operator"):
        assert cliente.get(f"/api/v1/automations/{automation_id}/formulario").status_code == 403


def test_arquivar_tira_do_catalogo_bloqueia_executar_e_restaurar_volta(cliente, sessao) -> None:
    _admin(cliente, sessao)
    automation_id, version_id = automacao(sessao)
    publicar(sessao, version_id)
    base = f"/api/v1/automations/{automation_id}"
    cliente.post(f"{base}/itens", json={"chave": "5081", "rotulo": "Matriz", "atributos": {}})
    assert cliente.delete(base).status_code == 204
    assert cliente.get(base).json()["status"] == "archived"
    bloqueado = cliente.post(f"{base}/itens/pedir-execucao", json={"chaves": ["5081"]})
    assert bloqueado.status_code == 422 and "arquivada" in bloqueado.text
    assert cliente.get(f"{base}/itens").json()["contagem"]["total"] == 1  # os itens continuam guardados
    voltou = cliente.post(f"{base}/restaurar").json()
    assert (voltou["status"], voltou["is_active"]) == ("active", True)
    assert cliente.post(f"{base}/itens/pedir-execucao", json={"chaves": ["5081"]}).status_code == 201
    acoes = sessao.execute(text("SELECT action FROM audit_events WHERE resource_type = 'automation' AND resource_id = :a"
                                " AND action IN ('automation.archived', 'automation.restored') ORDER BY occurred_at"),
                           {"a": str(automation_id)}).scalars().all()
    assert acoes == ["automation.archived", "automation.restored"]
