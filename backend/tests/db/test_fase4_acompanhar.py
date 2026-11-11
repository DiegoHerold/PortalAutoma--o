"""Fase 4 no PostgreSQL: imagens dos passos nos dois modos, Acompanhar, logs, concessões por
automação, tempo real por LISTEN/NOTIFY e nenhuma credencial na URL."""

from __future__ import annotations

import asyncio
import contextlib
import io
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from tests.db.semente import Roteiro, automacao, execucao, instancia_direta, maquina, tentativa_direta


@pytest.fixture(autouse=True)
def _storage_temporario(tmp_path, monkeypatch):
    """Imagens dos testes nunca vão para a pasta real do portal."""
    from infrastructure.config import get_settings

    monkeypatch.setattr(get_settings(), "local_storage_path", str(tmp_path / "storage"))
    monkeypatch.setattr(get_settings(), "storage_backend", "local")


def jpeg(largura: int = 1280, altura: int = 720, cor_unica: bool = False) -> bytes:
    from PIL import Image

    imagem = Image.new("RGB", (largura, altura), (40, 60, 90))
    if not cor_unica:
        for x in range(0, largura, 7):
            for y in range(0, altura, 97):
                imagem.putpixel((x, y), (250, 250, 250))
    saida = io.BytesIO()
    imagem.save(saida, "JPEG", quality=85)
    return saida.getvalue()


def _usuario(sessao, papel: str = "viewer") -> int:
    role = sessao.execute(text("SELECT id FROM roles WHERE slug = :s ORDER BY id LIMIT 1"), {"s": papel}).scalar()
    if role is None:  # o banco de teste só tem as migrations; os papéis vêm do seed da aplicação
        role = sessao.execute(text("INSERT INTO roles (name, slug, status, is_system) VALUES (:n, :s, 'active', true) "
                                   "RETURNING id"), {"n": papel.title(), "s": papel}).scalar_one()
    uid = sessao.execute(text(
        "INSERT INTO users (name, email, password_hash, role_id, status, is_active) "
        "VALUES (:n, :e, 'x', :r, 'active', true) RETURNING id"),
        {"n": f"Pessoa {papel}", "e": f"{uuid.uuid4().hex[:10]}@teste.invalid", "r": role}).scalar_one()
    sessao.commit()
    return uid


def _time_com(sessao, user_id: int) -> int:
    org = sessao.execute(text("INSERT INTO access_organizations (key, name) VALUES (:k, 'Org teste') RETURNING id"),
                         {"k": f"org-{uuid.uuid4().hex[:8]}"}).scalar_one()
    time_id = sessao.execute(text("INSERT INTO access_teams (organization_id, key, name) VALUES (:o, :k, 'Fiscal') RETURNING id"),
                             {"o": org, "k": f"t-{uuid.uuid4().hex[:6]}"}).scalar_one()
    sessao.execute(text("INSERT INTO access_team_memberships (team_id, user_id) VALUES (:t, :u)"), {"t": time_id, "u": user_id})
    sessao.commit()
    return time_id


@contextlib.contextmanager
def como(cliente, user_id: int, papel: str):
    from modules.access.api.dependencies import get_current_user

    anterior = cliente.app.dependency_overrides[get_current_user]
    cliente.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=user_id, role=SimpleNamespace(slug=papel), category_permissions=[], permissions=[])
    try:
        yield
    finally:
        cliente.app.dependency_overrides[get_current_user] = anterior


@pytest.fixture
def job(sessao, cliente):
    from modules.access.api.dependencies import get_current_user

    admin = _usuario(sessao, "admin")
    cliente.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=admin, role=SimpleNamespace(slug="admin"), category_permissions=[], permissions=[])
    automation_id, version_id = automacao(sessao)
    mch = maquina(sessao, f"FOLHA-{uuid.uuid4().hex[:4]}")
    instancia = instancia_direta(sessao, automation_id, mch)
    execution_id, job_id = execucao(sessao, version_id, datetime.now(UTC) - timedelta(minutes=5))
    attempt_id, token = tentativa_direta(sessao, job_id, instancia, mch)
    sessao.execute(text("UPDATE task_executions SET status = 'running' WHERE id = :j"), {"j": job_id})
    sessao.commit()
    return SimpleNamespace(automation_id=automation_id, execution_id=execution_id, job_id=job_id,
                           attempt_id=attempt_id, token=token, machine=mch, admin=admin)


