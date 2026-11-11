"""Instância direta: inscrição, sessão por desafio assinado e espera de jobs (ADR-018).

Uso típico numa máquina sem Agent:

    instancia = Instancia.inscrever("https://portal:8443", codigo="ABCD-EFGH-JKLM-NPQR",
                                    nome="integracao-contabil", arquivo_ca="Biason-Intranet-Root-CA.crt")
    trabalhar(instancia, executar=lambda job, ambiente: rodar_lote(job, ambiente))

- A chave ECDSA P-256 é gerada aqui e a privada fica cifrada com o DPAPI do Windows, no
  escopo do usuário: só esse usuário, nesta máquina, consegue usá-la. Nunca sai da máquina.
- HTTPS, TLS 1.2+, certificado sempre validado. Credencial só no corpo ou no cabeçalho.
  Exceção provisória: ``permitir_http=True`` aceita http:// só na rede interna (``enderecos.py``).
- Depois da inscrição, a instância fica pendente até o administrador aprová-la e escolher
  a máquina no Portal. Enquanto isso, ``trabalhar`` só espera.
"""

from __future__ import annotations

import base64
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .enderecos import usa_http, validar_url_portal
from .transporte import FalhaDeTransporte, Recusado

PROTOCOLO = "portal-automacoes/direto/1"
ENTROPIA = PROTOCOLO.encode("utf-8")
ESPERA_JOB_S = 30
TEMPO_LIMITE_S = 45.0  # acima da espera longa do próximo job


def pasta_padrao() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "PortalAutomacoes" / "instancias"


@dataclass(frozen=True)
class Job:
    job_id: str
    execucao_id: str
    token: str
    tentativa: int
    parametros: dict[str, Any]
    itens: list[dict[str, Any]]


