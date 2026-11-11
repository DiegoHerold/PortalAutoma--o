"""Regras das imagens dos passos que não dependem de biblioteca de imagem."""

from __future__ import annotations

import re

# O SDK gera ``img_`` + 32 hexadecimais; o Portal aceita qualquer id curto e seguro para
# compor o caminho no Storage (nada de barra, ponto-ponto ou espaço).
FORMATO_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")
TAMANHOS = ("miniatura", "media", "cheia")
BUCKET = "imagens-passos"


class ImagemInvalida(ValueError):
    """Recusa com o código HTTP do contrato: 413 grande demais, 422 vazia ou corrompida."""

    def __init__(self, status: int, motivo: str) -> None:
        super().__init__(motivo)
        self.status = status
        self.motivo = motivo


def id_valido(imagem_id: str) -> bool:
    return bool(FORMATO_ID.fullmatch(imagem_id or ""))


def chave_no_storage(execution_id: str, attempt_id: str, imagem_id: str, tamanho: str) -> str:
    if not id_valido(imagem_id) or tamanho not in TAMANHOS:
        raise ImagemInvalida(422, "imagem_id ou tamanho inválido")
    return f"{execution_id}/{attempt_id}/{imagem_id}/{tamanho}.jpg"