def _put_imagem(cliente, job, imagem_id: str, conteudo: bytes, tipo: str = "image/jpeg", token: str | None = None):
    return cliente.put(f"/api/v1/direto/jobs/{job.job_id}/imagens/{imagem_id}", content=conteudo,
                       headers={"Content-Type": tipo, "Authorization": f"Bearer {token or job.token}"})


def _eventos(cliente, job, eventos: list[dict]):
    resposta = cliente.post(f"/api/v1/direto/jobs/{job.job_id}/eventos", json={"eventos": eventos},
                            headers={"Authorization": f"Bearer {job.token}"})
    assert resposta.status_code == 200 and resposta.json()["recusados"] == [], resposta.text
    return resposta


# -- Imagens ---------------------------------------------------------------------------------

def test_imagem_do_modo_direto_vira_tres_medidas_sem_metadados(cliente, sessao, job) -> None:
    from PIL import Image

    resposta = _put_imagem(cliente, job, "img_tela1", jpeg())
    assert resposta.status_code == 201 and resposta.json() == {"imagem_id": "img_tela1"}
    linha = sessao.execute(text("SELECT status, largura, altura, origem FROM step_images WHERE imagem_id = 'img_tela1'")).one()
    assert tuple(linha) == ("pronta", 1280, 720, "direto")
    larguras = {}
    for tamanho in ("miniatura", "media", "cheia"):
        r = cliente.get(f"/api/v1/execucoes/{job.execution_id}/imagens/img_tela1", params={"tamanho": tamanho})
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
        assert r.headers["cache-control"].startswith("private")
        figura = Image.open(io.BytesIO(r.content))
        larguras[tamanho] = figura.width
        assert not figura.info.get("exif")
    assert larguras == {"miniatura": 320, "media": 960, "cheia": 1280}
    print(f"\nimagem do passo (modo direto): 201; medidas {larguras}; sem EXIF")


@pytest.mark.parametrize("conteudo,tipo,status,motivo", [
    (b"\xff\xd8\xff" + b"lixo" * 100, "image/jpeg", 422, "imagem corrompida"),
    (b"GIF89a....", "image/jpeg", 422, "não é um JPEG"),
    (None, "image/jpeg", 422, "imagem vazia ou de uma cor só"),
    (b"\xff\xd8\xff" + b"0" * (4 * 1024 * 1024 + 1), "image/jpeg", 413, None),
    (b"qualquer", "image/png", 415, None),
], ids=["corrompida", "nao-jpeg", "cor-unica", "grande-demais", "tipo-errado"])
def test_imagem_recusada_com_o_codigo_do_contrato(cliente, sessao, job, conteudo, tipo, status, motivo) -> None:
    imagem_id = f"img_{uuid.uuid4().hex[:8]}"
    resposta = _put_imagem(cliente, job, imagem_id, conteudo if conteudo is not None else jpeg(cor_unica=True), tipo)
    assert resposta.status_code == status, resposta.text
    if motivo:
        assert resposta.json() == {"erro": motivo}
        registro = sessao.execute(text("SELECT status, motivo_recusa FROM step_images WHERE imagem_id = :i"),
                                  {"i": imagem_id}).one()
        assert tuple(registro) == ("recusada", motivo)


def test_imagem_repetida_nao_duplica_e_token_de_outro_job_e_recusado(cliente, sessao, job) -> None:
    assert _put_imagem(cliente, job, "img_rep", jpeg()).status_code == 201
    assert _put_imagem(cliente, job, "img_rep", jpeg()).status_code == 201
    assert sessao.execute(text("SELECT count(*) FROM step_images WHERE imagem_id = 'img_rep'")).scalar_one() == 1
    assert _put_imagem(cliente, job, "img_x", jpeg(), token="token-falso").status_code == 401
    assert _put_imagem(cliente, job, "../fora", jpeg()).status_code in (404, 422)