class Instancia:
    def __init__(self, portal: str, instancia_id: str, chave_privada: Any, arquivo_ca: str | None,
                 arquivo: Path | None = None, permitir_http: bool = False) -> None:
        self.portal = validar_url_portal(portal, permitir_http)
        self.permitir_http = permitir_http
        self.id = instancia_id
        self._chave = chave_privada
        self.arquivo_ca = arquivo_ca
        self.arquivo = arquivo
        self._tls = None if usa_http(self.portal) else contexto_tls(arquivo_ca)
        self._sessao: tuple[str, datetime] | None = None

    # -- inscrição e credencial ------------------------------------------------------------
    @classmethod
    def inscrever(cls, portal: str, *, codigo: str, nome: str, arquivo_ca: str | None = None,
                  nome_maquina: str | None = None, versao_sdk: str = "0.1.0", pasta: Path | None = None,
                  permitir_http: bool = False) -> "Instancia":
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        arquivo = (pasta or pasta_padrao()) / f"{nome}.json"
        if arquivo.exists():
            raise FileExistsError(f"já existe a credencial {arquivo}; apague-a só se for inscrever de novo")
        chave = ec.generate_private_key(ec.SECP256R1())
        publica = chave.public_key().public_bytes(serialization.Encoding.PEM,
                                                  serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii")
        portal = validar_url_portal(portal, permitir_http)
        resposta = _pedir(None if usa_http(portal) else contexto_tls(arquivo_ca), "POST", portal + "/api/v1/direto/inscricao",
                          {"codigo": codigo, "chave_publica": publica, "versao_sdk": versao_sdk,
                           "nome_maquina": nome_maquina or os.environ.get("COMPUTERNAME") or ""})
        instancia = cls(portal, str(resposta["instancia_id"]), chave, arquivo_ca, arquivo, permitir_http)
        privada = chave.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption())
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(json.dumps({
            "portal": instancia.portal, "instancia_id": instancia.id, "arquivo_ca": arquivo_ca,
            "permitir_http": permitir_http,
            "chave_privada_dpapi": base64.b64encode(proteger(privada)).decode("ascii"),
        }, indent=2), encoding="utf-8")
        return instancia

    @classmethod
    def carregar(cls, nome_ou_arquivo: str | Path) -> "Instancia":
        from cryptography.hazmat.primitives import serialization

        arquivo = Path(nome_ou_arquivo)
        if not arquivo.suffix:
            arquivo = pasta_padrao() / f"{nome_ou_arquivo}.json"
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        privada = desproteger(base64.b64decode(dados["chave_privada_dpapi"]))
        chave = serialization.load_der_private_key(privada, password=None)
        return cls(dados["portal"], dados["instancia_id"], chave, dados.get("arquivo_ca"), arquivo,
                   bool(dados.get("permitir_http")))

    # -- sessão ----------------------------------------------------------------------------
    def _token(self) -> str:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec

        agora = datetime.now(timezone.utc)
        if self._sessao and self._sessao[1] - agora > timedelta(seconds=60):
            return self._sessao[0]
        desafio = _pedir(self._tls, "POST", self.portal + "/api/v1/direto/sessao/desafio", {"instancia_id": self.id})
        mensagem = f"{PROTOCOLO}|{self.id}|{desafio['desafio_id']}|{desafio['nonce']}".encode("utf-8")
        assinatura = self._chave.sign(mensagem, ec.ECDSA(hashes.SHA256()))
        sessao = _pedir(self._tls, "POST", self.portal + "/api/v1/direto/sessao", {
            "instancia_id": self.id, "desafio_id": desafio["desafio_id"],
            "assinatura": base64.b64encode(assinatura).decode("ascii")})
        self._sessao = (sessao["token"], datetime.fromisoformat(sessao["expira_em"]))
        return self._sessao[0]

    def status(self) -> dict[str, Any]:
        return _pedir(self._tls, "GET", self.portal + "/api/v1/direto/status", token=self._token())

    def proximo_job(self, espera: int = ESPERA_JOB_S) -> Job | None:
        resposta = _pedir(self._tls, "GET", self.portal + f"/api/v1/direto/jobs/proximo?espera={int(espera)}",
                          token=self._token())
        job = resposta.get("job")
        if not job:
            return None
        return Job(job["job_id"], job["execucao_id"], job["token"], int(job.get("tentativa") or 1),
                   dict(job.get("parametros") or {}), list(job.get("itens") or []))

    def declarar(self, declaracao: dict[str, Any]) -> dict[str, Any]:
        """Diz ao Portal o que a automação pede para executar (``parametros``), o que é um item
        (``itens``: nome, chave, grupo e ``colunas``) e, se tiver, a ``tabela`` de itens. O Portal
        junta com o que já existe (edições feitas lá valem) e põe a tabela em prévia para alguém
        aprovar. Só vale com a instância aprovada. Devolve o que mudou."""
        return _pedir(self._tls, "POST", self.portal + "/api/v1/direto/declaracao", declaracao, token=self._token())

    def ambiente_do_job(self, job: Job) -> dict[str, str]:
        """O que ``Automacao.conectar(ambiente=...)`` precisa para falar com o Portal neste job."""
        ambiente = {"PORTAL_MODO": "direto", "PORTAL_URL": self.portal, "PORTAL_JOB_ID": job.job_id,
                    "PORTAL_JOB_TOKEN": job.token}
        if self.arquivo_ca:
            ambiente["PORTAL_CA_ARQUIVO"] = self.arquivo_ca
        if self.permitir_http:
            ambiente["PORTAL_PERMITIR_HTTP"] = "1"
        return ambiente


def trabalhar(instancia: Instancia, executar: Callable[[Job, dict[str, str]], None], *,
              parar: Callable[[], bool] = lambda: False, avisar: Callable[[str], None] = print,
              espera_aprovacao_s: float = 30.0,
              declaracao: dict[str, Any] | Callable[[], dict[str, Any]] | None = None) -> None:
    """Espera jobs para sempre (ou até ``parar()``), um por vez, e entrega cada um a ``executar``.

    ``declaracao`` (ou uma função que a monta na hora): enviada assim que a instância puder
    receber jobs, e de novo se ela voltar a ser aprovada. Declaração recusada é avisada e o
    trabalho segue (o Portal continua com o que já tinha)."""
    pausa = 2.0
    ultimo_status = None
    declarada = False
    while not parar():
        try:
            situacao = instancia.status()
            if situacao["status"] != ultimo_status:
                avisar(f"instância {instancia.id}: {situacao['status']}"
                       + ("" if situacao.get("recebe_jobs") else " (sem jobs: aguardando o administrador)"))
                ultimo_status = situacao["status"]
            if not situacao.get("recebe_jobs"):
                declarada = False
                time.sleep(espera_aprovacao_s)
                continue
            if declaracao is not None and not declarada:
                declarada = _declarar(instancia, declaracao, avisar)
            job = instancia.proximo_job()
            pausa = 2.0
            if job is None:
                continue
            avisar(f"job {job.job_id}: {len(job.itens)} item(ns), parâmetros {job.parametros}")
            executar(job, instancia.ambiente_do_job(job))
        except Recusado as exc:
            avisar(f"Portal recusou a instância: {exc}. Confira se ela foi revogada.")
            time.sleep(espera_aprovacao_s)
        except FalhaDeTransporte as exc:
            avisar(f"Portal indisponível ({exc}); tentando de novo em {pausa:.0f} s")
            time.sleep(pausa)
            pausa = min(pausa * 2, 60.0)


