"""Portal simulado para o modo direto: só a API que a automação usa, em HTTPS.

Implementa o contrato de contracts/automation-events/v1/README.md (seção "Modo direto")
com as mesmas regras que o Portal real vai aplicar: token do job no cabeçalho, um job
por token, idempotência por sequência, limite de tamanho, validação de cada evento pela
função recebida (nos testes, o validador do próprio Portal) e imagem conferida.
"""

from __future__ import annotations

import hmac
import io
import json
import re
import ssl
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

LIMITE_CORPO = 1_000_000
LIMITE_IMAGEM = 5_000_000
ROTA = re.compile(r"^/api/v1/direto/jobs/(?P<job>[A-Za-z0-9_-]{1,80})/(?P<recurso>eventos/estado|eventos|comandos|imagens/(?P<imagem>[A-Za-z0-9_-]{1,80}))$")


@dataclass
class JobSimulado:
    token: str
    eventos: list[dict[str, Any]] = field(default_factory=list)
    recusados: list[dict[str, Any]] = field(default_factory=list)
    imagens: dict[str, bytes] = field(default_factory=dict)
    comandos: list[dict[str, Any]] = field(default_factory=list)
    ultima_sequencia: int = 0


class PortalSimulado:
    def __init__(self, certificado: Path | None, chave: Path | None, validar: Callable[[dict[str, Any]], Any]) -> None:
        """Sem certificado: HTTP puro (só para testar o modo provisório sem TLS na rede interna)."""
        self.jobs: dict[str, JobSimulado] = {}
        self.recusas_autenticacao = 0
        self._validar = validar
        self._lock = threading.Lock()
        self._servidor = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._esquema = "http"
        if certificado is not None:
            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            tls.minimum_version = ssl.TLSVersion.TLSv1_2
            tls.load_cert_chain(certificado, chave)
            self._servidor.socket = tls.wrap_socket(self._servidor.socket, server_side=True)
            self._esquema = "https"
        self._thread = threading.Thread(target=self._servidor.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"{self._esquema}://127.0.0.1:{self._servidor.server_address[1]}"  # localhost tentaria ::1 antes, 2 s por conexão

    def criar_job(self, job_id: str, token: str) -> JobSimulado:
        self.jobs[job_id] = JobSimulado(token)
        return self.jobs[job_id]

    def __enter__(self) -> "PortalSimulado":
        self._thread.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self._servidor.shutdown()
        self._servidor.server_close()

    def _handler(self):
        portal = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_: Any) -> None:  # sem log de acesso: os testes leem a saída
                return

            def _responder(self, codigo: int, corpo: dict[str, Any]) -> None:
                dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
                self.send_response(codigo)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)

            def _job(self) -> tuple[JobSimulado, re.Match[str]] | None:
                caminho, _, consulta = self.path.partition("?")
                rota = ROTA.match(caminho)
                if rota is None:
                    self._responder(404, {"erro": "rota inexistente"})
                    return None
                job = portal.jobs.get(rota["job"])
                enviado = (self.headers.get("Authorization") or "").removeprefix("Bearer ")
                if job is None or not hmac.compare_digest(enviado.encode(), job.token.encode()):
                    portal.recusas_autenticacao += 1
                    self._responder(401, {"erro": "token do job inválido para este job"})
                    return None
                return job, rota

            def _corpo(self, limite: int) -> bytes | None:
                tamanho = int(self.headers.get("Content-Length") or 0)
                if tamanho > limite:
                    self._responder(413, {"erro": f"corpo acima de {limite} bytes"})
                    return None
                return self.rfile.read(tamanho)

            def do_GET(self) -> None:  # noqa: N802
                achado = self._job()
                if achado is None:
                    return
                job, rota = achado
                if rota["recurso"] == "eventos/estado":
                    return self._responder(200, {"ultima_sequencia": job.ultima_sequencia})
                if rota["recurso"] == "comandos":
                    with portal._lock:
                        comandos, job.comandos = job.comandos, []
                    return self._responder(200, {"comandos": comandos})
                self._responder(405, {"erro": "método não permitido"})

            def do_POST(self) -> None:  # noqa: N802
                achado = self._job()
                if achado is None:
                    return
                job, rota = achado
                if rota["recurso"] != "eventos":
                    return self._responder(405, {"erro": "método não permitido"})
                if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                    return self._responder(415, {"erro": "envie application/json"})
                corpo = self._corpo(LIMITE_CORPO)
                if corpo is None:
                    return
                try:
                    lote = json.loads(corpo)
                    eventos = lote["eventos"]
                    assert isinstance(eventos, list) and 1 <= len(eventos) <= 500
                except (ValueError, KeyError, TypeError, AssertionError):
                    return self._responder(400, {"erro": "lote fora do contrato"})
                recusados = []
                with portal._lock:
                    for evento in eventos:
                        sequencia = evento.get("sequence") if isinstance(evento, dict) else None
                        if not isinstance(sequencia, int) or sequencia <= job.ultima_sequencia:
                            continue  # repetido: idempotente
                        try:
                            portal._validar(evento)
                        except Exception as exc:  # noqa: BLE001 - recusa registrada, o resto do lote segue
                            recusados.append({"sequence": sequencia, "motivo": str(exc)[:300]})
                            job.recusados.append(evento)
                        else:
                            job.eventos.append(evento)
                        job.ultima_sequencia = sequencia
                    ultima = job.ultima_sequencia
                self._responder(200, {"ultima_sequencia": ultima, "recusados": recusados})

            def do_PUT(self) -> None:  # noqa: N802
                achado = self._job()
                if achado is None:
                    return
                job, rota = achado
                if not rota["imagem"]:
                    return self._responder(405, {"erro": "método não permitido"})
                if self.headers.get("Content-Type") != "image/jpeg":
                    return self._responder(415, {"erro": "envie image/jpeg"})
                corpo = self._corpo(LIMITE_IMAGEM)
                if corpo is None:
                    return
                from PIL import Image

                try:
                    with Image.open(io.BytesIO(corpo)) as imagem:
                        imagem.verify()
                    with Image.open(io.BytesIO(corpo)) as imagem:
                        minimo, maximo = imagem.convert("L").getextrema()
                except Exception:  # noqa: BLE001
                    return self._responder(422, {"erro": "imagem corrompida"})
                if maximo - minimo < 4:
                    return self._responder(422, {"erro": "imagem vazia"})
                job.imagens[rota["imagem"]] = corpo
                self._responder(201, {"imagem_id": rota["imagem"]})

        return Handler
