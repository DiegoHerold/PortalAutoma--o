"""Webhooks (13/11/2026): uma URL que só aciona UMA automação. Nada mais.

Diferente da conta de serviço (que usa a API do Portal com um papel), o webhook não lê nada e não
faz nada além de pedir uma execução daquela automação, com os campos de entrada e os itens
conferidos pelo formulário dela, igual ao botão Executar.

Chamada: ``POST /api/v1/webhooks/{id}`` com ``Authorization: Bearer wht_...`` e o corpo
``{"parametros": {...}, "itens": ["101", ...], "com_filiais": true}`` (tudo opcional conforme a
automação). Resposta ``202 {"execucao_id", "itens", "situacao": "na_fila"}``.

Segurança, na ordem em que é conferida:
1. Token só no cabeçalho ``Authorization: Bearer``; na URL ou no corpo é recusado (400).
2. Webhook inexistente ou token errado: a mesma resposta 401 (não revela quais webhooks existem).
   O Portal guarda só o SHA-256 do token; o token aparece uma única vez.
3. Webhook desligado: 403. IP fora da lista de IPs/redes permitidos (quando há lista): 403.
   O IP é o da conexão (o Portal não confia em X-Forwarded-For).
4. Mais chamadas no último minuto do que o limite do webhook: 429.
5. Corpo só JSON, até 64 KB; chaves desconhecidas: 422.
6. ``Idempotency-Key`` repetida em 24 h: devolve a mesma execução, sem criar outra.
7. Campos e itens conferidos pelo formulário da automação (422 com o motivo).
Toda chamada a um webhook existente (aceita, repetida ou recusada) fica no histórico dele.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from uuid import uuid4

from modules.governance.domain.audit import AuditEvent

PREFIXO_TOKEN = "wht_"
LIMITE_CORPO = 64 * 1024
LIMITE_PADRAO = 30
LIMITE_MAXIMO = 600
LIMITE_DE_REDES = 50
JANELA_IDEMPOTENCIA = timedelta(hours=24)
CHAVES_DO_CORPO = frozenset({"parametros", "itens", "com_filiais"})
CREDENCIAL_INVALIDA = "credencial inválida para este webhook"
PARAMETROS_COM_TOKEN = frozenset({"token", "secret", "access_token", "api_key", "chave"})


class WebhookInvalido(ValueError):
    """Erro de cadastro (422)."""


class WebhookNaoEncontrado(LookupError):
    pass


class SemPermissao(PermissionError):
    pass


@dataclass
class Recusa(Exception):
    """Chamada recusada: ``codigo`` HTTP, ``erro`` para quem chamou, ``detalhe`` opcional (campos)."""

    codigo: int
    erro: str
    detalhe: Any = None


@dataclass(frozen=True)
class Chamada:
    webhook_id: str
    token: str | None
    ip: str | None
    user_agent: str | None
    chave_idempotencia: str | None
    tipo_do_conteudo: str | None
    corpo: bytes
    token_na_url: bool = False


def hash_do_token(token: str) -> str:
    return "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def novo_token() -> tuple[str, str, str]:
    token = PREFIXO_TOKEN + secrets.token_urlsafe(32)
    return token, hash_do_token(token), token[-4:]


def validar_redes(brutas: Any) -> list[str]:
    if brutas in (None, ""):
        return []
    if isinstance(brutas, str):
        brutas = [p for p in brutas.replace(",", "\n").splitlines()]
    if not isinstance(brutas, list):
        raise WebhookInvalido("IPs permitidos: envie uma lista (ex.: 10.0.0.15, 10.0.8.0/24).")
    redes: list[str] = []
    for bruta in brutas:
        texto = str(bruta or "").strip()
        if not texto:
            continue
        try:
            rede = ipaddress.ip_network(texto, strict=False)
        except ValueError as exc:
            raise WebhookInvalido(f"IP ou rede inválida: {texto}") from exc
        if str(rede) not in redes:
            redes.append(str(rede))
    if len(redes) > LIMITE_DE_REDES:
        raise WebhookInvalido(f"No máximo {LIMITE_DE_REDES} IPs ou redes.")
    return redes


def ip_permitido(ip: str | None, redes: list[str]) -> bool:
    if not redes:
        return True
    try:
        endereco = ipaddress.ip_address(ip or "")
    except ValueError:
        return False
    return any(endereco in ipaddress.ip_network(r, strict=False) for r in redes)


def _texto(valor: Any, limite: int, obrigatorio: str | None = None) -> str | None:
    texto = str(valor or "").strip()
    if not texto:
        if obrigatorio:
            raise WebhookInvalido(obrigatorio)
        return None
    return texto[:limite]


def _limite(valor: Any) -> int:
    if valor in (None, ""):
        return LIMITE_PADRAO
    if not isinstance(valor, int) or isinstance(valor, bool) or not 1 <= valor <= LIMITE_MAXIMO:
        raise WebhookInvalido(f"Limite por minuto: de 1 a {LIMITE_MAXIMO}.")
    return valor


class Webhooks:
    def __init__(self, repo: Any, pode: Callable[[Any, int, str], bool], auditoria: Any, transacao: Any,
                 pedir: Callable[[int, dict[str, Any], str], dict[str, Any]], agora: Callable[[], datetime] | None = None) -> None:
        self.repo = repo
        self.pode = pode
        self.auditoria = auditoria
        self.transacao = transacao
        self.pedir = pedir
        self._agora = agora or (lambda: datetime.now(UTC))

    # -- gestão --------------------------------------------------------------------------------
    def listar(self, ator: Any, automation_id: int | None = None) -> list[dict[str, Any]]:
        lista = self.repo.todos(automation_id)
        return [self._dados(w) for w in lista if self.pode(ator, w.automation_id, "ver_execucoes")]

    def ver(self, ator: Any, webhook_id: str) -> dict[str, Any]:
        webhook = self._webhook(webhook_id)
        if not self.pode(ator, webhook.automation_id, "ver_execucoes"):
            raise WebhookNaoEncontrado("Webhook não encontrado.")
        return self._dados(webhook)

    def criar(self, ator: Any, dados: dict[str, Any]) -> dict[str, Any]:
        automation_id = dados.get("automation_id")
        if not isinstance(automation_id, int) or isinstance(automation_id, bool) or self.repo.nome_da_automacao(automation_id) is None:
            raise WebhookInvalido("Escolha a automação que o webhook vai acionar.")
        self._pode_executar(ator, automation_id)
        token, hash_, final = novo_token()
        agora = self._agora()
        webhook = self.repo.criar(id=f"whk_{secrets.token_hex(8)}", automation_id=automation_id,
                                  nome=_texto(dados.get("nome"), 180, "Dê um nome ao webhook (quem vai chamar)."),
                                  descricao=_texto(dados.get("descricao"), 2000), token_hash=hash_, token_final=final,
                                  ips=validar_redes(dados.get("ips_permitidos")), limite=_limite(dados.get("limite_por_minuto")),
                                  criado_por=_id(ator), agora=agora)
        self._auditar(ator, "webhook.criado", webhook.id, depois=self._resumo(webhook))
        self.transacao.commit()
        return {"webhook": self._dados(webhook), "token": token}

    def mudar(self, ator: Any, webhook_id: str, dados: dict[str, Any]) -> dict[str, Any]:
        webhook = self._webhook(webhook_id)
        self._pode_executar(ator, webhook.automation_id)
        antes = self._resumo(webhook)
        mudanca: dict[str, Any] = {}
        if "nome" in dados:
            mudanca["nome"] = _texto(dados["nome"], 180, "O nome não pode ficar vazio.")
        if "descricao" in dados:
            mudanca["descricao"] = _texto(dados["descricao"], 2000)
        if "ips_permitidos" in dados:
            mudanca["ips_permitidos"] = validar_redes(dados["ips_permitidos"])
        if "limite_por_minuto" in dados:
            mudanca["limite_por_minuto"] = _limite(dados["limite_por_minuto"])
        if "ativo" in dados:
            if not isinstance(dados["ativo"], bool):
                raise WebhookInvalido("ativo: true ou false.")
            if dados["ativo"] and not webhook.token_hash.startswith("sha256:"):
                raise WebhookInvalido("Gere um token antes de ligar o webhook.")
            mudanca["ativo"] = dados["ativo"]
        self.repo.mudar(webhook, mudanca, self._agora())
        depois = self._resumo(webhook)
        if antes != depois:
            self._auditar(ator, "webhook.alterado", webhook.id, antes=antes, depois=depois)
        self.transacao.commit()
        return self._dados(webhook)

    def gerar_token(self, ator: Any, webhook_id: str) -> dict[str, Any]:
        webhook = self._webhook(webhook_id)
        self._pode_executar(ator, webhook.automation_id)
        token, hash_, final = novo_token()
        self.repo.trocar_token(webhook, hash_, final, self._agora())
        self._auditar(ator, "webhook.token_gerado", webhook.id, depois={"token_final": final})
        self.transacao.commit()
        return {"webhook": self._dados(webhook), "token": token}

    def apagar(self, ator: Any, webhook_id: str) -> None:
        webhook = self._webhook(webhook_id)
        self._pode_executar(ator, webhook.automation_id)
        resumo = self._resumo(webhook)
        self.repo.apagar(webhook)
        self._auditar(ator, "webhook.apagado", webhook_id, antes=resumo)
        self.transacao.commit()

    def chamadas(self, ator: Any, webhook_id: str, limite: int = 50) -> list[dict[str, Any]]:
        webhook = self._webhook(webhook_id)
        if not self.pode(ator, webhook.automation_id, "ver_execucoes"):
            raise WebhookNaoEncontrado("Webhook não encontrado.")
        return [{"id": c.id, "recebida_em": c.recebida_em, "situacao": c.situacao, "motivo": c.motivo, "codigo_http": c.codigo_http,
                 "ip": c.ip, "execucao_id": c.execution_id, "itens": c.itens, "chave_idempotencia": c.chave_idempotencia}
                for c in self.repo.chamadas(webhook.id, limite)]

    # -- chamada pública -------------------------------------------------------------------------
    def acionar(self, chamada: Chamada) -> tuple[int, dict[str, Any]]:
        agora = self._agora()
        webhook = self.repo.webhook(chamada.webhook_id) if chamada.webhook_id.startswith("whk_") else None
        try:
            if webhook is None:
                raise Recusa(401, CREDENCIAL_INVALIDA)  # não registra: não há de quem
            if chamada.token_na_url:
                raise Recusa(400, "o token vai só no cabeçalho Authorization: Bearer, nunca na URL")
            if not chamada.token or not hmac.compare_digest(hash_do_token(chamada.token), webhook.token_hash):
                raise Recusa(401, CREDENCIAL_INVALIDA)
            if not webhook.ativo:
                raise Recusa(403, "webhook desligado no Portal")
            if not ip_permitido(chamada.ip, list(webhook.ips_permitidos or [])):
                raise Recusa(403, "origem não permitida para este webhook")
            if self.repo.chamadas_desde(webhook.id, agora - timedelta(minutes=1)) >= webhook.limite_por_minuto:
                raise Recusa(429, f"limite de {webhook.limite_por_minuto} chamadas por minuto")
            chave = (chamada.chave_idempotencia or "").strip()[:120] or None
            if chave:
                anterior = self.repo.aceita_com_chave(webhook.id, chave, agora - JANELA_IDEMPOTENCIA)
                if anterior is not None:
                    self._registrar(webhook, chamada, agora, "repetida", 200, "Idempotency-Key repetida", anterior.execution_id,
                                    anterior.itens)
                    self.transacao.commit()
                    return 200, {"execucao_id": anterior.execution_id, "situacao": "repetida",
                                 "mensagem": "esta chave de idempotência já foi aceita; nada novo foi criado"}
            corpo = self._corpo(chamada)
            pedido = {"parametros": corpo.get("parametros") or {}, "chaves": corpo.get("itens") or [],
                      "com_filiais": corpo.get("com_filiais", True)}
            resultado = self.pedir(webhook.automation_id, pedido, f"webhook:{webhook.id}")
        except Recusa as recusa:
            self.transacao.rollback()
            if webhook is not None:
                self._registrar(webhook, chamada, agora, "recusada", recusa.codigo, recusa.erro, None, None)
                self.transacao.commit()
            resposta: dict[str, Any] = {"erro": recusa.erro}
            if recusa.detalhe is not None:
                resposta["detalhe"] = recusa.detalhe
            return recusa.codigo, resposta
        itens = list(resultado.get("itens") or [])
        self._registrar(webhook, chamada, agora, "aceita", 202, None, resultado.get("execution_id"), len(itens))
        self.repo.marcar_uso(webhook, agora)
        self.transacao.commit()
        return 202, {"execucao_id": resultado.get("execution_id"), "itens": itens, "situacao": "na_fila"}

    def _corpo(self, chamada: Chamada) -> dict[str, Any]:
        if len(chamada.corpo) > LIMITE_CORPO:
            raise Recusa(413, f"corpo acima de {LIMITE_CORPO // 1024} KB")
        if not chamada.corpo.strip():
            return {}
        if not (chamada.tipo_do_conteudo or "").lower().startswith("application/json"):
            raise Recusa(415, "envie Content-Type: application/json")
        try:
            corpo = json.loads(chamada.corpo)
        except ValueError as exc:
            raise Recusa(400, "JSON inválido") from exc
        if not isinstance(corpo, dict):
            raise Recusa(422, "o corpo precisa ser um objeto JSON")
        if "token" in corpo or "secret_token" in corpo:
            raise Recusa(400, "o token vai só no cabeçalho Authorization: Bearer, nunca no corpo")
        sobrando = sorted(set(corpo) - CHAVES_DO_CORPO)
        if sobrando:
            raise Recusa(422, f"campos desconhecidos no corpo: {', '.join(sobrando)} (use parametros, itens e com_filiais)")
        itens = corpo.get("itens")
        if itens is not None and (not isinstance(itens, list) or not all(isinstance(i, (str, int)) and not isinstance(i, bool) for i in itens)):
            raise Recusa(422, "itens: uma lista de chaves (texto ou número)")
        if "com_filiais" in corpo and not isinstance(corpo["com_filiais"], bool):
            raise Recusa(422, "com_filiais: true ou false")
        return corpo

    def _registrar(self, webhook: Any, chamada: Chamada, agora: datetime, situacao: str, codigo: int, motivo: str | None,
                   execucao: str | None, itens: int | None) -> None:
        self.repo.registrar(id=f"whc_{uuid4().hex[:24]}", webhook_id=webhook.id, recebida_em=agora, situacao=situacao,
                            motivo=(motivo or None) and motivo[:300], codigo_http=codigo, ip=chamada.ip,
                            user_agent=(chamada.user_agent or "")[:300] or None,
                            chave_idempotencia=(chamada.chave_idempotencia or "").strip()[:120] or None,
                            execution_id=execucao, itens=itens)

    # -- apoio -------------------------------------------------------------------------------------
    def _webhook(self, webhook_id: str) -> Any:
        webhook = self.repo.webhook(webhook_id)
        if webhook is None:
            raise WebhookNaoEncontrado("Webhook não encontrado.")
        return webhook

    def _pode_executar(self, ator: Any, automation_id: int) -> None:
        if not self.pode(ator, automation_id, "executar"):
            raise SemPermissao("Para criar ou mudar um webhook, você precisa poder executar a automação.")

    def _dados(self, w: Any) -> dict[str, Any]:
        agora = self._agora()
        aceitas, recusadas = self.repo.contagem(w.id, agora - timedelta(hours=24))
        return {"id": w.id, "automacao": {"id": w.automation_id, "nome": self.repo.nome_da_automacao(w.automation_id)},
                "nome": w.nome, "descricao": w.descricao, "ativo": w.ativo,
                "tem_token": w.token_hash.startswith("sha256:"), "token_final": w.token_final, "token_criado_em": w.token_criado_em,
                "ips_permitidos": list(w.ips_permitidos or []), "limite_por_minuto": w.limite_por_minuto,
                "ultimo_uso_em": w.ultimo_uso_em, "criado_em": w.criado_em, "migrado": w.legado_trigger_id is not None,
                "chamadas_24h": {"aceitas": aceitas, "recusadas": recusadas}}

    @staticmethod
    def _resumo(w: Any) -> dict[str, Any]:
        return {"nome": w.nome, "automacao": w.automation_id, "ativo": w.ativo, "ips_permitidos": list(w.ips_permitidos or []),
                "limite_por_minuto": w.limite_por_minuto}

    def _auditar(self, ator: Any, acao: str, recurso: str, *, antes: dict | None = None, depois: dict | None = None) -> None:
        self.auditoria.append(AuditEvent(
            id=f"aud_{uuid4().hex}", actor_type="user", actor_id=_id(ator), action=acao, resource_type="webhook",
            resource_id=recurso, before=antes, after=depois, occurred_at=self._agora()))


def _id(ator: Any) -> str | None:
    valor = getattr(ator, "id", None)
    return str(valor) if valor is not None else None
