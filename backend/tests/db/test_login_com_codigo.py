"""Login com código por e-mail, navegador confiável, esqueci a senha, convite e trocar a senha
(13/11/2026), no PostgreSQL e pela API real, com um carteiro falso no lugar do Graph."""

from __future__ import annotations

import re
import uuid
from contextlib import contextmanager

from sqlalchemy import text

from tests.db.test_correio import Carteiro


@contextmanager
def _sem_usuario_injetado(cliente):
    from modules.access.api.dependencies import get_current_user

    anterior = cliente.app.dependency_overrides.pop(get_current_user)
    try:
        yield
    finally:
        cliente.app.dependency_overrides[get_current_user] = anterior


def _ligar_email(monkeypatch) -> Carteiro:
    import modules.telemetry.infrastructure.email_graph as graph

    carteiro = Carteiro()
    monkeypatch.setattr(graph, "montar_carteiro", lambda settings: carteiro)
    monkeypatch.setattr(graph, "situacao_do_envio", lambda settings: "ligado")
    return carteiro


def _token_do_link(email: dict) -> str:
    achado = re.search(r"/redefinir-senha#t=([A-Za-z0-9_-]+)", email["html"])
    assert achado, email["html"]
    return achado.group(1)


def _codigo(carteiro: Carteiro) -> str:
    return re.match(r"(\d{6}) é o seu código", carteiro.enviados[-1]["assunto"]).group(1)


