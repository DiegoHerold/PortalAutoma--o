"""Pendências com "Continuar processo" (13/11/2026).

Um item que termina em **atenção** (ex.: rubricas a parametrizar na Integração Contábil) vira
uma pendência ``aguardando``. Quem resolve o que faltava aperta **Continuar processo**:
- no e-mail (o botão abre o aviso no Portal, que pede login), ou
- no Portal (página Pendências).
Continuar põe na Fila uma execução nova só com esses itens, com os mesmos campos de entrada do
pedido original. A pendência fica ``continuada`` e nenhum outro caminho continua de novo: o botão
do e-mail, clicado outra vez, diz quando e quem já continuou. Se o item rodar de novo por outro
caminho (Executar, webhook), a pendência fica ``substituida``.

Quem recebe o e-mail: quem a automação disser (``a.email(..., continuar=[itens])`` põe o botão no
e-mail dela); se a execução terminar com pendências sem nenhum aviso, o Portal manda um e-mail
para quem pediu a execução. Continuar exige poder **executar** a automação.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

ESPERA_PELO_AVISO_DA_AUTOMACAO = timedelta(seconds=60)
JANELA_DE_SINCRONIA = timedelta(days=7)
MARCADOR_DO_BOTAO = "{{continuar}}"


class SemPendencia(LookupError):
    pass


class SemPermissao(PermissionError):
    pass


class JaResolvida(Exception):
    """Nada aguardando: alguém já continuou (ou o item rodou de novo). ``resolucao`` diz quando e quem."""

    def __init__(self, resolucao: dict[str, Any]) -> None:
        super().__init__("Este processo já foi continuado.")
        self.resolucao = resolucao


def botao(link: str, itens: int) -> str:
    """O bloco do botão, no padrão dos e-mails da Biason (só HTML com estilo inline)."""
    texto = "Continuar processo"
    return (
        "<table role='presentation' cellpadding='0' cellspacing='0' style='margin:24px 0'><tr><td>"
        "<p style='font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#1d2330;margin:0 0 12px'>"
        f"Depois de resolver o que falta, continue o processo{' destes itens' if itens > 1 else ''} pelo Portal:</p>"
        f"<a href='{html.escape(link, quote=True)}' style='display:inline-block;background:#102947;color:#ffffff;"
        "font-family:Segoe UI,Arial,sans-serif;font-size:15px;font-weight:600;text-decoration:none;padding:12px 22px;"
        f"border-radius:8px'>{texto}</a>"
        "<p style='font-family:Segoe UI,Arial,sans-serif;font-size:12px;color:#5d6677;margin:12px 0 0'>"
        "O botão vale uma vez e só enquanto o processo estiver aguardando. Pede login no Portal.</p>"
        "</td></tr></table>")


def injetar_botao(corpo: str | None, link: str, itens: int) -> str:
    bloco = botao(link, itens)
    if not corpo:
        return bloco
    if MARCADOR_DO_BOTAO in corpo:
        return corpo.replace(MARCADOR_DO_BOTAO, bloco)
    fim = corpo.lower().rfind("</body>")
    return corpo[:fim] + bloco + corpo[fim:] if fim >= 0 else corpo + bloco


class Pendencias:
    def __init__(self, repo: Any, pode: Callable[[Any, int, str], bool], enfileirar: Callable[..., dict[str, Any]],
                 pedir_email: Callable[..., Any] | None, link_base: str, auditoria: Any = None,
                 agora: Callable[[], datetime] | None = None) -> None:
        self.repo = repo
        self.pode = pode
        self.enfileirar = enfileirar  # (automation_id, execucao_original, itens: list[str], solicitante) -> {"execution_id", "itens"}
        self.pedir_email = pedir_email  # (para, assunto, html, contexto) -> registro
        self.link_base = link_base.rstrip("/")
        self.auditoria = auditoria
        self._agora = agora or (lambda: datetime.now(UTC))

    def link(self, aviso_id: str) -> str:
        return f"{self.link_base}/pendencias/{aviso_id}"

    # -- leitura ------------------------------------------------------------------------------------
    def sincronizar(self) -> int:
        return self.repo.sincronizar(self._agora() - JANELA_DE_SINCRONIA)

    def listar(self, ator: Any) -> list[dict[str, Any]]:
        self.sincronizar()
        grupos: dict[str, dict[str, Any]] = {}
        nomes: dict[int, str | None] = {}
        for p in self.repo.aguardando():
            if not self.pode(ator, p.automation_id, "ver_execucoes"):
                continue
            if p.automation_id not in nomes:
                nomes[p.automation_id] = self.repo.nome_da_automacao(p.automation_id)
            grupo = grupos.setdefault(p.execution_id, {
                "execucao_id": p.execution_id, "automacao": {"id": p.automation_id, "nome": nomes[p.automation_id]},
                "pode_continuar": self.pode(ator, p.automation_id, "executar"), "desde": p.criada_em, "itens": []})
            grupo["desde"] = min(grupo["desde"], p.criada_em)
            grupo["itens"].append(self._item(p))
        return sorted(grupos.values(), key=lambda g: g["desde"], reverse=True)

    def aviso(self, ator: Any, aviso_id: str) -> dict[str, Any]:
        self.sincronizar()
        aviso = self.repo.aviso(aviso_id)
        if aviso is None or not self.pode(ator, aviso.automation_id, "ver_execucoes"):
            raise SemPendencia("Pendência não encontrada (ou você não tem acesso a esta automação).")
        return self._situacao(ator, aviso.execution_id, aviso.automation_id, list(aviso.item_keys), aviso.criado_em)

    def da_execucao(self, ator: Any, execution_id: str) -> dict[str, Any]:
        self.sincronizar()
        execucao = self.repo.execucao(execution_id)
        if execucao is None or execucao["automation_id"] is None or not self.pode(ator, execucao["automation_id"], "ver_execucoes"):
            raise SemPendencia("Execução não encontrada.")
        chaves = [p.item_key for p in self.repo.da_execucao(execution_id)]
        return self._situacao(ator, execution_id, execucao["automation_id"], chaves, None)

    def _situacao(self, ator: Any, execution_id: str, automation_id: int, chaves: list[str], avisado_em: Any) -> dict[str, Any]:
        pendencias = self.repo.da_execucao(execution_id, chaves)
        aguardando = [p for p in pendencias if p.situacao == "aguardando"]
        return {"execucao_id": execution_id, "automacao": {"id": automation_id, "nome": self.repo.nome_da_automacao(automation_id)},
                "avisado_em": avisado_em, "itens": [self._item(p) for p in pendencias],
                "aguardando": len(aguardando), "pode_continuar": bool(aguardando) and self.pode(ator, automation_id, "executar"),
                "resolucao": None if aguardando else self._resolucao(pendencias)}

    def _item(self, p: Any) -> dict[str, Any]:
        quem = self.repo.usuario(p.resolvida_por)
        return {"id": p.id, "item": p.item_key, "rotulo": p.rotulo, "motivo": p.motivo, "situacao": p.situacao,
                "desde": p.criada_em, "resolvida_em": p.resolvida_em, "resolvida_via": p.resolvida_via,
                "resolvida_por": quem["name"] if quem else None, "continuacao_execucao_id": p.continuacao_execution_id}

    def _resolucao(self, pendencias: list[Any]) -> dict[str, Any] | None:
        resolvidas = [p for p in pendencias if p.resolvida_em is not None]
        if not resolvidas:
            return None
        ultima = max(resolvidas, key=lambda p: p.resolvida_em)
        return {k: v for k, v in self._item(ultima).items() if k in ("situacao", "resolvida_em", "resolvida_via", "resolvida_por",
                                                                      "continuacao_execucao_id")}

    # -- continuar ------------------------------------------------------------------------------------
    def continuar(self, ator: Any, *, aviso_id: str | None = None, execution_id: str | None = None,
                  itens: list[str] | None = None, via: str = "portal") -> dict[str, Any]:
        self.sincronizar()
        if aviso_id is not None:
            aviso = self.repo.aviso(aviso_id)
            if aviso is None:
                raise SemPendencia("Pendência não encontrada.")
            execution_id, automation_id, chaves = aviso.execution_id, aviso.automation_id, list(aviso.item_keys)
        else:
            execucao = self.repo.execucao(execution_id or "")
            if execucao is None or execucao["automation_id"] is None:
                raise SemPendencia("Execução não encontrada.")
            automation_id, chaves = execucao["automation_id"], itens
        if not self.pode(ator, automation_id, "executar"):
            raise SemPermissao("Para continuar, você precisa poder executar esta automação.")
        travadas = self.repo.da_execucao(execution_id, chaves, travar=True)  # duas pessoas ao mesmo tempo: só uma continua
        aguardando = [p for p in travadas if p.situacao == "aguardando"]
        if not aguardando:
            raise JaResolvida(self._resolucao(travadas) or {})
        agora = self._agora()
        quem = str(getattr(ator, "id", "") or "") or None
        self.repo.resolver(aguardando, situacao="continuada", por=quem, via="email" if via == "email" else "portal", agora=agora)
        resultado = self.enfileirar(automation_id, execution_id, [p.item_key for p in aguardando], quem or "desconhecido")
        self.repo.ligar_continuacao(aguardando, resultado["execution_id"])
        if self.auditoria is not None:
            from uuid import uuid4

            from modules.governance.domain.audit import AuditEvent

            self.auditoria.append(AuditEvent(
                id=f"aud_{uuid4().hex}", actor_type="user", actor_id=quem, action="pendencia.continuada",
                resource_type="execution", resource_id=execution_id,
                after={"itens": [p.item_key for p in aguardando], "via": via, "nova_execucao": resultado["execution_id"]},
                occurred_at=agora))
        return {"execucao_id": resultado["execution_id"], "itens": [p.item_key for p in aguardando]}

    # -- avisos -------------------------------------------------------------------------------------
    def preparar_aviso_da_automacao(self, execution_id: str, automation_id: int, itens: list[str],
                                    destinatarios: list[str]) -> Any:
        """A automação vai mandar o e-mail dela com o botão: as pendências existem já (mesmo que o
        evento de atenção ainda esteja a caminho) e o aviso guarda para quem foi."""
        chaves = [str(i)[:120] for i in itens if str(i).strip()][:500]
        if not chaves:
            return None
        self.repo.garantir(execution_id, automation_id, chaves, self._agora())
        return self.repo.criar_aviso(execution_id=execution_id, automation_id=automation_id, item_keys=chaves,
                                     destinatarios=destinatarios, origem="automacao", agora=self._agora())

    def avisar_por_padrao(self) -> dict[str, int]:
        """Execuções que terminaram com pendências e sem aviso da automação: e-mail para quem pediu."""
        self.sincronizar()
        contagem = {"avisados": 0, "sem_destinatario": 0}
        if self.pedir_email is None:
            return contagem
        limite = self._agora() - ESPERA_PELO_AVISO_DA_AUTOMACAO
        for execution_id in self.repo.execucoes_para_avisar(self._agora() - JANELA_DE_SINCRONIA):
            pendencias = [p for p in self.repo.da_execucao(execution_id) if p.situacao == "aguardando"]
            if not pendencias or max(p.criada_em for p in pendencias) > limite:
                continue  # a automação ainda pode mandar o e-mail dela
            execucao = self.repo.execucao(execution_id) or {}
            pessoa = self.repo.usuario(execucao.get("requested_by"))
            automation_id = pendencias[0].automation_id
            destino = [pessoa["email"]] if pessoa and pessoa.get("is_active") and "@" in str(pessoa.get("email") or "") else []
            aviso = self.repo.criar_aviso(execution_id=execution_id, automation_id=automation_id,
                                          item_keys=[p.item_key for p in pendencias], destinatarios=destino, origem="portal",
                                          agora=self._agora())
            if not destino:
                contagem["sem_destinatario"] += 1  # fica na página Pendências do Portal
                continue
            nome = self.repo.nome_da_automacao(automation_id) or "Automação"
            registro = self.pedir_email(destino, f"{nome}: {len(pendencias)} item(ns) aguardando você",
                                        self._html_padrao(nome, pendencias, self.link(aviso.id)), execution_id, automation_id)
            if registro is not None:
                self.repo.ligar_email(aviso, registro.id)
            contagem["avisados"] += 1
        return contagem

    @staticmethod
    def _html_padrao(nome: str, pendencias: list[Any], link: str) -> str:
        linhas = "".join(
            f"<tr><td style='padding:8px 10px;border-top:1px solid #e3e7ef;font:13px Segoe UI,Arial,sans-serif;color:#1d2330'>"
            f"<b>{html.escape(p.rotulo or p.item_key)}</b></td>"
            f"<td style='padding:8px 10px;border-top:1px solid #e3e7ef;font:13px Segoe UI,Arial,sans-serif;color:#5d6677'>"
            f"{html.escape(p.motivo or 'precisa de uma pessoa')}</td></tr>" for p in pendencias)
        return (
            "<div style='max-width:640px;font-family:Segoe UI,Arial,sans-serif;color:#1d2330'>"
            "<p style='font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#5d6677;margin:0 0 6px'>Portal de Automações · Biason</p>"
            f"<h2 style='font-size:20px;margin:0 0 12px'>{html.escape(nome)} precisa de você</h2>"
            "<p style='font-size:14px;margin:0 0 12px'>Estes itens pararam esperando uma pessoa:</p>"
            f"<table role='presentation' cellpadding='0' cellspacing='0' style='border-collapse:collapse;width:100%'>{linhas}</table>"
            f"{botao(link, len(pendencias))}"
            "<p style='font-size:12px;color:#5d6677'>Se não foi você que pediu esta execução, ignore este e-mail.</p></div>")

    def substituir(self, automation_id: int, itens: list[str], nova_execucao: str, por: str | None) -> int:
        return self.repo.substituir(automation_id, itens, nova_execucao, por, self._agora())