def test_modo_agente_arquivo_passos_que_subiu_vira_imagem_do_passo(sessao, job) -> None:
    from gateway.agent_gateway.message_router import _registrar_imagem_do_passo
    from modules.storage.application.use_cases.objetos import GuardarObjeto
    from modules.storage.infrastructure.adapters import build_storage_adapters

    adapters = build_storage_adapters(sessao)
    objeto = GuardarObjeto(adapters.object_storage, adapters.stored_objects).execute(
        bucket="artifacts", object_key=f"{job.attempt_id}/passos/img_agente.jpg", conteudo=jpeg(), content_type="image/jpeg")
    sessao.commit()
    artefato = SimpleNamespace(name="passos/img_agente.jpg", stored_object_id=objeto.id, execution_attempt_id=job.attempt_id)
    _registrar_imagem_do_passo(sessao, artefato)
    linha = sessao.execute(text("SELECT status, origem FROM step_images WHERE imagem_id = 'img_agente'")).one()
    assert tuple(linha) == ("pronta", "agente")
    # Outro artefato qualquer não vira imagem.
    _registrar_imagem_do_passo(sessao, SimpleNamespace(name="relatorio.pdf", stored_object_id=objeto.id,
                                                       execution_attempt_id=job.attempt_id))
    assert sessao.execute(text("SELECT count(*) FROM step_images WHERE execution_attempt_id = :a"),
                          {"a": job.attempt_id}).scalar_one() == 1
    print("\nmodo agente: passos/img_agente.jpg subiu como artefato -> imagem do passo pronta (origem agente)")


# -- Acompanhar e logs -----------------------------------------------------------------------

def _passo(r: Roteiro, **payload) -> Roteiro:
    """O passo tem um campo ``tipo``, que colide com o parâmetro de ``Roteiro.emitir``."""
    from portal_automacoes import eventos as contrato

    evento = contrato.montar(len(r.eventos) + 1, "passo", payload)
    evento["occurred_at"] = r.agora.isoformat().replace("+00:00", "Z")
    contrato.validar(evento)
    r.eventos.append(evento)
    return r


def _roteiro(job, inicio: datetime) -> list[dict]:
    r = Roteiro(inicio)
    r.emitir("execucao.iniciada").emitir("item.iniciado", item="5066", rotulo="Empresa 5066")
    r.emitir("etapa.iniciada", etapa="rubricas", item="5066", tarefas_previstas=50)
    _passo(r, rotulo="Abriu Rubricas", tipo="abriu", imagem_id="img_a", item="5066")
    r.emitir("log", nivel="info", texto="Centro 1 de 50", item="5066")
    r.passar(5).emitir("log", nivel="info", texto="aguardando a Domínio responder", espera=True)
    r.emitir("progresso", atual=18, total=50, rotulo="centro 18 de 50", item="5066")
    _passo(r.passar(2), rotulo="Salvou o centro 18", tipo="acao", imagem_id="img_b", item="5066")
    r.emitir("log", nivel="aviso", texto="senha=segredo123 não pode aparecer", item="5066")
    return r.eventos