def test_convite_codigo_navegador_confiavel_esqueci_e_trocar(cliente, sessao, monkeypatch) -> None:
    carteiro = _ligar_email(monkeypatch)
    papel = sessao.execute(text("SELECT id FROM roles WHERE slug = 'viewer'")).scalar_one()
    email = f"pessoa{uuid.uuid4().hex[:6]}@biason-teste.com.br"

    # Criar sem senha: vai o convite (48 h) com o link no fragmento #, nunca na URL do servidor.
    criado = cliente.post("/api/v1/users", json={"name": "Pessoa Teste", "email": email, "role_id": papel})
    assert criado.status_code == 201, criado.text
    assert criado.json()["aguardando_senha"] is True and criado.json()["convite_enviado"] is True
    convite = carteiro.enviados[-1]
    assert convite["para"] == [email] and convite["assunto"].startswith("Crie sua senha")
    token = _token_do_link(convite)
    uid = criado.json()["id"]
    assert next(u for u in cliente.get("/api/v1/users").json() if u["id"] == uid)["aguardando_senha"] is True

    with _sem_usuario_injetado(cliente):
        assert cliente.post("/api/v1/auth/login", json={"email": email, "password": "qualquer"}).status_code == 401  # sem senha ainda
        visto = cliente.post("/api/v1/auth/senha/ver", json={"token": token}).json()
        assert visto["tipo"] == "convite" and visto["email"] == email
        assert cliente.post("/api/v1/auth/senha", json={"token": token, "senha": "aaaaaaaaa"}).status_code == 422
        assert cliente.post("/api/v1/auth/senha", json={"token": token, "senha": "curta"}).status_code == 422
        assert cliente.post("/api/v1/auth/senha", json={"token": token, "senha": "Folha-2026-ok"}).status_code == 200
        assert cliente.post("/api/v1/auth/senha", json={"token": token, "senha": "Outra-2026-ok"}).status_code == 410  # uso único

        # Entrar: senha certa pede o código; e-mail mascarado.
        assert cliente.post("/api/v1/auth/login", json={"email": email, "password": "errada-123"}).status_code == 401
        passo = cliente.post("/api/v1/auth/login", json={"email": email.upper(), "password": "Folha-2026-ok"}).json()
        assert passo["precisa_codigo"] is True and "access_token" not in passo and passo["email"].startswith("pe")
        assert "•" in passo["email"] and passo["tentativas"] == 5
        codigo = _codigo(carteiro)
        errado = cliente.post("/api/v1/auth/codigo", json={"desafio": passo["desafio"], "codigo": "000000" if codigo != "000000" else "111111"})
        assert errado.status_code == 401 and errado.json()["restantes"] == 4
        entrou = cliente.post("/api/v1/auth/codigo", json={"desafio": passo["desafio"], "codigo": codigo, "confiar": True}).json()
        assert entrou["access_token"] and entrou["dispositivo"]
        assert cliente.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {entrou['access_token']}"}).json()["id"] == uid
        assert cliente.post("/api/v1/auth/codigo", json={"desafio": passo["desafio"], "codigo": codigo}).json()["voltar_ao_login"] is True

        # Navegador confiável: 30 dias só com a senha; o dispositivo de outra pessoa não vale.
        enviados = len(carteiro.enviados)
        direto = cliente.post("/api/v1/auth/login", json={"email": email, "password": "Folha-2026-ok", "dispositivo": entrou["dispositivo"]})
        assert "access_token" in direto.json() and len(carteiro.enviados) == enviados
        cab = {"Authorization": f"Bearer {direto.json()['access_token']}"}
        assert len(cliente.get("/api/v1/auth/navegadores", headers=cab).json()["navegadores"]) == 1

        # Reenviar: no máximo 3 por minuto.
        outro = cliente.post("/api/v1/auth/login", json={"email": email, "password": "Folha-2026-ok"}).json()
        respostas = [cliente.post("/api/v1/auth/codigo/reenviar", json={"desafio": outro["desafio"]}).status_code for _ in range(3)]
        assert respostas == [200, 200, 401]
        # 5 códigos errados: volta ao login.
        for _ in range(4):
            cliente.post("/api/v1/auth/codigo", json={"desafio": outro["desafio"], "codigo": "999999"})
        quinto = cliente.post("/api/v1/auth/codigo", json={"desafio": outro["desafio"], "codigo": "999998"}).json()
        assert quinto["voltar_ao_login"] is True

        # Esqueci a senha: a mesma resposta para quem existe e quem não existe.
        antes = len(carteiro.enviados)
        r1 = cliente.post("/api/v1/auth/esqueci", json={"email": "ninguem@biason-teste.com.br"})
        r2 = cliente.post("/api/v1/auth/esqueci", json={"email": email})
        assert r1.status_code == r2.status_code == 200 and r1.json() == r2.json()
        assert len(carteiro.enviados) == antes + 1 and carteiro.enviados[-1]["assunto"].startswith("Redefinir sua senha")
        redefinir = _token_do_link(carteiro.enviados[-1])
        assert cliente.post("/api/v1/auth/senha", json={"token": redefinir, "senha": "Nova-Senha-2026"}).status_code == 200
        assert carteiro.enviados[-1]["assunto"].startswith("Sua senha foi alterada")
        # Senha redefinida: o navegador confiável deixa de valer (pede o código de novo).
        de_novo = cliente.post("/api/v1/auth/login", json={"email": email, "password": "Nova-Senha-2026",
                                                           "dispositivo": entrou["dispositivo"]}).json()
        assert de_novo.get("precisa_codigo") is True
        sessao_nova = cliente.post("/api/v1/auth/codigo", json={"desafio": de_novo["desafio"], "codigo": _codigo(carteiro)}).json()
        cab = {"Authorization": f"Bearer {sessao_nova['access_token']}"}

        # Trocar no perfil: pede a atual.
        assert cliente.post("/api/v1/auth/trocar-senha", json={"atual": "errada", "nova": "Outra-Senha-2026"}, headers=cab).status_code == 422
        assert cliente.post("/api/v1/auth/trocar-senha", json={"atual": "Nova-Senha-2026", "nova": "Outra-Senha-2026"},
                            headers=cab).status_code == 200
        assert carteiro.enviados[-1]["assunto"].startswith("Sua senha foi alterada")

        # 10 senhas erradas seguidas travam por 15 min (nem a certa entra).
        for _ in range(10):
            cliente.post("/api/v1/auth/login", json={"email": email, "password": "errada-de-novo"})
        travada = cliente.post("/api/v1/auth/login", json={"email": email, "password": "Outra-Senha-2026"})
        assert travada.status_code == 401 and "travada" in travada.json()["erro"]

    # Nada que dá acesso fica guardado em texto: nem na auditoria, nem na tela E-mails.
    sessao.expire_all()
    tudo = sessao.execute(text("SELECT string_agg(coalesce(metadata::text,'') || coalesce(after::text,''), ' ') FROM audit_events")).scalar()
    guardado = sessao.execute(text("SELECT string_agg(coalesce(html,'') || coalesce(texto,'') || assunto, ' ') FROM emails "
                                   "WHERE para::text LIKE :e"), {"e": f"%{email}%"}).scalar()
    for segredo in (token, redefinir, entrou["dispositivo"], codigo, "Folha-2026-ok", "Nova-Senha-2026"):
        assert segredo not in tudo and segredo not in (guardado or "").replace(f"{codigo} é o seu código", "")
    assert "(mensagem de acesso: o conteúdo não fica guardado)" in guardado
    print("\nlogin: convite com link de uso único; código de 6 dígitos com 5 tentativas; navegador confiável 30 dias; "
          "reenviar limitado; esqueci a senha sem revelar a conta; senha nova corta o navegador confiável; trava em 10 erros")


def test_sem_envio_de_email_entra_so_com_a_senha(cliente, sessao) -> None:
    """Envio desligado (ou e-mail que não recebe): não há como mandar o código; entra e fica na auditoria."""
    from tests.db.test_auditoria_completa import _admin_com_senha
    from tests.db.test_times_e_maquinas import SENHA

    _, email = _admin_com_senha(sessao)
    with _sem_usuario_injetado(cliente):
        r = cliente.post("/api/v1/auth/login", json={"email": email, "password": SENHA})
        assert r.status_code == 200 and r.json()["access_token"] and "sem código" in r.json()["aviso"]
    via = sessao.execute(text("SELECT metadata->>'via' FROM audit_events WHERE action = 'login_succeeded' "
                              "ORDER BY occurred_at DESC LIMIT 1")).scalar()
    assert via == "sem_codigo"
