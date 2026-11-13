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

Parar e cancelar (0.4.0): o SDK atende os comandos do Portal sozinho, em qualquer automação.

- ``parar_apos_item``: o próximo ``item()``/``iniciar_item()`` não começa (levanta
  ``ParadaSolicitada``); quem registrou ``ao_parar`` é chamado na hora.
- ``cancelar``: quem registrou ``ao_cancelar`` é chamado na hora e tem ``PRAZO_CANCELAR_S``
  (60 s, ou PORTAL_PRAZO_CANCELAR_S) para encerrar. Sem nada registrado, ou passado o prazo, o
  SDK interrompe a thread principal (como um Ctrl+C) e, se a automação roda num processo só
  dela (``portal-automacoes trabalhar -- comando``), encerra o processo 15 s depois.
- Sem comunicação com o Portal por ``LIMITE_SEM_PORTAL_S`` (2 min, ou
  PORTAL_LIMITE_SEM_PORTAL_S), ou o Portal dizendo que o job não vale mais (401/409), o SDK
  avisa no log local e cancela a execução do mesmo jeito: a automação não roda às cegas.

Segredos (0.5.0): ``a.segredo("dominio.senha_banco")`` devolve o valor ligado à automação no
Portal (aba Técnico), só durante a execução. O valor fica na memória e vira ``***`` em todo
evento e no log local. Ver ``segredos.py``.

