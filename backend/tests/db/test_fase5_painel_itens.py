"""Fase 5 no PostgreSQL: cadastro de itens (com a importação da Integração Contábil),
pedido de execução pelo cadastro, Painel, linha do tempo e Histórico."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from tests.db.semente import Roteiro, automacao, execucao, instancia_direta, maquina, publicar, tentativa_direta


def _empresas_db(pasta: Path) -> bytes:
    """Um empresas.db com o mesmo esquema da Integração Contábil, com dados de teste."""
    arquivo = pasta / "empresas.db"
    con = sqlite3.connect(arquivo)
    con.executescript("""
        CREATE TABLE empresas (codigo INTEGER PRIMARY KEY, nome TEXT NOT NULL, matriz_codigo INTEGER,
            separar_por_custo INTEGER NOT NULL DEFAULT 0, caminho_saida TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '', ativa INTEGER NOT NULL DEFAULT 1, observacao TEXT NOT NULL DEFAULT '',
            criada_em TEXT NOT NULL, alterada_em TEXT NOT NULL);
        CREATE TABLE rubricas_ignoradas (empresa INTEGER NOT NULL, codigo INTEGER NOT NULL,
            descricao TEXT NOT NULL DEFAULT '', PRIMARY KEY (empresa, codigo));
        INSERT INTO empresas VALUES (5081, 'Matriz de teste', NULL, 1, 'C:\\saida\\5081', 'folha@teste.invalid', 1, '', 'x', 'x');
        INSERT INTO empresas VALUES (5076, 'Filial de teste', 5081, 0, 'C:\\saida\\5076', '', 1, '', 'x', 'x');
        INSERT INTO empresas VALUES (5066, 'Empresa sozinha', NULL, 0, '', '', 1, 'obs', 'x', 'x');
        INSERT INTO rubricas_ignoradas VALUES (5081, 450, 'Ajuda de custo');
    """)
    con.commit()
    con.close()
    return arquivo.read_bytes()


def como(cliente, user_id: int, papel: str):
    import contextlib

    from modules.access.api.dependencies import get_current_user

    @contextlib.contextmanager
    def _ctx():
        anterior = cliente.app.dependency_overrides[get_current_user]
        cliente.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=user_id, role=SimpleNamespace(slug=papel), category_permissions=[], permissions=[])
        try:
            yield
        finally:
            cliente.app.dependency_overrides[get_current_user] = anterior

    return _ctx()


def _usuario(sessao, papel: str = "viewer") -> int:
    role = sessao.execute(text("SELECT id FROM roles WHERE slug = :s ORDER BY id LIMIT 1"), {"s": papel}).scalar()
    if role is None:
        role = sessao.execute(text("INSERT INTO roles (name, slug, status, is_system) VALUES (:n, :s, 'active', true) RETURNING id"),
                              {"n": papel.title(), "s": papel}).scalar_one()
    uid = sessao.execute(text("INSERT INTO users (name, email, password_hash, role_id, status, is_active) "
                              "VALUES ('Pessoa', :e, 'x', :r, 'active', true) RETURNING id"),
                         {"e": f"{uuid.uuid4().hex[:10]}@teste.invalid", "r": role}).scalar_one()
    sessao.commit()
    return uid


def _conceder(sessao, automation_id: int, user_id: int, acoes: list[str]) -> None:
    import json

    sessao.execute(text("INSERT INTO automation_grants (id, automation_id, user_id, acoes) VALUES (:i, :a, :u, CAST(:c AS jsonb))"),
                   {"i": f"agr_{uuid.uuid4().hex}", "a": automation_id, "u": user_id, "c": json.dumps(acoes)})
    sessao.commit()


@pytest.fixture
def admin(cliente, sessao):
    from modules.access.api.dependencies import get_current_user

    uid = _usuario(sessao, "admin")
    cliente.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=uid, role=SimpleNamespace(slug="admin"), category_permissions=[], permissions=[])
    automation_id, version_id = automacao(sessao)
    publicar(sessao, version_id)
    return SimpleNamespace(id=uid, automation_id=automation_id, version_id=version_id)


@pytest.fixture(autouse=True)
def _storage_temporario(tmp_path, monkeypatch):
    from infrastructure.config import get_settings

    monkeypatch.setattr(get_settings(), "local_storage_path", str(tmp_path / "storage"))


# -- Cadastro de itens -------------------------------------------------------------------------

def test_importa_o_cadastro_da_integracao_contabil_com_previa(cliente, sessao, admin, tmp_path) -> None:
    base = f"/api/v1/automations/{admin.automation_id}/itens"
    arquivo = _empresas_db(tmp_path)
    previa = cliente.post(f"{base}/importar/previa", files={"arquivo": ("empresas.db", arquivo, "application/octet-stream")}).json()
    assert [n["chave"] for n in previa["novos"]] == ["5066", "5076", "5081"] and previa["erros"] == []
    matriz = next(n for n in previa["novos"] if n["chave"] == "5081")
    assert matriz["atributos"]["rubricas_ignoradas"] == [{"codigo": 450, "descricao": "Ajuda de custo"}]
    assert next(n for n in previa["novos"] if n["chave"] == "5076")["grupo"] == "5081"

    assert cliente.post(f"{base}/importar", json={"itens": previa["novos"]}).json() == {"criados": 3, "alterados": 0, "iguais": 0}
    de_novo = cliente.post(f"{base}/importar/previa", files={"arquivo": ("empresas.db", arquivo, "application/octet-stream")}).json()
    assert (de_novo["novos"], de_novo["alterados"], de_novo["iguais"]) == ([], [], 3)
    assert cliente.post(f"{base}/importar/previa", files={"arquivo": ("x.db", b"lixo", "application/octet-stream")}).status_code == 422

    lista = cliente.get(base).json()
    assert [i["chave"] for i in lista["itens"]] == ["5066", "5081", "5076"]  # filial logo depois da matriz
    assert lista["contagem"] == {"ativos": 3, "total": 3} and lista["definicao"]["nome"] == "Empresa"
    print(f"\nimportação do empresas.db: prévia 3 novos -> gravados -> nova prévia 3 iguais; ordem {[i['chave'] for i in lista['itens']]}")


def test_quem_so_executa_nao_ve_email_nem_pasta_e_nao_edita(cliente, sessao, admin, tmp_path) -> None:
    base = f"/api/v1/automations/{admin.automation_id}/itens"
    cliente.post(base, json={"chave": "5081", "rotulo": "Matriz", "atributos": {"separar_por_custo": True, "email": "a@b.c"}})
    pessoa = _usuario(sessao)
    with como(cliente, pessoa, "viewer"):
        assert cliente.get(base).status_code == 403
    _conceder(sessao, admin.automation_id, pessoa, ["executar"])
    with como(cliente, pessoa, "viewer"):
        lista = cliente.get(base).json()
        assert lista["pode_editar"] is False and lista["itens"][0]["atributos"] == {}
        assert cliente.put(f"{base}/5081", json={"rotulo": "x", "atributos": {"separar_por_custo": False}}).status_code == 403


def test_regras_do_cadastro_e_auditoria(cliente, sessao, admin) -> None:
    base = f"/api/v1/automations/{admin.automation_id}/itens"
    ok = {"separar_por_custo": False}
    assert cliente.post(base, json={"chave": "1", "rotulo": "Matriz", "atributos": ok}).status_code == 201
    assert cliente.post(base, json={"chave": "1", "rotulo": "De novo", "atributos": ok}).status_code == 409
    assert cliente.post(base, json={"chave": "2", "rotulo": "Filial", "grupo": "1", "atributos": ok}).status_code == 201
    neta = cliente.post(base, json={"chave": "3", "rotulo": "Neta", "grupo": "2", "atributos": ok})
    assert neta.status_code == 422 and "grupo" in neta.json()["error"]["details"]["campos"]
    errado = cliente.post(base, json={"chave": "4", "rotulo": "X", "atributos": {"separar_por_custo": "sim"}})
    assert errado.status_code == 422 and "atributos.separar_por_custo" in errado.json()["error"]["details"]["campos"]
    assert cliente.post(f"{base}/2/situacao", json={"ativo": False}).json() == {"chave": "2", "ativo": False}
    acoes = [a for (a,) in sessao.execute(text("SELECT action FROM audit_events WHERE resource_type = 'automation_item' "
                                               "AND resource_id LIKE :r ORDER BY occurred_at"), {"r": f"{admin.automation_id}:%"})]
    assert acoes == ["automacao.item.criado", "automacao.item.criado", "automacao.item.situacao"]


def test_pedir_execucao_pelo_cadastro_leva_as_filiais_e_o_retrato_dos_itens(cliente, sessao, admin, tmp_path) -> None:
    base = f"/api/v1/automations/{admin.automation_id}/itens"
    novos = cliente.post(f"{base}/importar/previa", files={"arquivo": ("empresas.db", _empresas_db(tmp_path), "x")}).json()["novos"]
    cliente.post(f"{base}/importar", json={"itens": novos})
    pedido = cliente.post(f"{base}/pedir-execucao", json={"chaves": ["5081"], "com_filiais": True,
                                                         "parametros": {"competencia": "10/2026"}})
    assert pedido.status_code == 201, pedido.text
    corpo = pedido.json()
    assert corpo["itens"] == ["5081", "5076"] and len(corpo["jobs"]) == 1  # matriz e filial no mesmo job
    entrada = sessao.execute(text("SELECT input FROM task_executions WHERE id = :j"), {"j": corpo["jobs"][0]["job_id"]}).scalar_one()
    retrato = {i["chave"]: i for i in entrada["dados_dos_itens"]}
    assert retrato["5081"]["configuracao"] == {"separar_por_custo": True}
    assert retrato["5076"]["atributos"]["caminho_saida"] == "C:\\saida\\5076"
    # Mudar o cadastro depois não altera o job já na fila.
    cliente.put(f"{base}/5081", json={"rotulo": "Matriz renomeada", "atributos": {"separar_por_custo": False}})
    sessao.expire_all()
    entrada = sessao.execute(text("SELECT input FROM task_executions WHERE id = :j"), {"j": corpo["jobs"][0]["job_id"]}).scalar_one()
    assert {i["chave"]: i for i in entrada["dados_dos_itens"]}["5081"]["configuracao"] == {"separar_por_custo": True}
    print("\npedido pelo cadastro: 5081 com filiais -> 1 job (5081, 5076) com o retrato dos itens; mudar o cadastro depois não mexe no job")


# -- Painel, linha do tempo e Histórico --------------------------------------------------------------

@pytest.fixture
def rodando(cliente, sessao, admin):
    mch = maquina(sessao, f"PAINEL-{uuid.uuid4().hex[:4]}")
    instancia = instancia_direta(sessao, admin.automation_id, mch)
    execution_id, job_id = execucao(sessao, admin.version_id, datetime.now(UTC) - timedelta(minutes=5))
    attempt_id, token = tentativa_direta(sessao, job_id, instancia, mch)
    sessao.execute(text("UPDATE task_executions SET status = 'running' WHERE id = :j"), {"j": job_id})
    sessao.execute(text("UPDATE execution_attempts SET started_at = now() - interval '4 minutes' WHERE id = :a"), {"a": attempt_id})
    sessao.commit()
    r = Roteiro(datetime.now(UTC) - timedelta(seconds=60))
    r.emitir("execucao.iniciada").emitir("item.iniciado", item="5066", rotulo="Empresa 5066")
    r.emitir("etapa.iniciada", etapa="rubricas", item="5066", tarefas_previstas=50)
    r.emitir("progresso", atual=18, total=50, rotulo="centro 18 de 50", item="5066")
    for n in range(8):
        r.emitir("log", nivel="info", texto=f"linha {n}", item="5066")
    resposta = cliente.post(f"/api/v1/direto/jobs/{job_id}/eventos", json={"eventos": r.eventos},
                            headers={"Authorization": f"Bearer {token}"})
    assert resposta.status_code == 200, resposta.text
    return SimpleNamespace(execution_id=execution_id, job_id=job_id, maquina=mch, token=token)


def test_painel_mostra_o_que_roda_e_respeita_as_permissoes(cliente, sessao, admin, rodando) -> None:
    painel = cliente.get("/api/v1/painel").json()
    assert painel["central"] is True
    e = next(x for x in painel["execucoes"] if x["execucao_id"] == rodando.execution_id)
    assert e["etapa"]["etapa"] == "rubricas" and e["progresso"]["atual"] == 18 and e["maquina"].startswith("PAINEL-")
    assert [l["texto"] for l in e["log"]] == [f"linha {n}" for n in range(2, 8)]  # as últimas 6
    assert e["decorrido_s"] >= 230
    assert next(m for m in painel["maquinas"] if m["id"] == rodando.maquina)["ocupada"] is True

    pessoa = _usuario(sessao)
    with como(cliente, pessoa, "viewer"):
        alheio = cliente.get("/api/v1/painel").json()
        assert alheio["central"] is False
        assert rodando.execution_id not in [x["execucao_id"] for x in alheio["execucoes"]]
        maq = next(m for m in alheio["maquinas"] if m["id"] == rodando.maquina)
        assert maq["ocupada"] is True and maq["rodando"] is None  # vê que está ocupada, não com o quê
    _conceder(sessao, admin.automation_id, pessoa, ["ver_execucoes"])
    with como(cliente, pessoa, "viewer"):
        so_andamento = next(x for x in cliente.get("/api/v1/painel").json()["execucoes"] if x["execucao_id"] == rodando.execution_id)
        assert so_andamento["progresso"]["atual"] == 18 and so_andamento["log"] is None and so_andamento["tela"] is None
    print("\npainel: admin vê etapa, progresso 18/50 e as últimas 6 linhas; sem concessão a máquina aparece ocupada "
          "sem dizer com o quê; com ver_execucoes vê o andamento, sem tela e log")


def test_linha_do_tempo_e_historico(cliente, sessao, admin, rodando) -> None:
    linha = cliente.get("/api/v1/painel/linha-do-tempo", params={"horas_antes": 2, "horas_depois": 2}).json()
    blocos = next(m for m in linha["maquinas"] if m["maquina_id"] == rodando.maquina)["blocos"]
    assert [b["tipo"] for b in blocos] == ["rodando"] and blocos[0]["automacao"]
    assert 0 < linha["agora_posicao"] < 100 and len(linha["marcas"]) >= 3

    r = Roteiro(datetime.now(UTC))
    r.emitir("item.concluido", item="5066", situacao="ok").emitir("execucao.concluida", situacao="ok", resumo="1 empresa")
    for i, ev in enumerate(r.eventos):
        ev["sequence"] = 13 + i
    cliente.post(f"/api/v1/direto/jobs/{rodando.job_id}/eventos", json={"eventos": r.eventos},
                 headers={"Authorization": f"Bearer {rodando.token}"})
    sessao.execute(text("UPDATE orchestration_executions SET status = 'succeeded', completed_at = now(), "
                        "started_at = now() - interval '5 minutes' WHERE id = :e"), {"e": rodando.execution_id})
    sessao.commit()
    historico = cliente.get("/api/v1/historico", params={"busca": "integra"}).json()
    linha_h = next(h for h in historico["execucoes"] if h["execucao_id"] == rodando.execution_id)
    assert linha_h["status"] == "succeeded" and 290 <= linha_h["duracao_s"] <= 330 and linha_h["maquinas"].startswith("PAINEL-")
    assert cliente.get("/api/v1/historico", params={"busca": "nao-existe-xyz"}).json()["execucoes"] == []
    feitos = next(m for m in cliente.get("/api/v1/painel/linha-do-tempo").json()["maquinas"] if m["maquina_id"] == rodando.maquina)
    assert [b["tipo"] for b in feitos["blocos"]] == ["feito"]
    print(f"\nlinha do tempo: rodando -> feito depois de concluir; histórico: {linha_h['status']}, "
          f"{linha_h['duracao_s']:.0f} s, previsto {linha_h['previsto_s']}")