def _declarar(instancia: Instancia, declaracao: Any, avisar: Callable[[str], None]) -> bool:
    """``True`` quando não precisa tentar de novo (enviada ou recusada); a falha de rede volta."""
    try:
        dados = declaracao() if callable(declaracao) else declaracao
        resposta = instancia.declarar(dados)
    except Recusado as exc:
        avisar(f"declaração recusada: {exc}")
        return True
    except FalhaDeTransporte:
        raise
    except Exception as exc:  # montar a declaração falhou: avisa e segue trabalhando
        avisar(f"declaração não montada: {exc.__class__.__name__}: {exc}")
        return True
    novos = (resposta.get("entrada") or {}).get("novos") or []
    fora = (resposta.get("entrada") or {}).get("fora_de_uso") or []
    tabela = resposta.get("tabela")
    partes = [f"{len(novos)} campo(s) novo(s)" if novos else "", f"{len(fora)} fora de uso" if fora else "",
              f"tabela: {tabela['novos']} novo(s), {tabela['alterados']} alterado(s) para aprovar" if tabela
              and (tabela["novos"] or tabela["alterados"]) else ""]
    avisar("declaração enviada" + (": " + "; ".join(p for p in partes if p) if any(partes) else ": nada mudou"))
    return True


# -- HTTP ------------------------------------------------------------------------------------

def contexto_tls(arquivo_ca: str | None) -> ssl.SSLContext:
    contexto = ssl.create_default_context(cafile=arquivo_ca)
    contexto.minimum_version = ssl.TLSVersion.TLSv1_2
    contexto.check_hostname = True
    contexto.verify_mode = ssl.CERT_REQUIRED
    return contexto


def _validar_url(url: str) -> str:
    return validar_url_portal(url)


def _pedir(tls: ssl.SSLContext | None, metodo: str, url: str, corpo: Any = None, token: str | None = None) -> dict[str, Any]:
    cabecalhos = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"
    dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8") if corpo is not None else None
    pedido = urllib.request.Request(url, data=dados, method=metodo, headers=cabecalhos)
    try:
        with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE_S, context=tls) as resposta:
            texto = resposta.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 401, 403, 404, 409, 413, 415, 422):
            raise Recusado(f"Portal recusou ({exc.code}): {_motivo(exc)}") from exc
        raise FalhaDeTransporte(f"Portal respondeu {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise FalhaDeTransporte(f"Portal indisponível ({exc.__class__.__name__}: {getattr(exc, 'reason', exc)})") from exc
    return json.loads(texto) if texto else {}


def _motivo(exc: urllib.error.HTTPError) -> str:
    try:
        return str(json.loads(exc.read()).get("erro") or exc.reason)
    except (ValueError, OSError):
        return str(exc.reason)


# -- DPAPI (escopo do usuário) -----------------------------------------------------------------

def proteger(dados: bytes) -> bytes:
    return _dpapi(dados, cifrar=True)


def desproteger(dados: bytes) -> bytes:
    return _dpapi(dados, cifrar=False)


def _dpapi(dados: bytes, *, cifrar: bool) -> bytes:
    if sys.platform != "win32":
        raise OSError("a credencial da instância usa o DPAPI do Windows")
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def blob(b: bytes) -> tuple[Blob, Any]:
        buffer = ctypes.create_string_buffer(b, len(b))
        return Blob(len(b), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer

    entrada, _b1 = blob(dados)
    entropia, _b2 = blob(ENTROPIA)
    saida = Blob()
    sem_interface = 0x1  # CRYPTPROTECT_UI_FORBIDDEN; sem LOCAL_MACHINE: escopo do usuário
    crypt32 = ctypes.windll.crypt32
    if cifrar:
        ok = crypt32.CryptProtectData(ctypes.byref(entrada), ctypes.c_wchar_p("portal-automacoes"), ctypes.byref(entropia),
                                      None, None, sem_interface, ctypes.byref(saida))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(entrada), None, ctypes.byref(entropia), None, None, sem_interface,
                                        ctypes.byref(saida))
    if not ok:
        raise OSError(f"DPAPI falhou ({ctypes.GetLastError()}): a credencial é de outro usuário ou outra máquina?")
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(saida.pbData)