def test_acompanhar_mostra_o_agora_e_so_mostra_tela_com_concessao(cliente, sessao, job) -> None:
    assert _put_imagem(cliente, job, "img_a", jpeg()).status_code == 201
    assert _put_imagem(cliente, job, "img_b", jpeg()).status_code == 201
    _eventos(cliente, job, _roteiro(job, datetime.now(UTC) - timedelta(seconds=40)))

    visao = cliente.get(f"/api/v1/execucoes/{job.execution_id}/acompanhar").json()
    agora = visao["agora"]
    assert agora["etapa_atual"]["etapa"] == "rubricas" and agora["item_atual"]["item"] == "5066"
    assert agora["progresso"] == {"atual": 18, "total": 50, "rotulo": "centro 18 de 50", "item": "5066"}
    assert agora["tela"]["imagem_id"] == "img_b" and agora["tela"]["imagem"] == {"situacao": "pronta", "motivo": None}
    assert 25 <= agora["tela"]["segundos_nesta_tela"] <= 60
    assert [p["imagem_id"] for p in agora["passos"]] == ["img_a", "img_b"]
    assert visao["pode"]["ver_telas_e_logs"] is True and visao["jobs"][0]["maquina_nome"].startswith("FOLHA-")
    assert visao["jobs"][0]["modo"] == "direct" or visao["jobs"][0]["modo"] == "direto"

    # Quem vê as execuções pela categoria, mas não tem a concessão de telas e logs:
    pessoa = _usuario(sessao)
    with como(cliente, pessoa, "viewer"):
        assert cliente.get(f"/api/v1/execucoes/{job.execution_id}/acompanhar").status_code == 403
    sessao.execute(text("INSERT INTO automation_grants (id, automation_id, user_id, acoes) "
                        "VALUES (:i, :a, :u, '[\"ver_execucoes\"]')"),
                   {"i": f"agr_{uuid.uuid4().hex}", "a": job.automation_id, "u": pessoa})
    sessao.commit()
    with como(cliente, pessoa, "viewer"):
        so_execucoes = cliente.get(f"/api/v1/execucoes/{job.execution_id}/acompanhar").json()
        assert so_execucoes["pode"]["ver_telas_e_logs"] is False
        assert so_execucoes["agora"]["tela"] is None and so_execucoes["agora"]["passos"] == []
        assert so_execucoes["agora"]["etapa_atual"]["etapa"] == "rubricas"  # o andamento continua visível
        assert cliente.get(f"/api/v1/execucoes/{job.execution_id}/logs").status_code == 403
        assert cliente.get(f"/api/v1/execucoes/{job.execution_id}/imagens/img_b").status_code == 403
    print(f"\nacompanhar: etapa rubricas, item 5066, progresso 18/50, tela img_b há "
          f"{agora['tela']['segundos_nesta_tela']} s; sem concessão de telas: tela, passos, logs e imagens negados")


def test_logs_ultimos_cursor_espera_oculta_e_segredo_removido(cliente, sessao, job) -> None:
    _eventos(cliente, job, _roteiro(job, datetime.now(UTC) - timedelta(seconds=30)))
    base = f"/api/v1/execucoes/{job.execution_id}/logs"
    pagina = cliente.get(base).json()
    textos = [l["texto"] for l in pagina["logs"]]
    assert textos == ["Centro 1 de 50", "senha=*** não pode aparecer"] or textos == ["Centro 1 de 50", "senha=***não pode aparecer"]
    com_espera = cliente.get(base, params={"esconder_espera": "false"}).json()
    assert "aguardando a Domínio responder" in [l["texto"] for l in com_espera["logs"]]
    ultimos = cliente.get(base, params={"limite": 1}).json()
    assert [l["nivel"] for l in ultimos["logs"]] == ["aviso"]

    r = Roteiro(datetime.now(UTC))
    for _ in range(10):
        r.emitir("log", nivel="info", texto="x")
    for i, e in enumerate(r.eventos):  # continua a sequência da tentativa
        e["sequence"] = 11 + i
    _eventos(cliente, job, r.eventos)
    depois = cliente.get(base, params={"depois": pagina["cursor"]}).json()
    assert [l["texto"] for l in depois["logs"]] == ["x"] * 10
    assert cliente.get(base, params={"depois": depois["cursor"]}).json()["logs"] == []
    print(f"\nlogs: últimos {len(pagina['logs'])} sem as esperas; segredo mascarado ('{textos[-1]}'); "
          f"cursor traz só os 10 novos")


# -- Concessões ------------------------------------------------------------------------------

