"""E-mail centralizado no Portal (13/11/2026).

Todo e-mail sai pelo Portal (Microsoft Graph, remetente do ``.env``):
- a automação pede com o token do job (``POST /direto/jobs/{job}/emails``, SDK ``a.email()``);
- o próprio Portal (notificações, pendências, login) também passa por aqui.
Se a automação mandar pela máquina (Outlook, SMTP), ela avisa o Portal
(``POST /direto/jobs/{job}/emails/registro``): o e-mail fica registrado como ``enviado_pela_maquina``.

Regras:
- Automação só manda para domínios permitidos (lista no Portal; o domínio do remetente sempre
  pode). Fora disso: ``recusado``, registrado com o motivo.
- Até 100 destinatários, assunto até 255, corpo até 512 KB, até 10 anexos e 2,5 MB no total
  (limite de uma mensagem do Graph), sem executáveis.
- Envio na hora; falha temporária (rede, 429, 5xx) fica ``na_fila`` e é tentada de novo em 1, 5,
  15, 30 e 60 min; depois de 6 tentativas ou erro definitivo, ``falhou``. Enviado: o conteúdo dos
  anexos é apagado (ficam nome e tamanho).
- Mesma ``chave_idempotencia`` na mesma execução: devolve o e-mail já pedido, sem mandar outro.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from uuid import uuid4

from modules.telemetry.application.use_cases.notificacoes import ErroDeEnvio

EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
DOMINIO = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$")
LIMITE_DE_DESTINATARIOS = 100
LIMITE_DO_ASSUNTO = 255
LIMITE_DO_CORPO = 512 * 1024
LIMITE_DE_ANEXOS = 10
LIMITE_DOS_ANEXOS = int(2.5 * 1024 * 1024)
EXTENSOES_PROIBIDAS = frozenset({"exe", "bat", "cmd", "com", "js", "jse", "vbs", "vbe", "ps1", "msi", "scr", "jar", "dll",
                                 "lnk", "hta", "cpl", "reg", "pif", "wsf"})
ESPERAS = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=15), timedelta(minutes=30), timedelta(minutes=60))
MAXIMO_DE_TENTATIVAS = 6
MEIOS_DA_MAQUINA = frozenset({"outlook", "smtp", "outro"})


class EmailInvalido(ValueError):
    pass


@dataclass(frozen=True)
class Contexto:
    """De onde vem o pedido. Na automação, tirado do token do job (nunca do corpo)."""

    origem: str  # automacao | portal | maquina
    tipo: str = "mensagem"
    automation_id: int | None = None
    execution_id: str | None = None
    job_id: str | None = None
    instancia_id: str | None = None
    criado_por: str | None = None


@dataclass
class Mensagem:
    para: list[str]
    assunto: str
    html: str | None = None
    texto: str | None = None
    cc: list[str] = field(default_factory=list)
    cco: list[str] = field(default_factory=list)
    anexos: list[tuple[str, str, bytes]] = field(default_factory=list)  # (nome, tipo, conteúdo)
    responder_para: str | None = None


def _lista(valor: Any, campo: str) -> list[str]:
    if valor in (None, "", []):
        return []
    if isinstance(valor, str):
        valor = [p for p in re.split(r"[;,]", valor)]
    if not isinstance(valor, list):
        raise EmailInvalido(f"{campo}: envie uma lista de e-mails.")
    saida: list[str] = []
    for bruto in valor:
        email = str(bruto or "").strip()
        if not email:
            continue
        if not EMAIL.match(email):
            raise EmailInvalido(f"{campo}: e-mail inválido: {email[:120]}")
        local, dominio = email.rsplit("@", 1)
        normal = f"{local}@{dominio.lower()}"
        if normal.lower() not in {e.lower() for e in saida}:
            saida.append(normal)
    return saida


def dominio_de(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower()


def normalizar_dominio(valor: Any) -> str:
    dominio = str(valor or "").strip().lower().lstrip("@")
    if not DOMINIO.match(dominio) or len(dominio) > 255:
        raise EmailInvalido(f"Domínio inválido: {dominio or '(vazio)'}")
    return dominio


def validar(dados: dict[str, Any], anexos: list[tuple[str, str, bytes]] | None = None) -> Mensagem:
    para = _lista(dados.get("para"), "para")
    cc = _lista(dados.get("cc"), "cc")
    cco = _lista(dados.get("cco"), "cco")
    if not para:
        raise EmailInvalido("Informe ao menos um destinatário em para.")
    if len(para) + len(cc) + len(cco) > LIMITE_DE_DESTINATARIOS:
        raise EmailInvalido(f"No máximo {LIMITE_DE_DESTINATARIOS} destinatários.")
    assunto = " ".join(str(dados.get("assunto") or "").split())
    if not assunto:
        raise EmailInvalido("Informe o assunto.")
    if len(assunto) > LIMITE_DO_ASSUNTO:
        raise EmailInvalido(f"Assunto com até {LIMITE_DO_ASSUNTO} caracteres.")
    html = dados.get("html")
    texto = dados.get("texto")
    if html is not None and not isinstance(html, str) or texto is not None and not isinstance(texto, str):
        raise EmailInvalido("html e texto precisam ser texto.")
    if not (html or texto):
        raise EmailInvalido("Informe o corpo em html ou texto.")
    if len((html or "").encode("utf-8")) > LIMITE_DO_CORPO or len((texto or "").encode("utf-8")) > LIMITE_DO_CORPO:
        raise EmailInvalido(f"Corpo com até {LIMITE_DO_CORPO // 1024} KB.")
    responder = _lista(dados.get("responder_para"), "responder_para")
    lista_de_anexos = list(anexos or [])
    if len(lista_de_anexos) > LIMITE_DE_ANEXOS:
        raise EmailInvalido(f"No máximo {LIMITE_DE_ANEXOS} anexos.")
    total = 0
    limpos: list[tuple[str, str, bytes]] = []
    for nome, tipo, conteudo in lista_de_anexos:
        nome = re.sub(r"[\\/:*?\"<>|\r\n]", "_", str(nome or "").split("/")[-1].split("\\")[-1]).strip()[:160]
        if not nome:
            raise EmailInvalido("Anexo sem nome.")
        extensao = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
        if extensao in EXTENSOES_PROIBIDAS:
            raise EmailInvalido(f"Anexo não permitido (.{extensao}): {nome}")
        total += len(conteudo)
        limpos.append((nome, str(tipo or "application/octet-stream")[:120], conteudo))
    if total > LIMITE_DOS_ANEXOS:
        raise EmailInvalido("Anexos acima de 2,5 MB no total: entregue o arquivo pela aba Arquivos e mande o link.")
    return Mensagem(para=para, cc=cc, cco=cco, assunto=assunto, html=html or None, texto=texto or None, anexos=limpos,
                    responder_para=responder[0] if responder else None)


class Correio:
    def __init__(self, repo: Any, carteiro: Any | None, remetente: str, agora: Callable[[], datetime] | None = None) -> None:
        self.repo = repo
        self.carteiro = carteiro
        self.remetente = remetente
        self._agora = agora or (lambda: datetime.now(UTC))

    # -- domínios ------------------------------------------------------------------------------
    def dominio_do_remetente(self) -> str | None:
        return dominio_de(self.remetente) if "@" in (self.remetente or "") else None

    def dominios(self) -> list[str]:
        return self.repo.dominios()

    def permitido(self, email: str) -> bool:
        alvo = dominio_de(email)
        permitidos = set(self.dominios()) | ({self.dominio_do_remetente()} - {None})
        return any(alvo == d or alvo.endswith("." + d) for d in permitidos)

    def adicionar_dominio(self, valor: Any, por: str | None) -> str:
        dominio = normalizar_dominio(valor)
        self.repo.adicionar_dominio(dominio, por, self._agora())
        return dominio

    def remover_dominio(self, valor: Any) -> None:
        self.repo.remover_dominio(normalizar_dominio(valor))

    # -- pedir -------------------------------------------------------------------------------------
    def pedir(self, contexto: Contexto, mensagem: Mensagem, chave_idempotencia: str | None = None) -> Any:
        """Registra e tenta mandar na hora. Devolve o registro (situação: enviado, na_fila, falhou ou recusado)."""
        chave = (chave_idempotencia or "").strip()[:120] or None
        if chave and contexto.execution_id:
            anterior = self.repo.por_chave(contexto.execution_id, chave)
            if anterior is not None:
                return anterior
        agora = self._agora()
        recusa = None
        if contexto.origem == "automacao":
            fora = [e for e in [*mensagem.para, *mensagem.cc, *mensagem.cco] if not self.permitido(e)]
            if fora:
                recusa = f"domínio não permitido: {', '.join(sorted({dominio_de(e) for e in fora}))[:400]}"
        registro = self.repo.criar(id=f"eml_{uuid4().hex[:24]}", contexto=contexto, mensagem=mensagem, meio="graph",
                                   situacao="recusado" if recusa else "na_fila", motivo=recusa, chave=chave, agora=agora,
                                   guardar_anexos=recusa is None)
        if recusa is None:
            self._tentar(registro, mensagem, agora)
        return registro

    def registrar_da_maquina(self, contexto: Contexto, dados: dict[str, Any]) -> Any:
        """A automação mandou pela máquina e avisa: só registra (não envia nada)."""
        meio = str(dados.get("meio") or "outro").strip().lower()
        if meio not in MEIOS_DA_MAQUINA:
            raise EmailInvalido(f"meio: {', '.join(sorted(MEIOS_DA_MAQUINA))}.")
        nomes = dados.get("anexos") or []
        if not isinstance(nomes, list) or len(nomes) > 50:
            raise EmailInvalido("anexos: lista com os nomes dos arquivos (até 50).")
        mensagem = validar({**dados, "html": None, "texto": dados.get("resumo") or "(enviado pela máquina)"})
        enviado = dados.get("enviado_em")
        try:
            quando = datetime.fromisoformat(str(enviado).replace("Z", "+00:00")) if enviado else self._agora()
        except ValueError as exc:
            raise EmailInvalido("enviado_em: data e hora ISO 8601.") from exc
        registro = self.repo.criar(id=f"eml_{uuid4().hex[:24]}", contexto=Contexto(**{**contexto.__dict__, "origem": "maquina"}),
                                   mensagem=Mensagem(para=mensagem.para, cc=mensagem.cc, cco=mensagem.cco, assunto=mensagem.assunto,
                                                     texto=mensagem.texto),
                                   meio=meio, situacao="enviado_pela_maquina", motivo=None, chave=None, agora=self._agora(),
                                   guardar_anexos=False, nomes_dos_anexos=[str(n)[:160] for n in nomes])
        self.repo.marcar(registro, situacao="enviado_pela_maquina", enviado_em=quando if quando.tzinfo else quando.replace(tzinfo=UTC))
        return registro

    # -- enviar ----------------------------------------------------------------------------------------
    def enviar_pendentes(self, limite: int = 50) -> dict[str, int]:
        agora = self._agora()
        contagem = {"enviados": 0, "falhas": 0, "na_fila": 0}
        if self.carteiro is None:
            return {**contagem, "desligado": 1}
        for registro in self.repo.na_fila(agora, limite):
            situacao = self._tentar(registro, self.repo.mensagem(registro), agora)
            contagem["enviados" if situacao == "enviado" else "falhas" if situacao == "falhou" else "na_fila"] += 1
        return contagem

    def reenviar(self, email_id: str) -> Any:
        registro = self.repo.email(email_id)
        if registro is None:
            raise LookupError("E-mail não encontrado.")
        if registro.situacao != "falhou":
            raise EmailInvalido("Só e-mail que falhou pode ser reenviado.")
        if not self.repo.tem_conteudo(registro):
            raise EmailInvalido("Os anexos já não estão guardados: peça o envio de novo pela automação.")
        self.repo.marcar(registro, situacao="na_fila", tentativas=0, proxima=self._agora(), motivo=None)
        self._tentar(registro, self.repo.mensagem(registro), self._agora())
        return registro

    def _tentar(self, registro: Any, mensagem: Mensagem, agora: datetime) -> str:
        if self.carteiro is None:
            self.repo.marcar(registro, situacao="na_fila", motivo="envio de e-mail desligado no Portal", proxima=agora + ESPERAS[0])
            return "na_fila"
        try:
            self.carteiro.enviar(mensagem.para, mensagem.assunto, mensagem.texto or "", html=mensagem.html, cc=mensagem.cc,
                                 cco=mensagem.cco, anexos=mensagem.anexos, responder_para=mensagem.responder_para)
        except ErroDeEnvio as exc:
            tentativas = registro.tentativas + 1
            if exc.temporario and tentativas < MAXIMO_DE_TENTATIVAS:
                self.repo.marcar(registro, situacao="na_fila", tentativas=tentativas, motivo=str(exc)[:500],
                                 proxima=agora + ESPERAS[min(tentativas - 1, len(ESPERAS) - 1)])
                return "na_fila"
            self.repo.marcar(registro, situacao="falhou", tentativas=tentativas, motivo=str(exc)[:500], proxima=None)
            return "falhou"
        self.repo.marcar(registro, situacao="enviado", tentativas=registro.tentativas + 1, motivo=None, proxima=None, enviado_em=agora)
        self.repo.apagar_conteudo_dos_anexos(registro)
        return "enviado"


class CarteiroQueRegistra:
    """Para as notificações da Fase 6, que têm a própria fila: cada envio também aparece em E-mails."""

    def __init__(self, carteiro: Any, repo: Any, agora: Callable[[], datetime] | None = None) -> None:
        self.carteiro = carteiro
        self.repo = repo
        self._agora = agora or (lambda: datetime.now(UTC))

    def enviar(self, para: Any, assunto: str, texto: str, **extra: Any) -> None:
        mensagem = Mensagem(para=[para] if isinstance(para, str) else list(para), assunto=assunto[:LIMITE_DO_ASSUNTO], texto=texto)
        agora = self._agora()
        registro = self.repo.criar(id=f"eml_{uuid4().hex[:24]}", contexto=Contexto(origem="portal", tipo="notificacao"),
                                   mensagem=mensagem, meio="graph", situacao="na_fila", motivo=None, chave=None, agora=agora,
                                   guardar_anexos=False)
        try:
            self.carteiro.enviar(para, assunto, texto, **extra)
        except ErroDeEnvio as exc:
            self.repo.marcar(registro, situacao="falhou", tentativas=1, motivo=str(exc)[:500], proxima=None)
            raise
        self.repo.marcar(registro, situacao="enviado", tentativas=1, motivo=None, proxima=None, enviado_em=agora)
