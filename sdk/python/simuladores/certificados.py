"""CA e certificado de servidor temporários, para testar TLS de verdade no modo direto."""

from __future__ import annotations

import datetime as dt
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def _salvar_chave(chave: ec.EllipticCurvePrivateKey, caminho: Path) -> None:
    caminho.write_bytes(chave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                            serialization.NoEncryption()))


def gerar(pasta: Path, nome_host: str = "localhost") -> tuple[Path, Path, Path]:
    """Devolve (ca.pem, servidor.pem, servidor-chave.pem)."""
    pasta.mkdir(parents=True, exist_ok=True)
    agora = dt.datetime.now(dt.timezone.utc)
    chave_ca = ec.generate_private_key(ec.SECP256R1())
    nome_ca = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "CA de teste do Portal")])
    ca = (x509.CertificateBuilder().subject_name(nome_ca).issuer_name(nome_ca).public_key(chave_ca.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(agora - dt.timedelta(minutes=5))
          .not_valid_after(agora + dt.timedelta(days=1))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True, content_commitment=False,
                                       key_encipherment=False, data_encipherment=False, key_agreement=False,
                                       encipher_only=False, decipher_only=False), critical=True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(chave_ca.public_key()), critical=False)
          .sign(chave_ca, hashes.SHA256()))
    chave = ec.generate_private_key(ec.SECP256R1())
    servidor = (x509.CertificateBuilder()
                .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nome_host)]))
                .issuer_name(nome_ca).public_key(chave.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(agora - dt.timedelta(minutes=5)).not_valid_after(agora + dt.timedelta(days=1))
                .add_extension(x509.SubjectAlternativeName([x509.DNSName(nome_host),
                                                            x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
                .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(chave_ca.public_key()), critical=False)
                .sign(chave_ca, hashes.SHA256()))
    caminho_ca, caminho_cert, caminho_chave = pasta / "ca.pem", pasta / "servidor.pem", pasta / "servidor-chave.pem"
    caminho_ca.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    caminho_cert.write_bytes(servidor.public_bytes(serialization.Encoding.PEM))
    _salvar_chave(chave, caminho_chave)
    return caminho_ca, caminho_cert, caminho_chave
