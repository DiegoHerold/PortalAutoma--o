"""Casos de uso das notificações (Fase 6): detectar ocorrências e enviar os e-mails.

Detectar é idempotente: a chave da ocorrência é única e o aviso é um por endereço. Toda
ocorrência é gravada, mesmo sem destinatário: assim quem liga um tipo depois não recebe
uma enxurrada do que já passou. O envio por e-mail só acontece se estiver ligado; sem
envio, os avisos ficam no portal.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from modules.telemetry.domain.notificacoes import (
    FILA_PARADA,
    JANELA_DE_DETECCAO,
    MAQUINA_OFFLINE,
    Ocorrencia,
    Pessoa,
    atencao,
    destinatarios,
    fila_parada,
    fim_de_execucao,
    maquina_offline,
)

# E-mail que não saiu em 6 h não sai mais: aviso velho confunde mais do que ajuda.
VALIDADE_DO_ENVIO = timedelta(hours=6)
TENTATIVAS_DE_ENVIO = 5


class ErroDeEnvio(RuntimeError):
    pass


def _agora() -> datetime:
    return datetime.now(UTC)


class DetectarOcorrencias:
    def __init__(self, leitor: Any, avisos: Any, ver_fila: Callable[[datetime], dict[str, Any]],
                 pode_ver: Callable[[Any, int], bool], transaction: Any, agora: Callable[[], datetime] = _agora) -> None:
        self.leitor = leitor
        self.avisos = avisos
        self.ver_fila = ver_fila
        self.pode_ver = pode_ver
        self.transaction = transaction
        self.agora = agora

    def ocorrencias(self, agora: datetime, pessoas: list[Pessoa]) -> list[Ocorrencia]:
        desde = agora - JANELA_DE_DETECCAO
        saida = [fim_de_execucao(t["execution_id"], t["situacao"], t["automation_id"], t["automacao"], t["quando"], t["falha"])
                 for t in self.leitor.terminadas(desde)]
        saida += [atencao(a["execution_id"], a["item"], a["motivo"], a["automation_id"], a["automacao"], a["quando"])
                  for a in self.leitor.atencoes(desde)]
        gestores = [p for p in pessoas if p.gestor]
        querem_maquina = any(MAQUINA_OFFLINE in p.tipos for p in gestores)
        minutos = sorted({p.fila_minutos for p in gestores if FILA_PARADA in p.tipos})
        if querem_maquina or minutos:
            visao = self.ver_fila(agora)
            if querem_maquina:
                sinais = self.leitor.ultimos_sinais()
                for m in visao["maquinas"]:
                    o = maquina_offline(m["id"], m["nome"] or m["id"], sinais.get(m["id"]), m["online"], agora)
                    if o is not None:
                        saida.append(o)
            if minutos:
                esperando = [datetime.fromisoformat(j["enfileirado_em"]) for j in visao["jobs"]]
                ultimo = self.leitor.ultimo_inicio()
                for m in minutos:
                    o = fila_parada(esperando, ultimo, agora, m)
                    if o is not None:
                        saida.append(o)
        unicas: dict[str, Ocorrencia] = {}
        for o in saida:
            unicas.setdefault(o.chave, o)  # a primeira atenção do item vale
        return list(unicas.values())

    def execute(self) -> dict[str, int]:
        agora = self.agora()
        com_usuario = self.avisos.pessoas()
        pessoas = [p for p, _ in com_usuario]
        usuarios = {p.user_id: u for p, u in com_usuario}
        ocorrencias = self.ocorrencias(agora, pessoas)
        ja = self.avisos.registradas([o.chave for o in ocorrencias])
        cache: dict[tuple[int, int], bool] = {}

        def pode(pessoa: Pessoa, automation_id: int) -> bool:
            chave = (pessoa.user_id, automation_id)
            if chave not in cache:
                cache[chave] = self.pode_ver(usuarios[pessoa.user_id], automation_id)
            return cache[chave]

        novas = avisos = 0
        for o in ocorrencias:
            if o.chave in ja:
                continue
            para = destinatarios(o, pessoas, pode)
            if self.avisos.registrar(o, para):
                novas += 1
                avisos += len(para)
        self.transaction.commit()
        return {"ocorrencias": novas, "avisos": avisos}


def corpo_do_email(titulo: str, texto: str, link: str | None, portal_url: str) -> str:
    linhas = [titulo, "", texto]
    if link:
        linhas += ["", f"Abrir no portal: {portal_url.rstrip('/')}{link}"]
    linhas += ["", "--", "Portal de Automações Biason. Para mudar o que recebe: Configurações > Notificações."]
    return "\n".join(linhas)


class EnviarAvisos:
    def __init__(self, avisos: Any, carteiro: Any | None, transaction: Any, portal_url: str,
                 agora: Callable[[], datetime] = _agora) -> None:
        self.avisos = avisos
        self.carteiro = carteiro
        self.transaction = transaction
        self.portal_url = portal_url
        self.agora = agora

    def execute(self, limite: int = 50) -> dict[str, int]:
        if self.carteiro is None:
            return {"ligado": 0}
        agora = self.agora()
        contagem = {"ligado": 1, "enviados": 0, "expirados": 0, "falhas": 0}
        for aviso, ocorrencia in self.avisos.pendentes(limite):
            if agora - aviso.created_at > VALIDADE_DO_ENVIO:
                aviso.email_status = "expirado"
                contagem["expirados"] += 1
                continue
            try:
                self.carteiro.enviar(aviso.email, ocorrencia.titulo,
                                     corpo_do_email(ocorrencia.titulo, ocorrencia.texto, ocorrencia.link, self.portal_url))
            except ErroDeEnvio as exc:
                aviso.tentativas += 1
                aviso.ultimo_erro = str(exc)[:500]
                if aviso.tentativas >= TENTATIVAS_DE_ENVIO:
                    aviso.email_status = "falhou"
                contagem["falhas"] += 1
                continue
            aviso.email_status = "enviado"
            aviso.enviado_em = agora
            contagem["enviados"] += 1
        self.transaction.commit()
        return contagem
