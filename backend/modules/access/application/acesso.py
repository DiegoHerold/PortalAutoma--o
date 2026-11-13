"""Login com código por e-mail, navegador confiável, esqueci a senha, convite e trocar a senha
(13/11/2026), no modelo do Biason Comunica.

Entrar:
1. E-mail e senha. 10 senhas erradas seguidas travam a conta por 15 minutos.
2. Navegador confiável (marcado há menos de 30 dias, para esta pessoa): entra direto.
3. Senão, um código de 6 dígitos vai por e-mail (vale 10 minutos, 5 tentativas; reenviar no
   máximo 3 por minuto). O passo entre a senha e o código é um ``desafio`` de 15 minutos.
   Marcando "Confiar neste navegador", os próximos 30 dias pedem só a senha.
Sem envio de e-mail ligado no Portal, ou com e-mail que não recebe (``.local``, ``.invalid``), não
há como mandar o código: entra só com a senha (fica na auditoria com o motivo).

Senha: link de uso único por e-mail, ``{frontend}/redefinir-senha#t=...`` (o token vai no
fragmento ``#``, que o navegador não manda ao servidor nem a logs): esqueci a senha (1 h) e
convite ao criar o usuário (48 h). Definir a senha pelo link ou trocar no perfil (pede a atual)
corta os navegadores confiáveis e os links pendentes. Pedir o link sempre responde igual, exista
ou não a conta. Regras: 8 a 128 caracteres, não um caractere repetido, não conter o nome do e-mail.

Tudo o que dá acesso fica guardado só como HMAC-SHA256 com a chave do Portal.
"""

from __future__ import annotations

import hashlib
import hmac
import html
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from uuid import uuid4

from modules.access.domain import AuthenticationFailed
from modules.governance.domain.audit import AuditEvent

DESAFIO = timedelta(minutes=15)
CODIGO = timedelta(minutes=10)
TENTATIVAS_DO_CODIGO = 5
REENVIOS_POR_MINUTO = 3
DISPOSITIVO = timedelta(days=30)
REDEFINIR = timedelta(hours=1)
CONVITE = timedelta(hours=48)
FALHAS_PARA_TRAVAR = 10
TRAVA = timedelta(minutes=15)
LINKS_POR_15_MIN = 3
DOMINIOS_QUE_NAO_RECEBEM = (".local", ".invalid", ".test", ".example", ".localhost")
SENHA_INUTILIZAVEL = "!"


class CodigoInvalido(Exception):
    def __init__(self, mensagem: str, restantes: int | None = None, voltar_ao_login: bool = False) -> None:
        super().__init__(mensagem)
        self.restantes = restantes
        self.voltar_ao_login = voltar_ao_login


class LinkInvalido(Exception):
    pass


class SenhaFraca(ValueError):
    pass


def recebe_email(email: str | None) -> bool:
    texto = str(email or "").strip().lower()
    return "@" in texto and not texto.endswith(DOMINIOS_QUE_NAO_RECEBEM)


def mascarar_email(email: str) -> str:
    local, _, dominio = email.partition("@")
    visivel = local[:2] if len(local) > 3 else local[:1]
    return f"{visivel}{'•' * max(len(local) - len(visivel), 3)}@{dominio}"


def conferir_senha(senha: str, email: str) -> None:
    if not isinstance(senha, str) or not 8 <= len(senha) <= 128:
        raise SenhaFraca("A senha precisa ter de 8 a 128 caracteres.")
    if len(set(senha)) == 1:
        raise SenhaFraca("A senha não pode ser um caractere repetido.")
    nome = email.split("@", 1)[0].lower()
    if len(nome) >= 4 and nome in senha.lower():
        raise SenhaFraca("A senha não pode conter o seu nome de e-mail.")


def senha_definida(user: Any) -> bool:
    return bool(user.password_hash) and not str(user.password_hash).startswith(SENHA_INUTILIZAVEL)


