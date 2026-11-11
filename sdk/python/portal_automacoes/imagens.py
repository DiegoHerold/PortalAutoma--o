"""Conferência e preparo das imagens dos passos.

Imagem vazia, de uma cor só ou corrompida nunca sai da máquina. Precisa do Pillow
(``pip install portal-automacoes-sdk[imagens]``).
"""

from __future__ import annotations

import io
import uuid
from typing import Any

LARGURA_MAXIMA = 1920
QUALIDADE = 80


class ImagemRecusada(ValueError):
    pass


def novo_id() -> str:
    return f"img_{uuid.uuid4().hex}"


def preparar(imagem: Any) -> bytes:
    """JPEG pronto para envio. Aceita uma imagem do Pillow ou os bytes de um arquivo de imagem."""
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:  # pragma: no cover - depende da instalação
        raise ImagemRecusada("imagens exigem o Pillow: pip install portal-automacoes-sdk[imagens]") from exc

    if isinstance(imagem, (bytes, bytearray)):
        try:
            with Image.open(io.BytesIO(imagem)) as conferida:
                conferida.verify()
            imagem = Image.open(io.BytesIO(imagem))
        except (UnidentifiedImageError, OSError, SyntaxError) as exc:
            raise ImagemRecusada("imagem corrompida ou em formato desconhecido") from exc
    if not isinstance(imagem, Image.Image):
        raise ImagemRecusada("passe uma imagem do Pillow ou os bytes de uma imagem")
    if imagem.width < 8 or imagem.height < 8:
        raise ImagemRecusada("imagem pequena demais")
    minimo, maximo = imagem.convert("L").getextrema()
    if maximo - minimo < 4:
        raise ImagemRecusada("imagem vazia ou de uma cor só")

    rgb = imagem.convert("RGB")
    if rgb.width > LARGURA_MAXIMA:
        rgb = rgb.resize((LARGURA_MAXIMA, round(rgb.height * LARGURA_MAXIMA / rgb.width)))
    saida = io.BytesIO()
    rgb.save(saida, "JPEG", quality=QUALIDADE, optimize=True)
    return saida.getvalue()
