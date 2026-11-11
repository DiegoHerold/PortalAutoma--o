"""Fase 8 no PostgreSQL: a automação se declara ao conectar (campos, item e tabela em prévia)
e os arquivos que ela entrega (guardar, listar, baixar com auditoria e retenção)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from tests.db.semente import automacao, publicar
from tests.db.test_fase4_acompanhar import como
from tests.db.test_fase6_notificacoes_retencao import _conceder, _job_direto, _usuario
from tests.db.test_modo_direto_inscricao import Instancia, _codigo

COMPETENCIA = {"chave": "competencia", "rotulo": "Competência", "tipo": "mes_ano", "obrigatorio": True}
MODO = {"chave": "modo", "rotulo": "Modo", "tipo": "lista", "opcoes": ["completo", "rubricas"], "padrao": "completo"}


def _auditoria(sessao, acao: str, recurso: str) -> list[tuple]:
    sessao.expire_all()
    return [tuple(r) for r in sessao.execute(text(
        "SELECT actor_type, actor_id FROM audit_events WHERE action = :a AND resource_id = :r ORDER BY occurred_at"),
        {"a": acao, "r": recurso})]


def _instancia_com_sessao(cliente, automation_id: int, aprovar: bool = True) -> tuple[Instancia, dict]:
    instancia = Instancia(cliente)
    assert instancia.inscrever(_codigo(cliente, automation_id)).status_code == 201
    if aprovar:
        mch = cliente.post("/api/v1/maquinas", json={"nome": f"MAQ-{uuid.uuid4().hex[:6]}"}).json()["id"]
        assert cliente.post(f"/api/v1/instancias-diretas/{instancia.id}/aprovar", json={"maquina_id": mch}).status_code == 200
    token = instancia.sessao().json()["token"]
    return instancia, {"Authorization": f"Bearer {token}"}


def test_declaracao_junta_campos_e_poe_a_tabela_em_previa(cliente, sessao) -> None:
    admin, _ = _usuario(sessao, "admin")
    automation_id, version_id = automacao(sessao)
    publicar(sessao, version_id)
    base = f"/api/v1/automations/{automation_id}"
    with como(cliente, admin, "admin"):
        # Pendente: a declaração ainda não muda nada.
        _, pendente = _instancia_com_sessao(cliente, automation_id, aprovar=False)
        assert cliente.post("/api/v1/direto/declaracao", json={"parametros": [COMPETENCIA]}, headers=pendente).status_code == 403
        assert cliente.post("/api/v1/direto/declaracao", json={}).status_code == 401

        instancia, cab = _instancia_com_sessao(cliente, automation_id)
        ruim = cliente.post("/api/v1/direto/declaracao", json={"parametros": [{"chave": "A"}]}, headers=cab)
        assert ruim.status_code == 422 and "parametros.campos[0].chave" in ruim.json()["campos"]
        assert cliente.post("/api/v1/direto/declaracao", content=b"{", headers={**cab, "Content-Type": "application/json"}).status_code == 400

        tabela = [{"chave": "5081", "rotulo": "Matriz", "atributos": {"separar_por_custo": True}},
                  {"chave": "5082", "rotulo": "Filial", "grupo": "5081"}]
        r = cliente.post("/api/v1/direto/declaracao", headers=cab, json={
            "versao": "2.1.0", "parametros": [COMPETENCIA, MODO], "itens": {"nome": "Empresa", "chave": "codigo"},
            "tabela": tabela})
        assert r.status_code == 200, r.text
        assert r.json()["entrada"]["novos"] == ["competencia", "modo"] and r.json()["item"] is None  # manifesto já define
        assert r.json()["tabela"] == {"novos": 2, "alterados": 0, "iguais": 0, "erros": 0}

        form = cliente.get(f"{base}/formulario").json()
        assert form["origem"] == "portal" and form["versao"] == 1
        assert [(c["chave"], c["origem"], c["fora_de_uso"]) for c in form["entrada"]] == [
            ("competencia", "automacao", False), ("modo", "automacao", False)]
        assert _auditoria(sessao, "automacao.declarada", str(automation_id)) == [("direct_instance", instancia.id)]

        # O Portal edita o rótulo; a automação declara de novo sem "modo": rótulo fica, modo sai de uso.
        editado = [{**COMPETENCIA, "rotulo": "Mês de referência"}, MODO]
        assert cliente.put(f"{base}/formulario", json={"entrada": editado, "colunas": form["colunas"], "versao": 1}).status_code == 200
        r2 = cliente.post("/api/v1/direto/declaracao", headers=cab, json={"parametros": [COMPETENCIA]}).json()
        assert r2["entrada"] == {"novos": [], "fora_de_uso": ["modo"], "voltaram": []}
        form = cliente.get(f"{base}/formulario").json()
        assert [(c["chave"], c["rotulo"], c["fora_de_uso"]) for c in form["entrada"]] == [
            ("competencia", "Mês de referência", False), ("modo", "Modo", True)]
        # Fora de uso não é exigido no pedido; a competência é.
        assert cliente.post(f"{base}/itens", json={"chave": "1", "rotulo": "Um"}).status_code == 201
        sem = cliente.post(f"{base}/itens/pedir-execucao", json={"chaves": ["1"]})
        assert sem.status_code == 422 and sem.json()["error"]["details"]["campos"] == {"competencia": "obrigatório"}

        # Prévia: quem não edita itens não vê; aprovar só o escolhido grava e tira a prévia.
        operador, _ = _usuario(sessao, "sem_permissao")
        _conceder(sessao, automation_id, operador, ["executar"])
        with como(cliente, operador, "sem_permissao"):
            assert cliente.get(f"{base}/itens/proposta").status_code == 403
            assert cliente.post(f"{base}/itens/proposta/aprovar", json={}).status_code == 403
        previa = cliente.get(f"{base}/itens/proposta").json()
        assert previa["total"] == 2 and previa["instancia_id"] == instancia.id
        assert [n["chave"] for n in previa["novos"]] == ["5081", "5082"]
        so_filial = cliente.post(f"{base}/itens/proposta/aprovar", json={"chaves": ["5082"]})
        assert so_filial.status_code == 422  # a filial aponta para a matriz, que não estaria no cadastro
        assert cliente.post(f"{base}/itens/proposta/aprovar", json={"chaves": "5081"}).status_code == 422
        aprovado = cliente.post(f"{base}/itens/proposta/aprovar", json={})
        assert aprovado.json() == {"criados": 2, "alterados": 0, "iguais": 0}, aprovado.text
        assert cliente.get(f"{base}/itens/proposta").json() is None
        assert cliente.post(f"{base}/itens/proposta/aprovar", json={}).status_code == 404
        assert _auditoria(sessao, "automacao.itens.proposta.aprovada", f"{automation_id}:*") == [("user", str(admin))]

        # Mesma tabela de novo: nada a aprovar. Tabela diferente e descartada: some, com auditoria.
        assert cliente.post("/api/v1/direto/declaracao", headers=cab, json={
            "itens": {"nome": "Empresa", "chave": "codigo"}, "tabela": tabela}).json()["tabela"]["iguais"] == 2
        assert cliente.get(f"{base}/itens/proposta").json() is None
        cliente.post("/api/v1/direto/declaracao", headers=cab, json={
            "itens": {"nome": "Empresa", "chave": "codigo"}, "tabela": [{"chave": "5081", "rotulo": "Matriz nova"}]})
        assert [a["chave"] for a in cliente.get(f"{base}/itens/proposta").json()["alterados"]] == ["5081"]
        assert cliente.delete(f"{base}/itens/proposta").status_code == 204
        assert cliente.get(f"{base}/itens/proposta").json() is None
        assert cliente.delete(f"{base}/itens/proposta").status_code == 404
        assert len(_auditoria(sessao, "automacao.itens.proposta.descartada", f"{automation_id}:*")) == 1
    print(f"\ndeclaração: pendente 403; campos juntados (edição do Portal vale, 'modo' fora de uso); "
          f"tabela -> prévia -> aprovada (2 itens) / descartada; auditoria ok")


def test_arquivos_entregues_listar_baixar_e_retencao(cliente, sessao) -> None:
    from modules.telemetry.infrastructure.adapters.notificacoes import build_aplicar_retencao

    admin, _ = _usuario(sessao, "admin")
    automation_id, version_id = automacao(sessao)
    outra_id, _ = automacao(sessao)
    job = _job_direto(sessao, automation_id, version_id)
    base = f"/api/v1/automations/{automation_id}/arquivos"
    url = f"/api/v1/direto/jobs/{job.job_id}/arquivos"
    cab = {"Authorization": f"Bearer {job.token}", "Content-Type": "text/plain"}
    with como(cliente, admin, "admin"):
        assert cliente.put(url, params={"nome": "x.txt"}, content=b"a").status_code == 401  # sem token
        assert cliente.put(url, params={"nome": "x.txt"}, content=b"", headers=cab).status_code == 422
        txt = cliente.put(url, params={"nome": r"C:\saida\5081\integracao 10-2026.txt", "item": "5081"},
                          content="linha;ção\n".encode(), headers=cab)
        assert txt.status_code == 201, txt.text
        assert txt.json()["nome"] == "integracao 10-2026.txt" and txt.json()["bytes"] == len("linha;ção\n".encode())
        planilha = cliente.put(url, params={"nome": "Resumo.xlsx"}, content=b"PK\x03\x04xlsx",
                               headers={**cab, "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"})
        assert planilha.status_code == 201
        # Imagem de passo também é artefato, mas não aparece na aba Arquivos.
        sessao.execute(text("UPDATE artifacts SET name = 'passos/img.jpg' WHERE id = :i"), {"i": planilha.json()["arquivo_id"]})
        sessao.commit()
        lista = cliente.get(base).json()
        assert [(a["nome"], a["item"], a["execucao_id"]) for a in lista["arquivos"]] == [
            ("integracao 10-2026.txt", "5081", job.execution_id)]
        sessao.execute(text("UPDATE artifacts SET name = 'Resumo.xlsx' WHERE id = :i"), {"i": planilha.json()["arquivo_id"]})
        sessao.commit()
        assert {a["nome"] for a in cliente.get(base).json()["arquivos"]} == {"integracao 10-2026.txt", "Resumo.xlsx"}
        assert [a["nome"] for a in cliente.get(base, params={"busca": "5081"}).json()["arquivos"]] == ["integracao 10-2026.txt"]
        assert cliente.get(f"/api/v1/automations/{outra_id}/arquivos").json()["arquivos"] == []

        arquivo_id = txt.json()["arquivo_id"]
        baixado = cliente.get(f"{base}/{arquivo_id}/baixar")
        assert baixado.status_code == 200 and baixado.content == "linha;ção\n".encode()
        assert "attachment" in baixado.headers["content-disposition"] and baixado.headers["cache-control"] == "private, no-store"
        assert cliente.get(f"/api/v1/automations/{outra_id}/arquivos/{arquivo_id}/baixar").status_code == 404
        assert _auditoria(sessao, "automacao.arquivo.baixado", arquivo_id) == [("user", str(admin))]

        # Sem "ver telas e logs" não lista nem baixa; com a concessão, baixa e fica auditado.
        quem, _ = _usuario(sessao, "sem_permissao")
        with como(cliente, quem, "sem_permissao"):
            assert cliente.get(base).status_code == 403
            assert cliente.get(f"{base}/{arquivo_id}/baixar").status_code == 403
        _conceder(sessao, automation_id, quem, ["ver_telas_e_logs"])
        with como(cliente, quem, "sem_permissao"):
            assert cliente.get(f"{base}/{arquivo_id}/baixar").status_code == 200
        assert len(_auditoria(sessao, "automacao.arquivo.baixado", arquivo_id)) == 2

        # Retenção: sem prazo nada sai; com prazo, só o que passou dele (o TXT, envelhecido).
        assert [f for f in build_aplicar_retencao(sessao).execute() if f["automation_id"] == automation_id] == []
        prazo = cliente.put(f"/api/v1/governance/retencao-por-automacao/{automation_id}", json={"arquivos_dias": 30})
        assert prazo.json() == {"automation_id": automation_id, "imagens_dias": None, "logs_dias": None, "arquivos_dias": 30}
        assert cliente.put(f"/api/v1/governance/retencao-por-automacao/{automation_id}", json={"arquivos_dias": 0}).status_code == 422
        sessao.execute(text("UPDATE artifacts SET created_at = :c WHERE id = :i"),
                       {"c": datetime.now(UTC) - timedelta(days=31), "i": arquivo_id})
        sessao.commit()
        objeto = sessao.execute(text("SELECT stored_object_id FROM artifacts WHERE id = :i"), {"i": arquivo_id}).scalar_one()
        feito = [f for f in build_aplicar_retencao(sessao).execute() if f["automation_id"] == automation_id]
        assert [(f["arquivos"], f["imagens"], f["linhas_de_log"]) for f in feito] == [(1, 0, 0)]
        sessao.expire_all()
        assert sessao.execute(text("SELECT status FROM stored_objects WHERE id = :i"), {"i": objeto}).scalar_one() == "deleted"
        assert sessao.execute(text("SELECT status FROM artifacts WHERE id = :i"), {"i": arquivo_id}).scalar_one() == "deleted"
        assert cliente.get(f"{base}/{arquivo_id}/baixar").status_code == 410
        assert [a["nome"] for a in cliente.get(base).json()["arquivos"]] == ["Resumo.xlsx"]
        assert [f for f in build_aplicar_retencao(sessao).execute() if f["automation_id"] == automation_id] == []
    print("\narquivos: TXT e planilha guardados; imagem de passo fora da lista; download só com 'ver telas e logs',"
          " auditado; retenção de 30 dias apagou o TXT velho (410) e manteve a planilha")
