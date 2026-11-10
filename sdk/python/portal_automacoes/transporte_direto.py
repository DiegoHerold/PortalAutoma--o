"""Modo direto: a automação fala direto com o Portal, só por HTTPS de saída.

Regras (ADR-018): só HTTPS, TLS 1.2 ou superior, certificado sempre validado (pela CA da
empresa no repositório do Windows ou por um arquivo de CA). Não existe opção para desligar
a validação. O token do job vai no cabeçalho, nunca na URL.

Nesta versão a automação recebe o job pronto (URL, id e token do job). A inscrição da
instância, o desafio assinado e o pedido de jobs entram na Fase 6.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import quote, urlsplit

from .transporte import FalhaDeTransporte, Recusado

TEMPO_LIMITE_S = 20.0


class TransporteDireto:
    nome = "direto"

    def __init__(self, url: str, job_id: str, token_job: str, arquivo_ca: str | None = None,
                 tempo_limite_s: float = TEMPO_LIMITE_S) -> None:
        partes = urlsplit(url)
        if partes.scheme != "https" or not partes.hostname:
            raise ValueError("o modo direto só aceita https://")
        if partes.query or partes.username or partes.password:
            raise ValueError("a URL do Portal não pode ter credenciais nem parâmetros")
        if not job_id or not token_job:
            raise ValueError("modo direto sem PORTAL_JOB_ID ou PORTAL_JOB_TOKEN")
        self._base = f"{url.rstrip('/')}/api/v1/direto/jobs/{quote(job_id, safe='')}"
        self._token = token_job
        self._tempo_limite_s = tempo_limite_s
        self._tls = ssl.create_default_context(cafile=arquivo_ca)
        self._tls.minimum_version = ssl.TLSVersion.TLSv1_2
        self._tls.check_hostname = True
        self._tls.verify_mode = ssl.CERT_REQUIRED
        self.recusados: list[dict[str, Any]] = []

    def conectar(self) -> int:
        resposta = self._pedir("GET", "/eventos/estado")
        return int(resposta.get("ultima_sequencia") or 0)

    def enviar(self, eventos: list[dict[str, Any]]) -> int:
        resposta = self._pedir("POST", "/eventos", {"eventos": eventos})
        # Evento recusado é consumido (não volta para a fila) e informado aqui.
        self.recusados += [r for r in resposta.get("recusados") or [] if isinstance(r, dict)]
        return int(resposta.get("ultima_sequencia") or 0)

    def comandos(self) -> list[dict[str, Any]]:
        resposta = self._pedir("GET", "/comandos?espera=0")
        comandos = resposta.get("comandos") or []
        return [c for c in comandos if isinstance(c, dict)]

    def enviar_imagem(self, imagem_id: str, jpeg: bytes) -> None:
        self._pedir("PUT", f"/imagens/{quote(imagem_id, safe='')}", corpo_bruto=jpeg, tipo="image/jpeg")

    def fechar(self) -> None:
        return None

    def _pedir(self, metodo: str, caminho: str, corpo: Any = None, corpo_bruto: bytes | None = None,
               tipo: str = "application/json") -> dict[str, Any]:
        dados = corpo_bruto if corpo_bruto is not None else (
            json.dumps(corpo, ensure_ascii=False).encode("utf-8") if corpo is not None else None)
        pedido = urllib.request.Request(self._base + caminho, data=dados, method=metodo, headers={
            "Authorization": f"Bearer {self._token}",
            "Content-Type": tipo,
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(pedido, timeout=self._tempo_limite_s, context=self._tls) as resposta:
                texto = resposta.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 401, 403, 404, 409, 413, 415, 422):
                raise Recusado(f"Portal recusou ({exc.code}): {_motivo(exc)}") from exc
            raise FalhaDeTransporte(f"Portal respondeu {exc.code}") from exc
        except (urllib.error.URLError, OSError) as exc:
            # Inclui certificado inválido: a conexão não acontece, e o evento fica na fila.
            raise FalhaDeTransporte(f"Portal indisponível ({exc.__class__.__name__}: {getattr(exc, 'reason', exc)})") from exc
        return json.loads(texto) if texto else {}


def _motivo(exc: urllib.error.HTTPError) -> str:
    try:
        return str(json.loads(exc.read()).get("erro") or exc.reason)
    except (ValueError, OSError):
        return str(exc.reason)
