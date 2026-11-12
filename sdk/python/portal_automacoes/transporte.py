"""Interface comum dos transportes. Trocar de modo não muda o código da automação."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class FalhaDeTransporte(RuntimeError):
    """Agent ou Portal indisponível. O evento fica na fila local e é reenviado depois."""


class Recusado(RuntimeError):
    """O receptor recusou definitivamente (credencial inválida, evento fora do contrato).
    ``codigo``: o status HTTP no modo direto (401/409: o Portal não aceita mais este job)."""

    def __init__(self, mensagem: str = "", codigo: int | None = None) -> None:
        super().__init__(mensagem)
        self.codigo = codigo


class Transporte(Protocol):
    nome: str

    def conectar(self) -> int:
        """Abre a conexão de saída. Devolve a última sequência que o receptor já tem."""

    def enviar(self, eventos: list[dict[str, Any]]) -> int:
        """Envia em ordem. Devolve a maior sequência confirmada."""

    def comandos(self) -> list[dict[str, Any]]:
        """Comandos pendentes (parar depois do item, cancelar)."""

    def enviar_imagem(self, imagem_id: str, jpeg: bytes) -> None:
        """Entrega a imagem fora do canal de eventos (arquivo local ou HTTPS)."""

    def enviar_arquivo(self, caminho: Path, nome: str, item: str | None, tipo: str) -> None:
        """Arquivo entregue pela automação (planilha, TXT...), fora do canal de eventos."""

    def fechar(self) -> None: ...


class TransporteDesligado:
    """Sem Portal nem Agent (desenvolvimento): os eventos são validados e descartados."""

    nome = "desligado"

    def conectar(self) -> int:
        return 0

    def enviar(self, eventos: list[dict[str, Any]]) -> int:
        return max((e["sequence"] for e in eventos), default=0)

    def comandos(self) -> list[dict[str, Any]]:
        return []

    def enviar_imagem(self, imagem_id: str, jpeg: bytes) -> None:
        return None

    def enviar_arquivo(self, caminho: Path, nome: str, item: str | None, tipo: str) -> None:
        return None

    def fechar(self) -> None:
        return None
