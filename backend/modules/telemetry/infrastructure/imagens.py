"""Conferência e versões das imagens dos passos (Pillow).

O Portal não confia no que chega: confere de novo o que o SDK já conferiu, porque a
automação pode não usar o SDK. Re-salva as três medidas sem metadados (EXIF pode levar
nome da máquina, usuário ou local).
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from modules.telemetry.domain.imagens import ImagemInvalida

LIMITE_BYTES = 4 * 1024 * 1024
LIMITE_PIXELS = 40_000_000          # 8K x 5K; acima disso é bomba de descompressão
LARGURAS = {"cheia": 1920, "media": 960, "miniatura": 320}
QUALIDADES = {"cheia": 82, "media": 78, "miniatura": 70}


@dataclass(frozen=True)
class ImagemProcessada:
    largura: int
    altura: int
    versoes: dict[str, bytes]


def processar(conteudo: bytes) -> ImagemProcessada:
    from PIL import Image, UnidentifiedImageError

    if len(conteudo) > LIMITE_BYTES:
        raise ImagemInvalida(413, f"imagem acima de {LIMITE_BYTES // (1024 * 1024)} MB")
    if not conteudo.startswith(b"\xff\xd8\xff"):
        raise ImagemInvalida(422, "não é um JPEG")
    try:
        with Image.open(io.BytesIO(conteudo)) as conferida:
            if conferida.format != "JPEG":
                raise ImagemInvalida(422, "não é um JPEG")
            if conferida.width * conferida.height > LIMITE_PIXELS:
                raise ImagemInvalida(413, "imagem com pixels demais")
            conferida.verify()
        imagem = Image.open(io.BytesIO(conteudo))
        imagem.load()
    except ImagemInvalida:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise ImagemInvalida(422, "imagem corrompida") from exc
    if imagem.width < 8 or imagem.height < 8:
        raise ImagemInvalida(422, "imagem pequena demais")
    minimo, maximo = imagem.convert("L").getextrema()
    if maximo - minimo < 4:
        raise ImagemInvalida(422, "imagem vazia ou de uma cor só")

    rgb = imagem.convert("RGB")
    versoes: dict[str, bytes] = {}
    for nome, largura in LARGURAS.items():
        versao = rgb if rgb.width <= largura else rgb.resize((largura, max(round(rgb.height * largura / rgb.width), 1)))
        saida = io.BytesIO()
        versao.save(saida, "JPEG", quality=QUALIDADES[nome], optimize=True)  # sem exif=: sai sem metadados
        versoes[nome] = saida.getvalue()
    return ImagemProcessada(imagem.width, imagem.height, versoes)