def test_concessao_por_time_da_telas_e_logs_e_fica_na_auditoria(cliente, sessao, job) -> None:
    pessoa = _usuario(sessao)
    time_id = _time_com(sessao, pessoa)
    assert _put_imagem(cliente, job, "img_t", jpeg()).status_code == 201
    url = f"/api/v1/automations/{job.automation_id}/acessos"
    with como(cliente, pessoa, "viewer"):
        assert cliente.get(f"/api/v1/execucoes/{job.execution_id}/imagens/img_t").status_code == 403
        assert cliente.put(url, json={"team_id": time_id, "acoes": ["ver_telas_e_logs"]}).status_code == 403
    resposta = cliente.put(url, json={"team_id": time_id, "acoes": ["ver_telas_e_logs", "ver_telas_e_logs"]})
    assert resposta.status_code == 200 and resposta.json()["concessao"]["acoes"] == ["ver_telas_e_logs"]
    assert cliente.put(url, json={"team_id": time_id, "acoes": ["apagar_tudo"]}).status_code == 422
    with como(cliente, pessoa, "viewer"):
        assert cliente.get(f"{url}/minhas").json() == {"acoes": ["ver_execucoes", "ver_telas_e_logs"]}
        assert cliente.get(f"/api/v1/execucoes/{job.execution_id}/imagens/img_t").status_code == 200
    assert cliente.put(url, json={"team_id": time_id, "acoes": []}).json() == {"concessao": None}
    with como(cliente, pessoa, "viewer"):
        assert cliente.get(f"/api/v1/execucoes/{job.execution_id}/imagens/img_t").status_code == 403
    acoes = [a for (a,) in sessao.execute(text(
        "SELECT action FROM audit_events WHERE resource_type = 'automation_grant' AND after->>'team_id' = :t "
        "ORDER BY occurred_at"), {"t": str(time_id)})]
    assert acoes == ["automacao.concessao.definida", "automacao.concessao.retirada"]
    print("\nconcessão ao time Fiscal: imagem 403 -> 200 -> retirada -> 403; auditoria: " + ", ".join(acoes))


def test_ver_imagem_e_auditado(cliente, sessao, job) -> None:
    assert _put_imagem(cliente, job, "img_aud", jpeg()).status_code == 201
    for _ in range(3):
        cliente.get(f"/api/v1/execucoes/{job.execution_id}/imagens/img_aud", params={"tamanho": "miniatura"})
    cliente.get(f"/api/v1/execucoes/{job.execution_id}/imagens/img_aud", params={"tamanho": "cheia"})
    acoes = sorted(a for (a,) in sessao.execute(text(
        "SELECT action FROM audit_events WHERE resource_type = 'execution' AND resource_id = :e"), {"e": job.execution_id}))
    assert acoes == ["execucao.tela.ampliada", "execucao.telas.vistas"]


# -- Tempo real e credencial fora da URL -----------------------------------------------------

def test_aviso_atravessa_conexoes_por_listen_notify(cliente, sessao, job) -> None:
    from modules.telemetry.infrastructure.realtime.postgres import CANAL_EXECUCAO, esperar_aviso, notificar, ouvinte

    async def cenario() -> tuple[bool, bool, float]:
        async with ouvinte.assinar(CANAL_EXECUCAO, job.execution_id) as sinal:
            for _ in range(100):  # a thread de escuta conecta
                if ouvinte.conectado:
                    break
                await asyncio.sleep(0.05)
            await asyncio.sleep(0.2)
            sinal.clear()
            inicio = asyncio.get_running_loop().time()
            # Gravar eventos pela API (outra conexão do pool) avisa quem está ouvindo.
            await asyncio.to_thread(_eventos, cliente, job, Roteiro(datetime.now(UTC)).emitir("execucao.iniciada").eventos)
            chegou = await esperar_aviso(sinal, 5)
            demora = asyncio.get_running_loop().time() - inicio
            notificar(CANAL_EXECUCAO, "outra-execucao")
            alheio = await esperar_aviso(sinal, 0.5)
            return chegou, alheio, demora

    chegou, alheio, demora = asyncio.run(cenario())
    assert chegou is True and alheio is False
    print(f"\nLISTEN/NOTIFY: evento gravado pela API -> aviso em {demora * 1000:.0f} ms; aviso de outra execução não chega")


def test_stream_e_websocket_nao_aceitam_token_na_url(cliente, sessao, job) -> None:
    from starlette.websockets import WebSocketDisconnect

    from modules.access.infrastructure.authentication import JwtTokenIssuer

    token = JwtTokenIssuer().create_access_token(str(job.admin))  # válido: mesmo assim não vale na URL
    assert cliente.get(f"/api/v1/executions/{job.execution_id}/stream", params={"token": token}).status_code == 401
    assert cliente.get(f"/api/v1/execucoes/{job.execution_id}/avisos", params={"token": token}).status_code == 401
    assert cliente.get("/api/v1/fila/avisos", params={"token": token}).status_code == 401

    with cliente.websocket_connect(f"/api/v1/ws/executions?token={token}") as ws:
        ws.send_text("ping")  # sem a mensagem de autenticação: fecha
        with pytest.raises(WebSocketDisconnect) as fechado:
            ws.receive_text()
    assert fechado.value.code == 4001
    with cliente.websocket_connect("/api/v1/ws/executions") as ws:
        ws.send_json({"type": "auth", "token": token})
        assert ws.receive_json()["type"] == "connected"
    print("\ntoken na URL: stream 401, avisos 401, fila/avisos 401, WebSocket fecha 4001; "
          "WebSocket com a autenticação na 1ª mensagem: conectado")


