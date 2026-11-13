"""Segredos usados pelas automações (13/11/2026).

- Quem gerencia segredos liga um segredo a uma automação (aba Técnico ou tela Segredos).
- Durante a execução, a automação pede o segredo pela chave, com o token do job
  (``POST /direto/jobs/{job}/segredos``). O Portal só entrega se a tentativa está ativa, o
  segredo está ativo e ligado àquela automação, e a versão atual não venceu.
- Cada entrega e cada recusa ficam na auditoria (qual automação, qual execução, qual versão).
  O valor nunca vai para log, auditoria, URL ou mensagem de erro.
- O Portal mascara os valores dos segredos da automação nos eventos que ela envia, e o SDK
  também mascara antes de gravar na fila local.

Campos (13/11/2026): um segredo é um objeto com vários campos (Domínio: usuário, senha, banco),
cifrados juntos numa versão. Cada campo é **oculto** (nunca aparece no Portal, vira *** no log)
ou **visível** (aparece no Portal e não é mascarado). Segredos de antes têm um campo ``valor``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from modules.governance.domain.audit import AuditEvent

ATIVAS = frozenset({"accepted", "committed", "preparing", "running"})
SITUACOES = ("active", "disabled")
CHAVE_VALIDA = re.compile(r"^[a-z0-9][a-z0-9._-]{0,159}$")
LIMITE_POR_PEDIDO = 50
MINIMO_PARA_MASCARAR = 4  # valor curto demais apagaria palavras comuns do log
MASCARA = "***"
NAO_LIBERADO = "não existe ou não está liberado para esta automação"
CAMPO_VALIDO = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
LIMITE_DE_CAMPOS = 20
LIMITE_DO_VALOR = 8 * 1024
CAMPOS_DE_ANTES = [{"nome": "valor", "oculto": True}]


class SegredoNaoEncontrado(LookupError):
    pass


class SegredoInvalido(ValueError):
    pass


class Cifra(Protocol):
    key_id: str

    def encrypt(self, value: str) -> str: ...

    def decrypt(self, value: str) -> str: ...


class Auditoria(Protocol):
    def append(self, event: AuditEvent) -> Any: ...


@dataclass(frozen=True)
class QuemPede:
    """Quem pede o segredo: a instância direta do job (vem do token do job, nunca do corpo)."""

    task_execution_id: str
    execution_attempt_id: str
    instancia_id: str
    ip: str | None = None
    user_agent: str | None = None


def normalizar_chave(valor: Any) -> str:
    chave = str(valor or "").strip().lower().replace(" ", "_")
    if not CHAVE_VALIDA.match(chave):
        raise SegredoInvalido("A chave usa só letras minúsculas, números, ponto, hífen e sublinhado (até 160).")
    return chave


def campos_de(segredo: Any) -> list[dict[str, Any]]:
    """Nomes e se é oculto, na ordem cadastrada (segredo de antes: um campo ``valor`` oculto)."""
    lista = getattr(segredo, "campos", None)
    return [{"nome": str(c["nome"]), "oculto": bool(c.get("oculto", True))} for c in lista] if lista else list(CAMPOS_DE_ANTES)


def abrir(cifra: Cifra, versao: Any) -> dict[str, str]:
    """Os valores da versão. Versão de antes (texto puro cifrado) é o campo ``valor``."""
    texto = cifra.decrypt(versao.encrypted_value)
    try:
        dados = json.loads(texto)
    except ValueError:
        return {"valor": texto}
    if isinstance(dados, dict) and dados.get("v") == 2 and isinstance(dados.get("campos"), dict):
        return {str(k): str(v) for k, v in dados["campos"].items()}
    return {"valor": texto}


def fechar(cifra: Cifra, valores: dict[str, str]) -> str:
    return cifra.encrypt(json.dumps({"v": 2, "campos": valores}, ensure_ascii=False))


def validar_campos(brutos: Any, atuais: dict[str, str] | None = None) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """``[{"nome", "oculto", "valor"}]`` -> (campos, valores). Sem ``valor``, mantém o atual (se houver)."""
    if not isinstance(brutos, list) or not 1 <= len(brutos) <= LIMITE_DE_CAMPOS:
        raise SegredoInvalido(f"Envie de 1 a {LIMITE_DE_CAMPOS} campos.")
    campos: list[dict[str, Any]] = []
    valores: dict[str, str] = {}
    for bruto in brutos:
        if not isinstance(bruto, dict):
            raise SegredoInvalido("Cada campo precisa de nome, oculto e valor.")
        nome = str(bruto.get("nome") or "").strip().lower()
        if not CAMPO_VALIDO.match(nome):
            rotulo = nome or "(sem nome)"
            raise SegredoInvalido(f"Campo {rotulo}: use letras minúsculas, números e sublinhado, começando por letra.")
        if nome in valores:
            raise SegredoInvalido(f"Campo {nome} repetido.")
        valor = bruto.get("valor")
        if valor in (None, ""):
            if atuais is None or nome not in atuais:
                raise SegredoInvalido(f"Campo {nome}: informe o valor.")
            valor = atuais[nome]
        if not isinstance(valor, str) or len(valor) > LIMITE_DO_VALOR:
            raise SegredoInvalido(f"Campo {nome}: valor em texto, até {LIMITE_DO_VALOR} caracteres.")
        campos.append({"nome": nome, "oculto": bool(bruto.get("oculto", True))})
        valores[nome] = valor
    return campos, valores


def _validade(valor: Any, agora: datetime) -> datetime | None:
    if valor in (None, ""):
        return None
    try:
        quando = valor if isinstance(valor, datetime) else datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError as exc:
        raise SegredoInvalido("Validade em data e hora (ISO 8601).") from exc
    quando = quando if quando.tzinfo else quando.replace(tzinfo=UTC)
    if quando <= agora:
        raise SegredoInvalido("A validade precisa ser no futuro.")
    return quando


def mascarar(dado: Any, valores: list[str]) -> Any:
    """Troca cada valor de segredo por *** em qualquer texto do evento (recursivo)."""
    if not valores:
        return dado
    if isinstance(dado, str):
        for valor in valores:
            if valor in dado:
                dado = dado.replace(valor, MASCARA)
        return dado
    if isinstance(dado, dict):
        return {k: mascarar(v, valores) for k, v in dado.items()}
    if isinstance(dado, list):
        return [mascarar(v, valores) for v in dado]
    return dado


def _vencida(versao: Any, agora: datetime) -> bool:
    return versao is None or versao.revoked_at is not None or (versao.expires_at is not None and versao.expires_at <= agora)


class Segredos:
    def __init__(self, repo: Any, cifra: Cifra, auditoria: Auditoria, agora: Any = None) -> None:
        self.repo = repo
        self.cifra = cifra
        self.auditoria = auditoria
        self._agora = agora or (lambda: datetime.now(UTC))

    # -- entrega à automação ------------------------------------------------------------
    def entregar(self, quem: QuemPede, chaves: Any) -> dict[str, Any]:
        if not isinstance(chaves, list) or not 1 <= len(chaves) <= LIMITE_POR_PEDIDO:
            raise SegredoInvalido(f"Envie 'chaves' com 1 a {LIMITE_POR_PEDIDO} chaves.")
        pedidas: list[str] = []
        for c in chaves:
            if not isinstance(c, str):
                raise SegredoInvalido("Cada chave precisa ser um texto.")
            chave = normalizar_chave(c)
            if chave not in pedidas:
                pedidas.append(chave)
        agora = self._agora()
        contexto = self.repo.contexto_do_job(quem.task_execution_id, quem.execution_attempt_id)
        if contexto is None or contexto[2] not in ATIVAS:
            raise SegredoInvalido("Esta execução não está ativa: segredos só são entregues durante a execução.")
        automation_id, execucao_id, _ = contexto
        ligados = {g.secret_id for g in self.repo.ligacoes(automation_id=automation_id, agora=agora)}
        por_chave = self.repo.segredos_por_chave(pedidas)
        entregues: dict[str, dict[str, Any]] = {}
        negados: dict[str, str] = {}
        for chave in pedidas:
            segredo = por_chave.get(chave)
            if segredo is None or segredo.id not in ligados:
                negados[chave] = NAO_LIBERADO
            elif segredo.status != "active":
                negados[chave] = "está desativado no Portal"
            else:
                versao = self.repo.versao_atual(segredo)
                if _vencida(versao, agora):
                    negados[chave] = "a versão atual venceu ou foi revogada; troque o valor no Portal"
                else:
                    valores = abrir(self.cifra, versao)
                    entregues[chave] = {"campos": valores,
                                        "ocultos": [c["nome"] for c in campos_de(segredo) if c["oculto"] and c["nome"] in valores]}
                    self._auditar(quem, "segredo.entregue", segredo.id, agora, chave=chave, versao=versao.version,
                                  campos=sorted(valores), automacao=str(automation_id), execucao=execucao_id)
                    continue
            self._auditar(quem, "segredo.negado", segredo.id if segredo else f"chave:{chave}", agora, chave=chave,
                          motivo=negados[chave], automacao=str(automation_id), execucao=execucao_id)
        return {"segredos": entregues, "negados": negados}

    def valores_da_automacao(self, automation_id: int) -> list[str]:
        """Valores atuais dos campos ocultos dos segredos ligados (para mascarar o que a automação envia)."""
        agora = self._agora()
        valores: list[str] = []
        for ligacao in self.repo.ligacoes(automation_id=automation_id, agora=agora):
            segredo = self.repo.segredo(ligacao.secret_id)
            versao = self.repo.versao_atual(segredo) if segredo else None
            if versao is None:
                continue
            try:
                atuais = abrir(self.cifra, versao)
            except Exception:  # noqa: BLE001 - chave de cifra trocada: não mascara, mas não derruba o envio
                continue
            for campo in campos_de(segredo):
                valor = atuais.get(campo["nome"])
                if campo["oculto"] and valor and len(valor) >= MINIMO_PARA_MASCARAR:
                    valores.append(valor)
        return sorted(set(valores), key=len, reverse=True)  # o mais longo primeiro (um pode conter o outro)

    def _auditar(self, quem: QuemPede, acao: str, recurso: str, agora: datetime, **metadados: Any) -> None:
        self.auditoria.append(AuditEvent(
            id=f"aud_{uuid4().hex}", actor_type="direct_instance", actor_id=quem.instancia_id, action=acao,
            resource_type="secret", resource_id=recurso,
            metadata={**metadados, "job": quem.task_execution_id, "tentativa": quem.execution_attempt_id},
            ip=quem.ip, user_agent=quem.user_agent, occurred_at=agora))

    # -- gestão ------------------------------------------------------------------------------
    def painel(self) -> list[dict[str, Any]]:
        agora = self._agora()
        segredos = self.repo.todos()
        ligacoes = self.repo.ligacoes(agora=agora)
        nomes = self.repo.nomes_das_automacoes({int(g.grantee_id) for g in ligacoes if g.grantee_id.isdigit()})
        usos = self.repo.ultimos_usos([s.id for s in segredos])
        por_segredo: dict[str, list[dict[str, Any]]] = {}
        for g in ligacoes:
            if not g.grantee_id.isdigit() or int(g.grantee_id) not in nomes:
                continue  # automação apagada
            por_segredo.setdefault(g.secret_id, []).append({
                "id": int(g.grantee_id), "nome": nomes[int(g.grantee_id)], "ligado_em": g.created_at,
                "ultimo_uso": usos.get((g.secret_id, g.grantee_id))})
        saida = []
        for s in segredos:
            versao = self.repo.versao_atual(s)
            automacoes = sorted(por_segredo.get(s.id, []), key=lambda a: a["nome"].lower())
            ultimos = [a["ultimo_uso"] for a in automacoes if a["ultimo_uso"]]
            saida.append({
                "id": s.id, "chave": s.key, "nome": s.name, "descricao": s.description, "situacao": s.status,
                "campos": self._campos_para_mostrar(s, versao),
                "versao": versao.version if versao else None, "versao_criada_em": versao.created_at if versao else None,
                "expira_em": versao.expires_at if versao else None, "vencido": _vencida(versao, agora),
                "atualizado_em": s.updated_at, "automacoes": automacoes, "ultimo_uso": max(ultimos) if ultimos else None,
            })
        return saida

    def da_automacao(self, automation_id: int) -> list[dict[str, Any]]:
        if not self.repo.automacao_existe(automation_id):
            raise SegredoNaoEncontrado("Automação não encontrada.")
        agora = self._agora()
        ligacoes = self.repo.ligacoes(automation_id=automation_id, agora=agora)
        usos = self.repo.ultimos_usos([g.secret_id for g in ligacoes])
        saida = []
        for g in ligacoes:
            s = self.repo.segredo(g.secret_id)
            if s is None:
                continue
            saida.append({"id": s.id, "chave": s.key, "nome": s.name, "situacao": s.status,
                          "campos": [c["nome"] for c in campos_de(s)],
                          "vencido": _vencida(self.repo.versao_atual(s), agora), "ligado_em": g.created_at,
                          "ultimo_uso": usos.get((s.id, str(automation_id)))})
        return sorted(saida, key=lambda s: s["chave"])

    def _campos_para_mostrar(self, segredo: Any, versao: Any) -> list[dict[str, Any]]:
        """Nome, se é oculto e, só nos visíveis, o valor."""
        campos = campos_de(segredo)
        visiveis: dict[str, str] = {}
        if versao is not None and any(not c["oculto"] for c in campos):
            try:
                visiveis = abrir(self.cifra, versao)
            except Exception:  # noqa: BLE001 - chave de cifra trocada: mostra sem o valor
                visiveis = {}
        return [{**c, "valor": None if c["oculto"] else visiveis.get(c["nome"])} for c in campos]

    def criar(self, ator: Any, dados: dict[str, Any]) -> dict[str, Any]:
        chave = normalizar_chave(dados.get("chave"))
        nome = str(dados.get("nome") or "").strip()
        if not nome:
            raise SegredoInvalido("Dê um nome ao segredo.")
        if self.repo.chave_existe(chave):
            raise SegredoInvalido("Já existe um segredo com esta chave.")
        campos, valores = validar_campos(dados.get("campos"))
        agora = self._agora()
        segredo = self.repo.criar(chave=chave, nome=nome[:180], descricao=(str(dados.get("descricao") or "").strip() or None),
                                  campos=campos, cifrado=fechar(self.cifra, valores), chave_da_cifra=self.cifra.key_id,
                                  expira_em=_validade(dados.get("expira_em"), agora), criado_por=_id(ator), agora=agora)
        self._auditar_gestao(ator, "segredo.criado", segredo.id, depois={"chave": chave, "campos": campos})
        return {"id": segredo.id, "chave": chave}

    def mudar_campos(self, ator: Any, segredo_id: str, dados: dict[str, Any]) -> None:
        """Os campos passam a ser os enviados. Valor vazio mantém o atual; mudou algum valor (ou
        entrou/saiu campo, ou a validade): versão nova. Só ocultar/mostrar: muda sem versão nova."""
        segredo = self._segredo(segredo_id)
        versao = self.repo.versao_atual(segredo)
        atuais = abrir(self.cifra, versao) if versao is not None else {}
        campos, valores = validar_campos(dados.get("campos"), atuais)
        agora = self._agora()
        antes = campos_de(segredo)
        trocados = sorted(n for n in valores if atuais.get(n) != valores[n])
        saiu = sorted(set(atuais) - set(valores))
        expira = _validade(dados.get("expira_em"), agora) if "expira_em" in dados else (versao.expires_at if versao else None)
        nova = bool(trocados or saiu or "expira_em" in dados)
        if nova:
            self.repo.nova_versao(segredo, fechar(self.cifra, valores), self.cifra.key_id, expira, _id(ator), agora)
        if campos != antes:
            self.repo.mudar(segredo, {"campos": campos}, agora)
        if nova or campos != antes:
            self._auditar_gestao(ator, "segredo.campos_alterados", segredo.id, antes={"campos": antes},
                                 depois={"campos": campos, "valores_trocados": trocados, "removidos": saiu})

    def ligar(self, ator: Any, segredo_id: str, automation_id: int) -> None:
        segredo = self._segredo(segredo_id)
        if not self.repo.automacao_existe(automation_id):
            raise SegredoNaoEncontrado("Automação não encontrada.")
        if any(g.secret_id == segredo.id for g in self.repo.ligacoes(automation_id=automation_id)):
            return  # já ligado
        self.repo.ligar(segredo.id, automation_id, self._agora())
        self._auditar_gestao(ator, "segredo.ligado", segredo.id, automacao=str(automation_id), chave=segredo.key)

    def desligar(self, ator: Any, segredo_id: str, automation_id: int) -> None:
        segredo = self._segredo(segredo_id)
        ligacoes = [g for g in self.repo.ligacoes(automation_id=automation_id) if g.secret_id == segredo.id]
        for g in ligacoes:
            self.repo.desligar(g, self._agora())
        if ligacoes:
            self._auditar_gestao(ator, "segredo.desligado", segredo.id, automacao=str(automation_id), chave=segredo.key)

    def definir_automacoes(self, ator: Any, segredo_id: str, ids: Any) -> None:
        if not isinstance(ids, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
            raise SegredoInvalido("Envie 'automacoes' como uma lista de ids.")
        segredo = self._segredo(segredo_id)
        atuais = {int(g.grantee_id) for g in self.repo.ligacoes(segredo_id=segredo.id) if g.grantee_id.isdigit()}
        for automation_id in sorted(set(ids) - atuais):
            self.ligar(ator, segredo.id, automation_id)
        for automation_id in sorted(atuais - set(ids)):
            self.desligar(ator, segredo.id, automation_id)

    def mudar(self, ator: Any, segredo_id: str, dados: dict[str, Any]) -> None:
        segredo = self._segredo(segredo_id)
        mudanca: dict[str, Any] = {}
        if "nome" in dados:
            nome = str(dados["nome"] or "").strip()
            if not nome:
                raise SegredoInvalido("O nome não pode ficar vazio.")
            mudanca["name"] = nome[:180]
        if "descricao" in dados:
            mudanca["description"] = (str(dados["descricao"]).strip() or None) if dados["descricao"] is not None else None
        if "situacao" in dados:
            if dados["situacao"] not in SITUACOES:
                raise SegredoInvalido("Situação: active ou disabled.")
            mudanca["status"] = dados["situacao"]
        if not mudanca:
            raise SegredoInvalido("Nada para mudar.")
        antes = {"nome": segredo.name, "situacao": segredo.status}
        self.repo.mudar(segredo, mudanca, self._agora())
        self._auditar_gestao(ator, "segredo.alterado", segredo.id, antes=antes,
                             depois={"nome": segredo.name, "situacao": segredo.status})

    def versoes(self, segredo_id: str) -> list[dict[str, Any]]:
        segredo = self._segredo(segredo_id)
        return [{"versao": v.version, "criada_em": v.created_at, "criada_por": v.created_by, "expira_em": v.expires_at,
                 "revogada_em": v.revoked_at, "atual": v.id == segredo.current_version_id}
                for v in self.repo.versoes(segredo.id)]

    def trocar_valor_unico(self, ator: Any, segredo_id: str, valor: str, expira_em: Any = None) -> None:
        """Rota antiga ``/secrets/{id}/rotate``: só para segredo de um campo."""
        segredo = self._segredo(segredo_id)
        campos = campos_de(segredo)
        if len(campos) != 1:
            raise SegredoInvalido("Este segredo tem vários campos: troque os valores em PUT /segredos/{id}/campos.")
        dados: dict[str, Any] = {"campos": [{**campos[0], "valor": valor}]}
        if expira_em is not None:
            dados["expira_em"] = expira_em
        self.mudar_campos(ator, segredo_id, dados)

    def _segredo(self, segredo_id: str) -> Any:
        segredo = self.repo.segredo(segredo_id)
        if segredo is None:
            raise SegredoNaoEncontrado("Segredo não encontrado.")
        return segredo

    def _auditar_gestao(self, ator: Any, acao: str, recurso: str, *, antes: dict | None = None, depois: dict | None = None,
                        **metadados: Any) -> None:
        quem = getattr(ator, "id", None)
        self.auditoria.append(AuditEvent(
            id=f"aud_{uuid4().hex}", actor_type="user", actor_id=str(quem) if quem is not None else None, action=acao,
            resource_type="secret", resource_id=recurso, before=antes, after=depois, metadata=metadados,
            organization_id=getattr(ator, "organization_id", None), occurred_at=self._agora()))


def _id(ator: Any) -> str | None:
    valor = getattr(ator, "id", None)
    return str(valor) if valor is not None else None