class Acesso:
    def __init__(self, repo: Any, senhas: Any, jwt: Any, auditoria: Any, chave: str, frontend_url: str,
                 enviar: Callable[[str, str, str, str], bool] | None, agora: Callable[[], datetime] | None = None) -> None:
        self.repo = repo
        self.senhas = senhas
        self.jwt = jwt
        self.auditoria = auditoria
        self._chave = chave.encode("utf-8")
        self.frontend_url = frontend_url.rstrip("/")
        self.enviar = enviar  # (para, assunto, html, tipo) -> enviou? ; None: envio de e-mail desligado
        self._agora = agora or (lambda: datetime.now(UTC))

    def _hash(self, tipo: str, valor: str) -> str:
        return hmac.new(self._chave, f"{tipo}:{valor}".encode("utf-8"), hashlib.sha256).hexdigest()

    # -- entrar ---------------------------------------------------------------------------------
    def entrar(self, email: str, senha: str, dispositivo: str | None = None, ip: str | None = None,
               user_agent: str | None = None) -> dict[str, Any]:
        agora = self._agora()
        normal = str(email or "").strip().lower()
        user = self.repo.usuario_por_email(normal)
        if user is not None and user.bloqueado_ate is not None and user.bloqueado_ate > agora:
            minutos = max(1, int((user.bloqueado_ate - agora).total_seconds() // 60) + 1)
            self._auditar("login_failed", user.id, ip, user_agent, {"reason": "bloqueado", "email": normal})
            raise AuthenticationFailed(f"Conta travada por excesso de tentativas. Tente de novo em {minutos} min ou use Esqueci a senha.")
        valida = False
        if user is not None and user.is_active and senha_definida(user) and not self.repo.e_tecnico(user.id):
            try:
                valida = self.senhas.verify(senha, user.password_hash)
            except ValueError:
                valida = False
        elif user is None:
            self.senhas.hash(senha or "x")  # o mesmo tempo para conta inexistente
        if not valida:
            if user is not None:
                user.falhas_login = (user.falhas_login or 0) + 1
                if user.falhas_login >= FALHAS_PARA_TRAVAR:
                    user.bloqueado_ate, user.falhas_login = agora + TRAVA, 0
                    self._auditar("conta_travada", user.id, ip, user_agent, {"minutos": int(TRAVA.total_seconds() // 60)})
                self.repo.salvar()
            self._auditar("login_failed", user.id if user else None, ip, user_agent,
                          {"reason": "invalid_password" if user else "invalid_user", "email": normal})
            raise AuthenticationFailed("E-mail ou senha não conferem.")
        user.falhas_login, user.bloqueado_ate = 0, None
        self.repo.salvar()
        if dispositivo and self._dispositivo_valido(user.id, dispositivo, agora):
            return self._sessao(user, ip, user_agent, {"via": "navegador_confiavel"})
        if self.enviar is None or not recebe_email(user.email):
            motivo = "envio de e-mail desligado" if self.enviar is None else "o e-mail da conta não recebe mensagens"
            return self._sessao(user, ip, user_agent, {"via": "sem_codigo", "motivo": motivo}, aviso=f"Entrou sem código: {motivo}.")
        desafio = secrets.token_urlsafe(32)
        registro = self.repo.criar(user_id=user.id, tipo="desafio", hash=self._hash("desafio", desafio), expira_em=agora + DESAFIO,
                                   agora=agora, ip=ip)
        self._novo_codigo(user, registro.id, agora)
        return {"precisa_codigo": True, "desafio": desafio, "email": mascarar_email(user.email),
                "codigo_vale_ate": agora + CODIGO, "tentativas": TENTATIVAS_DO_CODIGO}

    def _novo_codigo(self, user: Any, desafio_id: str, agora: datetime) -> None:
        """Manda o código. Sem conseguir mandar, não adianta esperar por ele: levanta com o motivo."""
        self.repo.invalidar(user.id, ("codigo",), agora)  # um código só vale de cada vez
        codigo = f"{secrets.randbelow(1_000_000):06d}"
        self.repo.criar(user_id=user.id, tipo="codigo", hash=self._hash("codigo", f"{user.id}:{desafio_id}:{codigo}"),
                        expira_em=agora + CODIGO, agora=agora, dados={"desafio": desafio_id})
        enviou = self._enviar(user.email, f"{codigo} é o seu código de acesso · Portal de Automações",
                              _email(f"Seu código de acesso é <b style='font-size:28px;letter-spacing:6px'>{codigo}</b>",
                                     "Ele vale 10 minutos. Se não foi você que tentou entrar, troque a sua senha.", None), "login")
        if not enviou:
            raise AuthenticationFailed("Não foi possível mandar o código por e-mail agora. Tente de novo em instantes.")

    def confirmar_codigo(self, desafio: str, codigo: str, confiar: bool = False, ip: str | None = None,
                         user_agent: str | None = None) -> dict[str, Any]:
        agora = self._agora()
        registro = self.repo.por_hash("desafio", self._hash("desafio", str(desafio or "")), travar=True)
        if registro is None or registro.usado_em is not None or registro.expira_em <= agora:
            raise CodigoInvalido("O tempo para digitar o código acabou. Entre de novo.", voltar_ao_login=True)
        user = self.repo.usuario(registro.user_id)
        atual = self.repo.codigo_do_desafio(registro.id)
        if user is None or not user.is_active or atual is None or atual.expira_em <= agora:
            raise CodigoInvalido("O código venceu. Peça outro ou entre de novo.", restantes=0)
        texto = re.sub(r"\D", "", str(codigo or ""))
        if not hmac.compare_digest(atual.hash, self._hash("codigo", f"{user.id}:{registro.id}:{texto}")):
            atual.tentativas += 1
            restantes = TENTATIVAS_DO_CODIGO - atual.tentativas
            if restantes <= 0:
                self.repo.usar(atual, agora)
                self.repo.usar(registro, agora)
                self._auditar("login_failed", user.id, ip, user_agent, {"reason": "codigo_tentativas"})
                raise CodigoInvalido("As tentativas acabaram. Entre de novo.", restantes=0, voltar_ao_login=True)
            self.repo.salvar()
            raise CodigoInvalido(f"Código errado. Resta{'m' if restantes > 1 else ''} {restantes} tentativa{'s' if restantes > 1 else ''}.",
                                 restantes=restantes)
        self.repo.usar(atual, agora)
        self.repo.usar(registro, agora)
        resposta = self._sessao(user, ip, user_agent, {"via": "codigo", "confiar": bool(confiar)})
        if confiar:
            dispositivo = secrets.token_urlsafe(32)
            self.repo.criar(user_id=user.id, tipo="dispositivo", hash=self._hash("dispositivo", dispositivo),
                            expira_em=agora + DISPOSITIVO, agora=agora, ip=ip, dados={"navegador": (user_agent or "")[:200]})
            resposta["dispositivo"] = dispositivo
            resposta["dispositivo_vale_ate"] = agora + DISPOSITIVO
        return resposta

    def reenviar_codigo(self, desafio: str) -> dict[str, Any]:
        agora = self._agora()
        registro = self.repo.por_hash("desafio", self._hash("desafio", str(desafio or "")), travar=True)
        if registro is None or registro.usado_em is not None or registro.expira_em <= agora:
            raise CodigoInvalido("O tempo para digitar o código acabou. Entre de novo.", voltar_ao_login=True)
        if self.repo.codigos_do_desafio_desde(registro.id, agora - timedelta(minutes=1)) >= REENVIOS_POR_MINUTO:
            raise CodigoInvalido("Espere um minuto para pedir outro código.")
        user = self.repo.usuario(registro.user_id)
        self._novo_codigo(user, registro.id, agora)
        return {"email": mascarar_email(user.email), "codigo_vale_ate": agora + CODIGO, "tentativas": TENTATIVAS_DO_CODIGO}

    def _dispositivo_valido(self, user_id: int, dispositivo: str, agora: datetime) -> bool:
        registro = self.repo.por_hash("dispositivo", self._hash("dispositivo", dispositivo))
        return registro is not None and registro.user_id == user_id and registro.usado_em is None and registro.expira_em > agora

    def _sessao(self, user: Any, ip: str | None, user_agent: str | None, detalhes: dict[str, Any], aviso: str | None = None) -> dict[str, Any]:
        user.last_login_at = self._agora()
        self.repo.salvar()
        self._auditar("login_succeeded", user.id, ip, user_agent, {"email": user.email, **detalhes})
        return {"access_token": self.jwt.create_access_token(str(user.id)), "token_type": "bearer", **({"aviso": aviso} if aviso else {})}

    # -- senha ------------------------------------------------------------------------------------
    def esqueci(self, email: str, ip: str | None = None) -> None:
        """Responde sempre igual (não revela se a conta existe)."""
        agora = self._agora()
        user = self.repo.usuario_por_email(str(email or "").strip().lower())
        if user is None or not user.is_active or self.repo.e_tecnico(user.id) or not recebe_email(user.email):
            return
        if self.repo.criados_desde(user.id, ("redefinir", "convite"), agora - timedelta(minutes=15)) >= LINKS_POR_15_MIN:
            return
        self._mandar_link(user, "redefinir" if senha_definida(user) else "convite", ip)

    def convidar(self, user_id: int, ip: str | None = None) -> bool:
        """Ao criar a pessoa (ou "mandar o link de novo"): link para criar a senha, 48 h."""
        user = self.repo.usuario(user_id)
        if user is None or not recebe_email(user.email) or self.enviar is None:
            return False
        return self._mandar_link(user, "convite", ip)

    def _mandar_link(self, user: Any, tipo: str, ip: str | None) -> bool:
        agora = self._agora()
        self.repo.invalidar(user.id, ("redefinir", "convite"), agora)  # só o link mais novo vale
        token = secrets.token_urlsafe(32)
        self.repo.criar(user_id=user.id, tipo=tipo, hash=self._hash(tipo, token), agora=agora, ip=ip,
                        expira_em=agora + (CONVITE if tipo == "convite" else REDEFINIR))
        link = f"{self.frontend_url}/redefinir-senha#t={token}"
        if tipo == "convite":
            enviou = self._enviar(user.email, "Crie sua senha · Portal de Automações", _email(
                f"Olá, {html.escape(user.name)}. Você ganhou acesso ao <b>Portal de Automações</b> da Biason.",
                "Crie a sua senha pelo botão abaixo. O link vale 48 horas e só pode ser usado uma vez.", ("Criar minha senha", link)),
                "convite")
        else:
            enviou = self._enviar(user.email, "Redefinir sua senha · Portal de Automações", _email(
                "Recebemos um pedido para redefinir a sua senha do Portal de Automações.",
                "O link vale 1 hora e só pode ser usado uma vez. Se não foi você, ignore este e-mail: a senha continua a mesma.",
                ("Criar nova senha", link)), "redefinir")
        self._auditar("senha.link_enviado", user.id, ip, None, {"tipo": tipo, "enviado": enviou})
        return enviou

    def ver_link(self, token: str) -> dict[str, Any]:
        registro, user = self._link(token)
        return {"tipo": registro.tipo, "email": user.email, "nome": user.name, "vale_ate": registro.expira_em}

    def definir_senha(self, token: str, senha: str, ip: str | None = None) -> None:
        registro, user = self._link(token, travar=True)
        conferir_senha(senha, user.email)
        agora = self._agora()
        user.password_hash = self.senhas.hash(senha)
        user.falhas_login, user.bloqueado_ate = 0, None
        self.repo.usar(registro, agora)
        self.repo.invalidar(user.id, ("redefinir", "convite", "codigo", "desafio", "dispositivo"), agora)
        self._auditar("senha.criada" if registro.tipo == "convite" else "senha.redefinida", user.id, ip, None, {})
        if registro.tipo == "redefinir":
            self._enviar(user.email, "Sua senha foi alterada · Portal de Automações", _email(
                "A senha da sua conta no Portal de Automações foi alterada agora.",
                "Se não foi você, use Esqueci a senha no login e avise a TI.", None), "senha_alterada")

    def _link(self, token: str, travar: bool = False) -> tuple[Any, Any]:
        agora = self._agora()
        for tipo in ("redefinir", "convite"):
            registro = self.repo.por_hash(tipo, self._hash(tipo, str(token or "")), travar=travar)
            if registro is not None:
                break
        user = self.repo.usuario(registro.user_id) if registro is not None else None
        if registro is None or user is None or not user.is_active:
            raise LinkInvalido("Este link não vale. Peça outro em Esqueci a senha.")
        if registro.usado_em is not None:
            raise LinkInvalido("Este link já foi usado. Se precisar, peça outro em Esqueci a senha.")
        if registro.expira_em <= agora:
            raise LinkInvalido("Este link venceu. Peça outro em Esqueci a senha.")
        return registro, user

    def trocar_senha(self, user_id: int, atual: str, nova: str, ip: str | None = None) -> None:
        user = self.repo.usuario(user_id)
        if user is None or not senha_definida(user):
            raise SenhaFraca("Esta conta ainda não tem senha: use o link do e-mail.")
        try:
            confere = self.senhas.verify(atual, user.password_hash)
        except ValueError:
            confere = False
        if not confere:
            self._auditar("senha.troca_recusada", user.id, ip, None, {})
            raise SenhaFraca("A senha atual não confere.")
        if atual == nova:
            raise SenhaFraca("A senha nova precisa ser diferente da atual.")
        conferir_senha(nova, user.email)
        agora = self._agora()
        user.password_hash = self.senhas.hash(nova)
        self.repo.invalidar(user.id, ("redefinir", "convite", "dispositivo"), agora)
        self.repo.salvar()
        self._auditar("senha.trocada", user.id, ip, None, {})
        self._enviar(user.email, "Sua senha foi alterada · Portal de Automações", _email(
            "A senha da sua conta no Portal de Automações foi alterada agora, pelo seu perfil.",
            "Se não foi você, use Esqueci a senha no login e avise a TI.", None), "senha_alterada")

    def navegadores(self, user_id: int) -> list[dict[str, Any]]:
        return [{"id": d.id, "desde": d.criado_em, "vale_ate": d.expira_em, "navegador": (d.dados or {}).get("navegador")}
                for d in self.repo.dispositivos(user_id, self._agora())]

    def esquecer_navegadores(self, user_id: int) -> int:
        quantos = self.repo.invalidar(user_id, ("dispositivo",), self._agora())
        self._auditar("navegadores.esquecidos", user_id, None, None, {"quantos": quantos})
        return quantos

    # -- apoio -------------------------------------------------------------------------------------
    def _enviar(self, para: str, assunto: str, corpo: str, tipo: str) -> bool:
        if self.enviar is None or not recebe_email(para):
            return False
        try:
            return bool(self.enviar(para, assunto, corpo, tipo))
        except Exception:  # noqa: BLE001 - aviso por e-mail não pode quebrar a troca de senha
            return False

    def _auditar(self, acao: str, user_id: int | None, ip: str | None, user_agent: str | None, dados: dict[str, Any]) -> None:
        recurso = str(user_id) if user_id is not None else "desconhecido"
        self.auditoria.append(AuditEvent(id=f"aud_{uuid4().hex}", actor_type="user", actor_id=recurso if user_id else None,
                                         action=acao, resource_type="user", resource_id=recurso, metadata=dados, ip=ip,
                                         user_agent=user_agent, occurred_at=self._agora()))


def _email(titulo: str, texto: str, botao: tuple[str, str] | None) -> str:
    """E-mail de acesso no padrão Biason (estilos inline)."""
    acao = ""
    if botao:
        acao = (f"<p style='margin:24px 0'><a href='{html.escape(botao[1], quote=True)}' style='display:inline-block;background:#102947;"
                "color:#ffffff;font-family:Segoe UI,Arial,sans-serif;font-size:15px;font-weight:600;text-decoration:none;"
                f"padding:12px 22px;border-radius:8px'>{html.escape(botao[0])}</a></p>")
    return ("<div style='max-width:560px;font-family:Segoe UI,Arial,sans-serif;color:#1d2330'>"
            "<p style='font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#5d6677;margin:0 0 10px'>Portal de Automações · Biason</p>"
            f"<p style='font-size:16px;line-height:1.5;margin:0 0 12px'>{titulo}</p>"
            f"<p style='font-size:14px;line-height:1.5;color:#3b4456;margin:0'>{html.escape(texto)}</p>{acao}"
            "<p style='font-size:12px;color:#5d6677;margin-top:24px'>Mensagem automática. Se não foi você, ignore este e-mail.</p></div>")