def test_dez_execucoes_simultaneas_recebem_avisos_sem_perder_eventos(cliente, sessao) -> None:
    """Plano da Fase 0: 10 automações ao mesmo tempo, cada uma com 10 lotes de eventos."""
    import statistics
    import threading
    import time

    from modules.access.api.dependencies import get_current_user
    from modules.telemetry.infrastructure.realtime.postgres import CANAL_EXECUCAO, ouvinte

    admin = _usuario(sessao, "admin")
    cliente.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=admin, role=SimpleNamespace(slug="admin"), category_permissions=[], permissions=[])
    jobs = []
    for _ in range(10):
        automation_id, version_id = automacao(sessao)
        mch = maquina(sessao)
        instancia = instancia_direta(sessao, automation_id, mch)
        execution_id, job_id = execucao(sessao, version_id, datetime.now(UTC))
        attempt_id, token = tentativa_direta(sessao, job_id, instancia, mch)
        jobs.append(SimpleNamespace(execution_id=execution_id, job_id=job_id, token=token))

    LOTES, POR_LOTE = 10, 5
    latencias: list[float] = []
    falhas: list[str] = []

    async def cenario() -> None:
        sinais = {}
        async with contextlib.AsyncExitStack() as pilha:
            for j in jobs:
                sinais[j.execution_id] = await pilha.enter_async_context(ouvinte.assinar(CANAL_EXECUCAO, j.execution_id))
            for _ in range(100):
                if ouvinte.conectado:
                    break
                await asyncio.sleep(0.05)

            def automacao_rodando(j) -> None:
                r = Roteiro(datetime.now(UTC))
                for n in range(LOTES * POR_LOTE):
                    r.emitir("log", nivel="info", texto=f"linha {n}")
                for lote in range(LOTES):
                    corpo = {"eventos": r.eventos[lote * POR_LOTE:(lote + 1) * POR_LOTE]}
                    resposta = cliente.post(f"/api/v1/direto/jobs/{j.job_id}/eventos", json=corpo,
                                            headers={"Authorization": f"Bearer {j.token}"})
                    if resposta.status_code != 200:
                        falhas.append(resposta.text)

            laco = asyncio.get_running_loop()
            inicio = {}
            for sinal in sinais.values():
                sinal.clear()
            for j in jobs:
                inicio[j.execution_id] = laco.time()
                threading.Thread(target=automacao_rodando, args=(j,), daemon=True).start()
            for j in jobs:
                await asyncio.wait_for(sinais[j.execution_id].wait(), timeout=30)
                latencias.append(laco.time() - inicio[j.execution_id])
            # espera todos os lotes terminarem
            limite = time.monotonic() + 60
            while time.monotonic() < limite:
                total = sessao.execute(text("SELECT count(*) FROM execution_events WHERE execution_id = ANY(:ids)"),
                                       {"ids": [j.execution_id for j in jobs]}).scalar_one()
                if total >= 10 * LOTES * POR_LOTE:
                    break
                await asyncio.sleep(0.2)

    asyncio.run(cenario())
    total = sessao.execute(text("SELECT count(*) FROM execution_events WHERE execution_id = ANY(:ids)"),
                           {"ids": [j.execution_id for j in jobs]}).scalar_one()
    assert falhas == [] and total == 10 * LOTES * POR_LOTE
    p95 = sorted(latencias)[int(len(latencias) * 0.95) - 1]
    print(f"\n10 execuções simultâneas: {total} eventos gravados (nenhum perdido); primeiro aviso de cada uma: "
          f"mediana {statistics.median(latencias) * 1000:.0f} ms, p95 {p95 * 1000:.0f} ms")
