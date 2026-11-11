"""Chave pública e assinatura da instância direta: ECDSA P-256 com SHA-256, nada mais."""

from __future__ import annotations

import base64
import binascii

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

LIMITE_PEM = 1024


class ChaveInvalida(ValueError):
    pass


def validar_chave_publica(pem: str) -> str:
    """Devolve a chave em PEM normalizado. Só P-256: outra curva ou outro tipo é recusado."""
    if not isinstance(pem, str) or not pem.strip() or len(pem) > LIMITE_PEM:
        raise ChaveInvalida("chave pública ausente ou grande demais")
    try:
        chave = serialization.load_pem_public_key(pem.encode("ascii"))
    except (ValueError, UnicodeEncodeError, TypeError) as exc:
        raise ChaveInvalida("chave pública ilegível") from exc
    if not isinstance(chave, ec.EllipticCurvePublicKey) or not isinstance(chave.curve, ec.SECP256R1):
        raise ChaveInvalida("a chave precisa ser ECDSA P-256")
    return chave.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii")


def assinatura_confere(pem: str, mensagem: bytes, assinatura_b64: str) -> bool:
    try:
        assinatura = base64.b64decode(assinatura_b64, validate=True)
        chave = serialization.load_pem_public_key(pem.encode("ascii"))
        if not isinstance(chave, ec.EllipticCurvePublicKey) or not isinstance(chave.curve, ec.SECP256R1):
            return False
        chave.verify(assinatura, mensagem, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError, binascii.Error, TypeError):
        return False
