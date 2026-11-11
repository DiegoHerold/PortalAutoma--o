"""Instância direta no SDK: credencial protegida pelo DPAPI e regras de URL."""

from __future__ import annotations

import sys

import pytest

from portal_automacoes.instancia import Instancia, desproteger, proteger


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI só existe no Windows")
def test_dpapi_ida_e_volta_e_o_cifrado_nao_contem_o_original() -> None:
    segredo = b"chave-privada-de-teste" * 4
    cifrado = proteger(segredo)
    assert segredo not in cifrado and desproteger(cifrado) == segredo
    with pytest.raises(OSError):
        desproteger(cifrado[:-4] + b"xxxx")  # adulterado


@pytest.mark.parametrize("url", ["http://portal:8000", "https://usuario:senha@portal", "https://portal?token=x", "portal"])
def test_url_do_portal_so_https_sem_credencial(url: str) -> None:
    from cryptography.hazmat.primitives.asymmetric import ec

    with pytest.raises(ValueError):
        Instancia(url, "dri_1", ec.generate_private_key(ec.SECP256R1()), None)
