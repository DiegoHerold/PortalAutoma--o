"""Endereço do Portal no modo direto.

Regra (ADR-018): HTTPS com TLS 1.2+ e certificado sempre validado. A exceção é
**provisória e explícita** (decisão de 11/11/2026: "não precisa usar https vindo da
automação por enquanto"): com ``permitir_http``, aceita ``http://`` só para um endereço da
rede interna (IP privado ou de loopback, nome de máquina sem domínio, ``.local`` ou
``.intranet.biason.net``). Endereço público em HTTP é sempre recusado. Credencial nunca
vai na URL.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

DOMINIOS_INTERNOS = (".local", ".intranet.biason.net")


def endereco_interno(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        nome = host.lower().rstrip(".")
        return "." not in nome or nome.endswith(DOMINIOS_INTERNOS)
    return ip.is_private or ip.is_loopback


def validar_url_portal(url: str, permitir_http: bool = False) -> str:
    partes = urlsplit(url)
    if not partes.hostname or partes.scheme not in ("https", "http"):
        raise ValueError("o modo direto só aceita https://")
    if partes.query or partes.username or partes.password:
        raise ValueError("a URL do Portal não pode ter credenciais nem parâmetros")
    if partes.scheme == "http":
        if not permitir_http:
            raise ValueError("o modo direto só aceita https:// (http só com permitir_http, na rede interna)")
        if not endereco_interno(partes.hostname):
            raise ValueError("http:// só é aceito para um endereço da rede interna")
    return url.rstrip("/")


def usa_http(url: str) -> bool:
    return urlsplit(url).scheme == "http"


def ligado(valor: str | None) -> bool:
    return (valor or "").strip().lower() in ("1", "true", "sim", "yes")
