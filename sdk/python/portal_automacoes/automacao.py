"""API da automação. A mesma nos dois modos de conexão.

    with Automacao.conectar() as a:
        with a.etapa("iniciar"):
            ...
        for empresa in empresas:
            with a.item(empresa.codigo, rotulo=empresa.nome, configuracao={"separar_por_custo": True}):
                with a.etapa("rubricas", tarefas_previstas=50) as etapa:
                    ...
                    etapa.tarefa_concluida()
            if a.deve_parar():
                break

Falha de transporte nunca derruba a automação: o evento fica na fila local e é reenviado.
Evento fora do contrato é erro de programação e levanta EventoInvalido na hora.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from . import eventos, imagens
from .fila import FilaLocal
from .transporte import FalhaDeTransporte, Recusado, Transporte, TransporteDesligado
from .transporte_agente import TransporteAgente
from .transporte_direto import TransporteDireto

VERSAO_SDK = "0.1.0"
INTERVALO_COMANDOS_S = 2.0


class ParadaSolicitada(Exception):
    """Levantada por ``verificar_parada()`` quando o Portal pede para parar."""


class Etapa:
    def __init__(self, automacao: "Automacao", chave: str, item: str | None) -> None:
        self._automacao = automacao
        self.chave = chave
        self.item = item
        self.tarefas = 0

    def tarefa_concluida(self, quantidade: int = 1) -> None:
        self.tarefas += quantidade


class Automacao:
    def __init__(self, transporte: Transporte, fila: FilaLocal, versao_automacao: str | None = None,
                 log_local: Any = None) -> None:
        self._transporte = transporte
        self._fila = fila
        self._versao = versao_automacao
        self._log_local = log_local if log_local is not None else sys.stderr
        self._sequencia = fila.ultima_sequencia()
        self._conectado = False
        self._item: str | None = None
        self._item_atencao = False
        self._item_resumo: str | None = None
        self._execucao_atencao = False
        self._parar = False
        self._cancelar = False
        self._ultima_consulta = 0.0
        self.recusados = 0
        self._pendentes_ao_fechar: int | None = None
        # Emissão de várias threads (ex.: um monitor de tela à parte) sai em ordem e sem repetir sequência.
        self._trava = threading.RLock()

    # -- criação -------------------------------------------------------------
    @classmethod
    def conectar(cls, versao_automacao: str | None = None, ambiente: dict[str, str] | None = None) -> "Automacao":
        """Escolhe o modo pela configuração (variáveis de ambiente), nunca pelo código.

        PORTAL_MODO=agente|direto|desligado. Sem PORTAL_MODO: agente se o ExecutionHost
        entregou o pipe, direto se há PORTAL_URL, senão desligado."""
        env = os.environ if ambiente is None else ambiente
        modo = (env.get("PORTAL_MODO") or "").strip().lower()
        if not modo:
            modo = "agente" if env.get("AUTOMATION_EVENTS_PIPE") else "direto" if env.get("PORTAL_URL") else "desligado"
        if modo == "agente":
            artefatos = Path(env.get("AUTOMATION_ARTIFACTS_PATH") or tempfile.gettempdir())
            transporte: Transporte = TransporteAgente(env.get("AUTOMATION_EVENTS_PIPE", ""),
                                                      env.get("AUTOMATION_EVENTS_TOKEN", ""), artefatos / "passos")
            chave = env.get("AUTOMATION_ATTEMPT_ID") or env.get("AUTOMATION_EVENTS_PIPE", "")
        elif modo == "direto":
            transporte = TransporteDireto(env.get("PORTAL_URL", ""), env.get("PORTAL_JOB_ID", ""),
                                          env.get("PORTAL_JOB_TOKEN", ""), env.get("PORTAL_CA_ARQUIVO") or None)
            chave = env.get("PORTAL_JOB_ID", "")
        elif modo == "desligado":
            transporte, chave = TransporteDesligado(), f"local-{os.getpid()}-{time.time_ns()}"
        else:
            raise ValueError(f"PORTAL_MODO inválido: {modo!r} (use agente, direto ou desligado)")
        padrao = Path(env["AUTOMATION_TEMP_PATH"]) / "portal-fila" if env.get("AUTOMATION_TEMP_PATH") \
            else Path(tempfile.gettempdir()) / "portal-automacoes" / "fila"
        pasta = Path(env.get("PORTAL_FILA_DIR") or padrao)
        nome = hashlib.sha256(f"{transporte.nome}:{chave}".encode()).hexdigest()[:24]
        return cls(transporte, FilaLocal(pasta / f"{nome}.db"), versao_automacao)

    @property
    def modo(self) -> str:
        return self._transporte.nome

    @property
    def pendentes(self) -> int:
        """Eventos ainda sem confirmação (depois de fechar, o que ficou no disco)."""
        return self._pendentes_ao_fechar if self._pendentes_ao_fechar is not None else self._fila.quantidade()

    # -- ciclo da execução -----------------------------------------------------
    def __enter__(self) -> "Automacao":
        self._emitir("execucao.iniciada", {"versao_automacao": self._versao, "sdk": f"portal-automacoes-sdk {VERSAO_SDK}"})
        return self

    def __exit__(self, tipo: type[BaseException] | None, erro: BaseException | None, _tb: Any) -> None:
        if tipo is None:
            situacao = "atencao" if self._execucao_atencao else "ok"
        elif issubclass(tipo, (ParadaSolicitada, KeyboardInterrupt)):
            situacao = "interrompida"
        else:
            situacao = "erro"
        self._emitir("execucao.concluida", {"situacao": situacao,
                                            "resumo": _curto(str(erro)) if erro and situacao == "erro" else None})
        self.fechar()

    def fechar(self, tempo_limite_s: float = 10.0) -> None:
        """Tenta esvaziar a fila antes de sair. O que sobrar continua no disco."""
        limite = time.monotonic() + tempo_limite_s
        while time.monotonic() < limite:
            with self._trava:
                if not self._fila.quantidade() or self._descarregar():
                    if not self._fila.quantidade():
                        break
                    continue
            time.sleep(0.5)
        with self._trava:
            if self._fila.quantidade():
                self._avisar(f"{self._fila.quantidade()} evento(s) ainda na fila local; serão reenviados na próxima conexão")
            self._pendentes_ao_fechar = self._fila.quantidade()
            self._transporte.fechar()
            self._fila.fechar()

    # -- etapas e itens ----------------------------------------------------------
    @contextmanager
    def etapa(self, chave: str, tarefas_previstas: int | None = None) -> Iterator[Etapa]:
        """``tarefas_previstas``: total da etapa no job, contando o que tentativas anteriores já
        fizeram. ``tarefa_concluida()`` conta só o que esta tentativa fez."""
        etapa = Etapa(self, chave, self._item)
        self._emitir("etapa.iniciada", {"etapa": chave, "item": etapa.item, "tarefas_previstas": tarefas_previstas})
        try:
            yield etapa
        except (ParadaSolicitada, KeyboardInterrupt):
            self._concluir_etapa(etapa, "interrompida")
            raise
        except BaseException:
            self._concluir_etapa(etapa, "erro")
            raise
        self._concluir_etapa(etapa, "ok")

    def _concluir_etapa(self, etapa: Etapa, situacao: str) -> None:
        self._emitir("etapa.concluida", {"etapa": etapa.chave, "item": etapa.item, "situacao": situacao,
                                         "tarefas": etapa.tarefas if etapa.tarefas else None})

    @contextmanager
    def item(self, chave: Any, rotulo: str | None = None, grupo: Any = None,
             configuracao: dict[str, Any] | None = None) -> Iterator[None]:
        anterior = self._item
        self._item, self._item_atencao, self._item_resumo = str(chave), False, None
        self._emitir("item.iniciado", {"item": self._item, "rotulo": rotulo,
                                       "grupo": str(grupo) if grupo is not None else None,
                                       "configuracao": configuracao})
        situacao = "ok"
        try:
            yield
        except (ParadaSolicitada, KeyboardInterrupt):
            situacao = "cancelado"
            raise
        except BaseException as exc:
            situacao = "erro"
            self._item_resumo = self._item_resumo or _curto(str(exc))
            raise
        finally:
            if situacao == "ok" and self._item_atencao:
                situacao = "atencao"
            self._emitir("item.concluido", {"item": self._item, "situacao": situacao, "resumo": self._item_resumo})
            self._item = anterior

    # -- para automações que já existem: início e fim em pontos diferentes do código -----------
    def iniciar_item(self, chave: Any, rotulo: str | None = None, grupo: Any = None,
                     configuracao: dict[str, Any] | None = None) -> None:
        """Como ``with item(...)``, para quem não consegue envolver o item num bloco."""
        with self._trava:
            self._item, self._item_atencao, self._item_resumo = str(chave), False, None
            self._emitir("item.iniciado", {"item": self._item, "rotulo": rotulo,
                                           "grupo": str(grupo) if grupo is not None else None,
                                           "configuracao": configuracao})

    def concluir_item(self, situacao: str = "ok", resumo: str | None = None) -> None:
        """``situacao``: ok, erro, atencao, cancelado ou ignorado. Sem item aberto, não faz nada."""
        with self._trava:
            if self._item is None:
                return
            if situacao == "ok" and self._item_atencao:
                situacao = "atencao"
            self._emitir("item.concluido", {"item": self._item, "situacao": situacao,
                                            "resumo": _curto(resumo) if resumo else self._item_resumo})
            self._item = None

    def iniciar_etapa(self, chave: str, tarefas_previstas: int | None = None, item: Any = ...) -> None:
        """``item``: o item atual, se omitido; ``None`` para etapa da execução inteira."""
        with self._trava:
            alvo = self._item if item is ... else (None if item is None else str(item))
            self._emitir("etapa.iniciada", {"etapa": chave, "item": alvo, "tarefas_previstas": tarefas_previstas})

    def concluir_etapa(self, chave: str, situacao: str = "ok", tarefas: int | None = None, item: Any = ...) -> None:
        with self._trava:
            alvo = self._item if item is ... else (None if item is None else str(item))
            self._emitir("etapa.concluida", {"etapa": chave, "item": alvo, "situacao": situacao, "tarefas": tarefas or None})

    def resumo(self, texto: str) -> None:
        """Resumo curto do item atual (sem valores sensíveis), mostrado no Portal."""
        self._item_resumo = _curto(texto)

    def item_ignorado(self, chave: Any, motivo: str) -> None:
        self._emitir("item.concluido", {"item": str(chave), "situacao": "ignorado", "resumo": _curto(motivo)})

    # -- telemetria ---------------------------------------------------------------
    def progresso(self, atual: int, total: int, rotulo: str | None = None) -> None:
        self._emitir("progresso", {"atual": atual, "total": total, "rotulo": rotulo, "item": self._item})

    def log(self, texto: str, nivel: str = "info", espera: bool = False) -> None:
        self._emitir("log", {"nivel": nivel, "texto": texto[:4000], "espera": espera or None, "item": self._item})

    def passo(self, rotulo: str, tipo: str = "acao", imagem: Any = None) -> None:
        """Passo da trajetória. A imagem vai por fora do canal de eventos; o evento leva só o id."""
        with self._trava:
            self._passo(rotulo, tipo, imagem)

    def _passo(self, rotulo: str, tipo: str, imagem: Any) -> None:
        imagem_id = None
        if imagem is not None:
            try:
                jpeg = imagens.preparar(imagem)
                imagem_id = imagens.novo_id()
                self._transporte.enviar_imagem(imagem_id, jpeg)
            except imagens.ImagemRecusada as exc:
                self._avisar(f"imagem do passo '{rotulo}' não enviada: {exc}")
                imagem_id = None
            except (FalhaDeTransporte, Recusado, OSError) as exc:
                self._avisar(f"imagem do passo '{rotulo}' não enviada: {exc}")
                imagem_id = None
        self._emitir("passo", {"rotulo": rotulo[:200], "tipo": tipo, "imagem_id": imagem_id, "item": self._item})

    def espera(self, rotulo: str, desde: str) -> None:
        """Ainda na mesma tela, sem imagem nova. ``desde`` em ISO 8601 com fuso."""
        self._emitir("espera.atualizada", {"desde": desde, "rotulo": rotulo, "item": self._item})

    def atencao(self, motivo: str, colunas: Sequence[tuple[str, str]] = (), linhas: Sequence[dict[str, Any]] = (),
                acoes: Sequence[dict[str, Any]] = ()) -> None:
        """O item precisa de uma pessoa (ex.: rubricas a parametrizar)."""
        if self._item is None:
            raise eventos.EventoInvalido("atencao precisa estar dentro de um item")
        payload: dict[str, Any] = {"item": self._item, "motivo": motivo}
        if colunas:
            payload["tabela"] = {"colunas": [{"chave": c, "titulo": t} for c, t in colunas], "linhas": list(linhas)}
        if acoes:
            payload["acoes"] = list(acoes)
        self._emitir("atencao", payload)
        self._item_atencao = self._execucao_atencao = True

    @contextmanager
    def pausa(self, motivo: str, detalhe: str | None = None) -> Iterator[None]:
        """Tempo fora do controle da automação (reinício, espera externa): fica fora da estimativa."""
        self._emitir("pausa.iniciada", {"motivo": motivo, "detalhe": detalhe, "item": self._item})
        try:
            yield
        finally:
            self._emitir("pausa.concluida", {"motivo": motivo, "item": self._item})

    # -- comandos -----------------------------------------------------------------
    def deve_parar(self) -> bool:
        """O Portal pediu para parar depois do item atual (ou cancelar)."""
        self._consultar_comandos()
        return self._parar or self._cancelar

    def cancelamento_pedido(self) -> bool:
        self._consultar_comandos()
        return self._cancelar

    def verificar_parada(self) -> None:
        if self.deve_parar():
            raise ParadaSolicitada("parada solicitada pelo Portal")

    def _consultar_comandos(self) -> None:
        agora = time.monotonic()
        if agora - self._ultima_consulta < INTERVALO_COMANDOS_S:
            return
        self._ultima_consulta = agora
        try:
            self._garantir_conexao()
            recebidos = self._transporte.comandos()
        except (FalhaDeTransporte, Recusado) as exc:
            self._avisar(f"sem consulta de comandos: {exc}")
            return
        for comando in recebidos:
            if not eventos.comando_valido(comando):
                self._avisar("comando fora do contrato ignorado")
                continue
            if comando["type"] == "cancelar":
                self._cancelar = True
            elif comando["type"] == "parar_apos_item":
                self._parar = True

    # -- envio ----------------------------------------------------------------------
    def _emitir(self, tipo: str, payload: dict[str, Any]) -> None:
        with self._trava:
            self._sequencia += 1
            evento = eventos.montar(self._sequencia, tipo, payload)
            self._fila.adicionar(evento)
            self._descarregar()

    def _garantir_conexao(self) -> None:
        if not self._conectado:
            ultima = self._transporte.conectar()
            self._fila.confirmar_ate(ultima)
            self._conectado = True

    def _descarregar(self) -> bool:
        try:
            self._garantir_conexao()
            while pendentes := self._fila.pendentes(500):
                try:
                    confirmada = self._transporte.enviar(pendentes)
                except Recusado as exc:
                    # Recusa definitiva de um evento: registra e segue, senão a fila trava.
                    self.recusados += 1
                    self._avisar(str(exc))
                    confirmada = pendentes[0]["sequence"]
                for recusado in getattr(self._transporte, "recusados", None) or []:
                    self.recusados += 1
                    self._avisar(f"Portal recusou o evento {recusado.get('sequence')}: {recusado.get('motivo')}")
                if getattr(self._transporte, "recusados", None):
                    self._transporte.recusados.clear()  # type: ignore[attr-defined]
                if confirmada < pendentes[0]["sequence"]:
                    return False
                self._fila.confirmar_ate(confirmada)
            return True
        except FalhaDeTransporte as exc:
            self._conectado = False
            self._avisar(f"{exc}; {self._fila.quantidade()} evento(s) na fila local")
            return False
        except Recusado as exc:
            self._conectado = False
            self._avisar(str(exc))
            return False

    def _avisar(self, texto: str) -> None:
        try:
            print(f"[portal-automacoes] {texto}", file=self._log_local, flush=True)
        except (OSError, ValueError):
            pass


def _curto(texto: str) -> str:
    texto = " ".join(texto.split())
    return texto[:297] + "..." if len(texto) > 300 else texto