``segundo_plano=True`` (ou PORTAL_ENVIO_EM_SEGUNDO_PLANO=1): uma thread do SDK envia os
eventos, as imagens, os arquivos entregues (``arquivo()``) e consulta os comandos. Quem emite nunca espera a rede: com o Portal
fora do ar, o robô segue no mesmo ritmo e tudo fica na fila local. Recomendado para
automação de tela (RPA).
"""

from __future__ import annotations

import _thread
import hashlib
import mimetypes
import os
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

from . import eventos, imagens
from .segredos import MINIMO_PARA_MASCARAR, SegredoIndisponivel, mascarar, normalizar
from .fila import FilaLocal
from .transporte import FalhaDeTransporte, Recusado, Transporte, TransporteDesligado
from .transporte_agente import TransporteAgente
from .enderecos import ligado
from .transporte_direto import TransporteDireto

VERSAO_SDK = "0.5.0"
INTERVALO_COMANDOS_S = 2.0
PRAZO_CANCELAR_S = 60.0  # depois de "cancelar", quanto a automação tem para parar sozinha
FOLGA_ENCERRAR_S = 15.0  # depois da interrupção, quanto até encerrar o processo (só processo próprio)
LIMITE_SEM_PORTAL_S = 120.0  # sem falar com o Portal por isso, a execução é cancelada

# O SDK interrompeu a thread principal (cancelamento, Portal fora do ar ou job encerrado no
# Portal). ``trabalhar`` usa isso para seguir esperando jobs em vez de sair com o Ctrl+C.
_interrompeu = threading.Event()


def interrompida_pelo_sdk(limpar: bool = True) -> bool:
    """A interrupção (KeyboardInterrupt) foi do SDK, e não de uma pessoa no terminal."""
    houve = _interrompeu.is_set()
    if limpar:
        _interrompeu.clear()
    return houve
ESPERA_MAXIMA_S = 30.0  # segundo plano: maior intervalo entre tentativas com o Portal fora do ar
LIMITE_ARQUIVO = 100 * 1024 * 1024  # o mesmo do Portal


class ParadaSolicitada(Exception):
    """Levantada por ``verificar_parada()`` (e no início de um item depois de "parar") quando o
    Portal pede para parar."""


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
                 log_local: Any = None, segundo_plano: bool = False, *, prazo_cancelar_s: float = PRAZO_CANCELAR_S,
                 limite_sem_portal_s: float = LIMITE_SEM_PORTAL_S, processo_proprio: bool = False,
                 interromper: Callable[[], None] | None = None, encerrar_processo: Callable[[int], None] | None = None) -> None:
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
        self._motivo: str | None = None
        self._ao_parar: list[Callable[[], Any]] = []
        self._ao_cancelar: list[Callable[[], Any]] = []
        self._encerrada = False
        self._prazo_cancelar_s = prazo_cancelar_s
        self._limite_sem_portal_s = limite_sem_portal_s
        self._processo_proprio = processo_proprio
        self._interromper_principal = interromper or _thread.interrupt_main
        self._encerrar_processo = encerrar_processo or os._exit
        self._sem_portal_desde: float | None = None
        self._trata_pedidos = False  # a automação consulta deve_parar()/cancelamento_pedido()
        self._temporizadores: list[threading.Timer] = []
        self._ultima_consulta = 0.0
        self.recusados = 0
        self._pendentes_ao_fechar: int | None = None
        # Emissão de várias threads (ex.: um monitor de tela à parte) sai em ordem e sem repetir sequência.
        self._trava = threading.RLock()
        self._trava_envio = threading.RLock()  # só uma conversa com o Portal por vez
        self._segundo_plano = segundo_plano
        self._acordar = threading.Event()
        self._fim = threading.Event()
        self._fora_do_ar_ate = 0.0
        self._arquivos: list[tuple[Path, str, str | None]] = []  # entregues e ainda não enviados
        self._trava_arquivos = threading.Lock()  # só protege a lista; nunca segura outra trava
        self._enviador: threading.Thread | None = None
        self._segredos: dict[str, str] = {}  # só na memória
        self._mascarar: list[str] = []  # valores a trocar por *** (o mais longo primeiro)
        self._trava_segredos = threading.Lock()
        if segundo_plano:
            self._enviador = threading.Thread(target=self._enviar_em_segundo_plano, name="portal-automacoes-envio",
                                              daemon=True)
            self._enviador.start()

    # -- criação -------------------------------------------------------------
    @classmethod
    def conectar(cls, versao_automacao: str | None = None, ambiente: dict[str, str] | None = None,
                 segundo_plano: bool | None = None) -> "Automacao":
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
                                          env.get("PORTAL_JOB_TOKEN", ""), env.get("PORTAL_CA_ARQUIVO") or None,
                                          permitir_http=ligado(env.get("PORTAL_PERMITIR_HTTP")))
            chave = env.get("PORTAL_JOB_ID", "")
        elif modo == "desligado":
            transporte, chave = TransporteDesligado(), f"local-{os.getpid()}-{time.time_ns()}"
        else:
            raise ValueError(f"PORTAL_MODO inválido: {modo!r} (use agente, direto ou desligado)")
        padrao = Path(env["AUTOMATION_TEMP_PATH"]) / "portal-fila" if env.get("AUTOMATION_TEMP_PATH") \
            else Path(tempfile.gettempdir()) / "portal-automacoes" / "fila"
        pasta = Path(env.get("PORTAL_FILA_DIR") or padrao)
        nome = hashlib.sha256(f"{transporte.nome}:{chave}".encode()).hexdigest()[:24]
        if segundo_plano is None:
            segundo_plano = ligado(env.get("PORTAL_ENVIO_EM_SEGUNDO_PLANO"))
        return cls(transporte, FilaLocal(pasta / f"{nome}.db"), versao_automacao, segundo_plano=segundo_plano,
                   prazo_cancelar_s=_segundos(env.get("PORTAL_PRAZO_CANCELAR_S"), PRAZO_CANCELAR_S),
                   limite_sem_portal_s=_segundos(env.get("PORTAL_LIMITE_SEM_PORTAL_S"), LIMITE_SEM_PORTAL_S),
                   # Rodando por "portal-automacoes trabalhar -- comando": o processo é só desta execução.
                   processo_proprio=bool(os.environ.get("PORTAL_JOB_ARQUIVO")) and ambiente is None)

    @property
    def modo(self) -> str:
        return self._transporte.nome

    @property
    def arquivos_pendentes(self) -> int:
        with self._trava_arquivos:
            return len(self._arquivos)

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
        resumo = _curto(str(erro)) if erro and situacao == "erro" else (
            _curto(self._motivo) if situacao == "interrompida" and self._motivo else None)
        self._concluir(situacao, resumo)
        self.fechar()

    def _concluir(self, situacao: str, resumo: str | None) -> None:
        """``execucao.concluida`` uma vez só (a saída normal e o encerramento à força não repetem)."""
        with self._trava:
            if self._encerrada:
                return
            self._encerrada = True
        for t in self._temporizadores:
            t.cancel()
        self._emitir("execucao.concluida", {"situacao": situacao, "resumo": resumo})

    def fechar(self, tempo_limite_s: float = 10.0) -> None:
        """Tenta esvaziar a fila antes de sair. O que sobrar continua no disco."""
        self._encerrada = True
        for t in self._temporizadores:
            t.cancel()
        if self._enviador is not None:
            self._fim.set()
            self._acordar.set()
            self._enviador.join(timeout=tempo_limite_s)
            self._enviador = None
            self._fora_do_ar_ate = 0.0
        limite = time.monotonic() + tempo_limite_s
        while time.monotonic() < limite:
            with self._trava:
                if not self._fila.quantidade() or self._descarregar():
                    if not self._fila.quantidade():
                        break
                    continue
            time.sleep(0.5)
        while self.arquivos_pendentes and time.monotonic() < limite:
            if not self._enviar_arquivos():
                time.sleep(0.5)
        with self._trava_arquivos:
            perdidos, self._arquivos = self._arquivos, []
        for caminho, nome, _ in perdidos:
            self._avisar(f"arquivo '{nome}' não foi enviado ao Portal (continua em {caminho})")
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
        self._antes_de_um_item()
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
        self._antes_de_um_item()
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
        """Passo da trajetória. A imagem vai por fora do canal de eventos; o evento leva só o id.
        O envio da imagem não segura quem emite os outros eventos. Com o Portal fora do ar, a
        imagem não é enviada (o passo entra só com o texto): imagem não fica na fila local."""
        self._passo(rotulo, tipo, imagem)

    def _passo(self, rotulo: str, tipo: str, imagem: Any) -> None:
        imagem_id = None
        if imagem is not None and time.monotonic() < self._fora_do_ar_ate:
            self._avisar(f"imagem do passo '{rotulo}' não enviada: Portal fora do ar")
            imagem = None
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
                if isinstance(exc, FalhaDeTransporte):
                    self._fora_do_ar_ate = time.monotonic() + ESPERA_MAXIMA_S
        self._emitir("passo", {"rotulo": rotulo[:200], "tipo": tipo, "imagem_id": imagem_id, "item": self._item})

    def arquivo(self, caminho: str | os.PathLike[str], nome: str | None = None, item: Any = ...) -> None:
        """Arquivo que a automação entregou (planilha, TXT...): aparece na aba Arquivos do
        Catálogo, ligado à execução e ao item (por padrão, o item atual). Vai por fora do canal de
        eventos, até 100 MB. Com o Portal fora do ar, fica pendente e é tentado de novo até
        ``fechar()``; o que não sair até lá é avisado no log local (o arquivo continua no disco)."""
        origem = Path(caminho)
        if not origem.is_file():
            raise FileNotFoundError(f"arquivo não encontrado: {origem}")
        tamanho = origem.stat().st_size
        if tamanho == 0:
            raise ValueError(f"arquivo vazio: {origem}")
        if tamanho > LIMITE_ARQUIVO:
            raise ValueError(f"arquivo acima de 100 MB: {origem}")
        dono = self._item if item is ... else (None if item is None else str(item))
        with self._trava_arquivos:
            self._arquivos.append((origem, (nome or origem.name)[:255], dono))
        if self._segundo_plano:
            self._acordar.set()
        else:
            self._enviar_arquivos()

    def _enviar_arquivos(self) -> bool:
        """Envia os pendentes em ordem. ``False``: Portal fora do ar (o resto fica para depois)."""
        while True:
            with self._trava_arquivos:
                if not self._arquivos:
                    return True
                caminho, nome, item = self._arquivos[0]
            try:
                with self._trava_envio:
                    tipo = mimetypes.guess_type(nome)[0] or "application/octet-stream"
                    self._transporte.enviar_arquivo(caminho, nome, item, tipo)
            except FalhaDeTransporte as exc:
                self._avisar(f"arquivo '{nome}' não enviado agora: {exc}")
                return False
            except (Recusado, OSError) as exc:  # recusa definitiva ou arquivo sumiu: não insiste
                self._avisar(f"arquivo '{nome}' não enviado: {exc}")
            with self._trava_arquivos:
                if self._arquivos and self._arquivos[0] == (caminho, nome, item):
                    self._arquivos.pop(0)

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

    def iniciar_pausa(self, motivo: str, detalhe: str | None = None) -> None:
        """Como ``with pausa(...)``, para quem não consegue envolver a pausa num bloco."""
        self._emitir("pausa.iniciada", {"motivo": motivo, "detalhe": detalhe, "item": self._item})

    def concluir_pausa(self, motivo: str) -> None:
        self._emitir("pausa.concluida", {"motivo": motivo, "item": self._item})

    # -- comandos -----------------------------------------------------------------
    def ao_cancelar(self, funcao: Callable[[], Any]) -> Callable[[], Any]:
        """Chamada (numa thread do SDK) assim que chega o "cancelar": a automação fecha o que
        precisa. Ela tem ``PRAZO_CANCELAR_S`` para terminar; depois o SDK interrompe."""
        self._ao_cancelar.append(funcao)
        return funcao

    def ao_parar(self, funcao: Callable[[], Any]) -> Callable[[], Any]:
        """Chamada assim que chega o "parar depois do item atual"."""
        self._ao_parar.append(funcao)
        return funcao

    @property
    def motivo_da_parada(self) -> str | None:
        return self._motivo

    def _antes_de_um_item(self) -> None:
        if not self._segundo_plano:
            self._consultar_comandos(fora_do_intervalo=True)  # início de item é raro: consulta sempre
        if self._parar or self._cancelar:
            raise ParadaSolicitada(self._motivo or "parada solicitada pelo Portal")

    def _receber(self, tipo: str, motivo: str) -> None:
        """Um pedido de parada (do Portal ou do próprio SDK). Cada tipo é atendido uma vez."""
        if tipo == "parar_apos_item":
            if self._parar or self._cancelar:
                return
            self._parar, self._motivo = True, motivo
            self._avisar(f"pedido para parar: {motivo}")
            self._emitir("log", {"nivel": "aviso", "texto": f"Pedido para parar recebido ({motivo}): termina o item "
                                                            "atual e não começa outro", "item": self._item})
            self._chamar(self._ao_parar)
            return
        if self._cancelar or self._encerrada:
            return
        self._cancelar, self._motivo = True, motivo
        self._avisar(f"cancelamento: {motivo}")
        self._emitir("log", {"nivel": "aviso", "texto": f"Cancelamento recebido ({motivo}): encerrando", "item": self._item})
        if self._ao_cancelar or self._trata_pedidos:
            self._chamar(self._ao_cancelar)
            self._agendar(self._prazo_cancelar_s, self._interromper)
        else:
            self._interromper()  # ninguém trata o cancelamento: interrompe já

    def _chamar(self, funcoes: list[Callable[[], Any]]) -> None:
        for funcao in list(funcoes):
            threading.Thread(target=self._chamar_uma, args=(funcao,), name="portal-automacoes-pedido", daemon=True).start()

    def _chamar_uma(self, funcao: Callable[[], Any]) -> None:
        try:
            funcao()
        except Exception as exc:  # noqa: BLE001 - o tratamento da automação falhou: o prazo segue valendo
            self._avisar(f"tratamento do pedido falhou: {exc.__class__.__name__}: {exc}")

    def _agendar(self, segundos: float, acao: Callable[[], None]) -> None:
        temporizador = threading.Timer(max(segundos, 0.0), acao)
        temporizador.daemon = True
        self._temporizadores.append(temporizador)
        temporizador.start()

    def _interromper(self) -> None:
        """A automação não parou sozinha: interrompe a thread principal (KeyboardInterrupt)."""
        if self._encerrada:
            return
        self._avisar("a automação não parou sozinha: interrompendo")
        _interrompeu.set()
        try:
            self._interromper_principal()
        except Exception as exc:  # noqa: BLE001
            self._avisar(f"não consegui interromper: {exc}")
        if self._processo_proprio:
            self._agendar(FOLGA_ENCERRAR_S, self._encerrar_agora)

    def _encerrar_agora(self) -> None:
        """Último recurso, só quando o processo é só desta execução: registra o fim e sai."""
        if self._encerrada:
            return
        self._avisar("a automação continua presa depois da interrupção: encerrando o processo")
        with self._trava:
            if self._item is not None:
                self._emitir("item.concluido", {"item": self._item, "situacao": "cancelado", "resumo": None})
                self._item = None
        self._concluir("interrompida", _curto(self._motivo or "cancelada"))
        self.fechar(tempo_limite_s=5.0)
        self._encerrar_processo(130)

    def _sem_portal(self, exc: Exception) -> None:
        """Falha de comunicação: avisa na primeira e cancela depois de ``LIMITE_SEM_PORTAL_S``."""
        if self._sem_portal_desde is None:
            self._sem_portal_desde = time.monotonic()
            self._avisar(f"sem comunicação com o Portal ({exc}); tentando por até {self._limite_sem_portal_s:.0f} s")
        self._verificar_sem_portal()

    def _com_portal(self) -> None:
        if self._sem_portal_desde is not None:
            self._avisar("comunicação com o Portal de volta")
        self._sem_portal_desde = None

    def _verificar_sem_portal(self) -> None:
        if (self._sem_portal_desde is not None and not self._cancelar and getattr(self._transporte, "nome", "") != "desligado"
                and time.monotonic() - self._sem_portal_desde >= self._limite_sem_portal_s):
            self._receber("cancelar", f"sem comunicação com o Portal há {self._limite_sem_portal_s / 60:.0f} min")

    def _job_encerrado_no_portal(self, exc: Recusado) -> bool:
        """401/409 no modo direto: o Portal já encerrou este job (cancelado, encerrado à força)."""
        if getattr(exc, "codigo", None) in (401, 409) and getattr(self._transporte, "nome", "") == "direto":
            self._receber("cancelar", "o Portal encerrou esta execução")
            return True
        return False

    def deve_parar(self) -> bool:
        """O Portal pediu para parar depois do item atual (ou cancelar)."""
        self._trata_pedidos = True
        if not self._segundo_plano:  # em segundo plano, a thread de envio consulta
            self._consultar_comandos()
        return self._parar or self._cancelar

    def cancelamento_pedido(self) -> bool:
        self._trata_pedidos = True
        if not self._segundo_plano:
            self._consultar_comandos()
        return self._cancelar

    def verificar_parada(self) -> None:
        if self.deve_parar():
            raise ParadaSolicitada("parada solicitada pelo Portal")

    def _consultar_comandos(self, fora_do_intervalo: bool = False) -> None:
        agora = time.monotonic()
        if not fora_do_intervalo:
            if agora - self._ultima_consulta < INTERVALO_COMANDOS_S:
                return
            self._ultima_consulta = agora
        try:
            with self._trava_envio:
                self._garantir_conexao()
                recebidos = self._transporte.comandos()
        except FalhaDeTransporte as exc:
            self._sem_portal(exc)
            return
        except Recusado as exc:
            if not self._job_encerrado_no_portal(exc):
                self._avisar(f"sem consulta de comandos: {exc}")
            return
        self._com_portal()
        for comando in recebidos:
            if not eventos.comando_valido(comando):
                self._avisar("comando fora do contrato ignorado")
                continue
            motivo = str(comando.get("motivo") or "pedido pelo Portal")
            if comando["type"] in ("cancelar", "parar_apos_item"):
                self._receber(comando["type"], motivo)

    # -- segredos -------------------------------------------------------------------
    def segredo(self, chave: str) -> str:
        """Valor do segredo ligado a esta automação no Portal. Levanta ``SegredoIndisponivel``."""
        return self.segredos(chave)[normalizar(chave)]

    def segredos(self, *chaves: str) -> dict[str, str]:
        """Vários de uma vez (um pedido só). Devolve ``{chave: valor}`` com as chaves normalizadas."""
        if not chaves:
            raise ValueError("informe ao menos uma chave")
        pedidas = list(dict.fromkeys(normalizar(c) for c in chaves))
        with self._trava_segredos:
            faltam = [c for c in pedidas if c not in self._segredos]
            if faltam:
                buscar = getattr(self._transporte, "segredos", None)
                if buscar is None:
                    raise SegredoIndisponivel(f"o modo {self.modo} não entrega segredos")
                try:
                    resposta = buscar(faltam)
                except FalhaDeTransporte as exc:
                    raise SegredoIndisponivel(f"Portal indisponível para entregar {', '.join(faltam)}: {exc}") from exc
                except Recusado as exc:
                    raise SegredoIndisponivel(f"o Portal recusou o pedido de segredos: {exc}") from exc
                for chave, valor in (resposta.get("segredos") or {}).items():
                    if isinstance(valor, str):
                        self._segredos[chave] = valor
                        if len(valor) >= MINIMO_PARA_MASCARAR and valor not in self._mascarar:
                            self._mascarar = sorted([*self._mascarar, valor], key=len, reverse=True)
                negados = {c: m for c, m in (resposta.get("negados") or {}).items() if c in faltam}
                ausentes = [c for c in faltam if c not in self._segredos]
                if ausentes:
                    motivos = "; ".join(f"{c}: {negados.get(c, 'não veio do Portal')}" for c in ausentes)
                    raise SegredoIndisponivel(f"segredo indisponível ({motivos})")
            return {c: self._segredos[c] for c in pedidas}

    # -- envio ----------------------------------------------------------------------
    def _emitir(self, tipo: str, payload: dict[str, Any]) -> None:
        payload = mascarar(payload, self._mascarar)  # nem a fila local guarda o valor
        with self._trava:
            self._sequencia += 1
            evento = eventos.montar(self._sequencia, tipo, payload)
            self._fila.adicionar(evento)
            if not self._segundo_plano:
                self._descarregar()
                self._verificar_sem_portal()
        if self._segundo_plano:
            self._acordar.set()

    def _enviar_em_segundo_plano(self) -> None:
        espera = 1.0
        while not self._fim.is_set():
            self._acordar.wait(INTERVALO_COMANDOS_S if espera <= 1.0 else espera)
            self._acordar.clear()
            if self._fim.is_set():
                break
            self._verificar_sem_portal()
            if time.monotonic() < self._fora_do_ar_ate:
                continue  # fora do ar: não insiste a cada evento novo
            ok = self._descarregar() if self._fila.quantidade() else True
            if ok and self.arquivos_pendentes:
                ok = self._enviar_arquivos()
            if ok:
                espera = 1.0
                self._consultar_comandos()
            else:
                espera = min(espera * 2, ESPERA_MAXIMA_S)
                self._fora_do_ar_ate = time.monotonic() + espera

    def _garantir_conexao(self) -> None:
        if not self._conectado:
            ultima = self._transporte.conectar()
            self._fila.confirmar_ate(ultima)
            self._conectado = True

    def _descarregar(self) -> bool:
        with self._trava_envio:
            return self._descarregar_sem_trava()

    def _descarregar_sem_trava(self) -> bool:
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
            self._com_portal()
            return True
        except FalhaDeTransporte as exc:
            self._conectado = False
            self._avisar(f"{exc}; {self._fila.quantidade()} evento(s) na fila local")
            self._sem_portal(exc)
            return False
        except Recusado as exc:
            self._conectado = False
            self._avisar(str(exc))
            self._job_encerrado_no_portal(exc)
            return False

    def _avisar(self, texto: str) -> None:
        try:
            print(f"[portal-automacoes] {mascarar(texto, self._mascarar)}", file=self._log_local, flush=True)
        except (OSError, ValueError):
            pass


def _segundos(texto: str | None, padrao: float) -> float:
    try:
        valor = float(texto) if texto not in (None, "") else padrao
    except ValueError:
        return padrao
    return valor if valor > 0 else padrao


def _curto(texto: str) -> str:
    texto = " ".join(texto.split())
    return texto[:297] + "..." if len(texto) > 300 else texto
