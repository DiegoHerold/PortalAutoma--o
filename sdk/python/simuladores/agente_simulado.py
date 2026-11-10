"""Agent simulado: faz o papel do Agent Service e roda o ExecutionHost.exe REAL.

Prepara o workspace e a configuração como o ExecutionManager faz, abre o pipe do Agent,
lança o ExecutionHost, que lança a automação, e recebe as mensagens do host. Cada
``automation.event`` vira um ``execution.event.batch`` igual ao que o OutboxMessagePublisher
monta para o Portal (event_type ``automation.event`` e o evento intacto no payload).

O que é simulado: só o Agent Service (sem SQLite, sem WebSocket com o Portal).
O que é real: ExecutionHost.exe, o canal de eventos (named pipe com token) e o SDK.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pipes_windows import ServidorPipe

RAIZ_REPO = Path(__file__).resolve().parents[3]
EXECUTION_HOST = RAIZ_REPO / "automation-agent" / "src" / "Agent.ExecutionHost" / "bin" / "Debug" / "net8.0" / "win-x64" / "ExecutionHost.exe"


@dataclass
class ResultadoAgente:
    codigo_saida: int
    mensagens_host: list[dict[str, Any]]
    lotes: list[dict[str, Any]] = field(default_factory=list)
    pasta_artefatos: Path | None = None
    stdout_automacao: str = ""

    @property
    def eventos(self) -> list[dict[str, Any]]:
        """Eventos da automação na ordem em que o Portal os receberia."""
        return [e["payload"] for lote in self.lotes for e in lote["payload"]["events"]]


class AgenteSimulado:
    def __init__(self, python: Path, pasta: Path, execution_host: Path = EXECUTION_HOST) -> None:
        if not execution_host.is_file():
            raise FileNotFoundError(f"ExecutionHost não compilado: {execution_host} (rode dotnet build)")
        self.python = python
        self.pasta = pasta
        self.execution_host = execution_host
        self.execution_id = f"exe_sim_{uuid.uuid4().hex[:8]}"
        self.attempt_id = f"att_sim_{uuid.uuid4().hex[:8]}"

    def executar(self, pacote: Path, modulo: str, ambiente: dict[str, str] | None = None,
                 timeout_s: int = 120) -> ResultadoAgente:
        ws = self.pasta / self.attempt_id
        caminhos = {nome: ws / nome for nome in ("input", "output", "artifacts", "temp", "logs")}
        for caminho in caminhos.values():
            caminho.mkdir(parents=True, exist_ok=True)
        (caminhos["input"] / "input.json").write_text("{}", encoding="utf-8")

        nome_pipe = f"biason-sim-agent-{uuid.uuid4().hex}"
        servidor = ServidorPipe(nome_pipe)
        mensagens: list[dict[str, Any]] = []

        def receber() -> None:
            servidor.aceitar()
            for linha in servidor.linhas():
                if linha.strip():
                    mensagens.append(json.loads(linha))

        leitor = threading.Thread(target=receber, daemon=True)
        leitor.start()

        config = {
            "execution_id": self.execution_id,
            "attempt_id": self.attempt_id,
            "automation_id": "automacao-exemplo",
            "mode": "background",
            "pipe_name": nome_pipe,
            "token": uuid.uuid4().hex,
            "entrypoint": {"type": "python_module", "executable_path": str(self.python), "module": modulo},
            "paths": {
                "runtime_path": str(self.python.parent),
                "package_path": str(pacote),
                "workspace_path": str(ws),
                "input_path": str(caminhos["input"]),
                "output_path": str(caminhos["output"]),
                "artifacts_path": str(caminhos["artifacts"]),
                "temp_path": str(caminhos["temp"]),
                "logs_path": str(caminhos["logs"]),
            },
            "timeout_seconds": timeout_s,
            "graceful_shutdown_seconds": 5,
            "environment": ambiente or {},
        }
        arquivo_config = ws / "host-config.json"
        arquivo_config.write_text(json.dumps(config), encoding="utf-8")

        processo = subprocess.run([str(self.execution_host), "--config", str(arquivo_config)],
                                  capture_output=True, timeout=timeout_s + 30, check=False)
        leitor.join(timeout=10)
        servidor.fechar()

        stdout = caminhos["logs"] / "stdout.log"
        resultado = ResultadoAgente(processo.returncode, mensagens, pasta_artefatos=caminhos["artifacts"],
                                    stdout_automacao=stdout.read_text(encoding="utf-8", errors="replace") if stdout.exists() else "")
        sequencia = 0
        for mensagem in mensagens:
            if mensagem.get("message_type") != "automation.event":
                continue
            sequencia += 1
            resultado.lotes.append(_lote(self.attempt_id, sequencia, mensagem["payload"]))
        return resultado


def _lote(attempt_id: str, sequencia: int, evento: dict[str, Any]) -> dict[str, Any]:
    """Mesmo formato do OutboxMessagePublisher.ToEventBatch."""
    message_id = str(uuid.uuid4())
    return {
        "message_id": message_id,
        "message_type": "execution.event.batch",
        "payload": {
            "execution_attempt_id": attempt_id,
            "events": [{
                "event_id": f"{message_id}:1",
                "event_sequence": sequencia,
                "event_type": "automation.event",
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "payload": evento,
            }],
        },
    }


def montar_pacote(destino: Path, *modulos: Path) -> Path:
    """Pacote da automação com o SDK junto, como uma automação real distribuiria."""
    destino.mkdir(parents=True, exist_ok=True)
    sdk = Path(__file__).resolve().parents[1] / "portal_automacoes"
    shutil.copytree(sdk, destino / "portal_automacoes", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    for modulo in modulos:
        shutil.copy2(modulo, destino / modulo.name)
    return destino
