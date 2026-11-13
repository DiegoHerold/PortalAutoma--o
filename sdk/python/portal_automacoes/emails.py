"""E-mail pelo Portal (0.5.0): o padrão é a automação pedir e o Portal mandar.

    a.email("analista@cliente.com.br", "Folha 10/2026", html="<p>...</p>", anexos=["resultado.csv"])

- Modo direto: ``POST .../emails`` com o token do job; o Portal manda pelo Microsoft Graph, só
  para domínios permitidos, e guarda o registro (tela E-mails). Domínio fora da lista ou anexo
  proibido: ``EmailRecusado`` (fica registrado no Portal com o motivo).
- Mandou pela máquina (Outlook, SMTP)? Avise com ``a.email_enviado_pela_maquina(...)``: o Portal
  só registra. Se o Portal não responder, o aviso não derruba a automação.
- Modo desligado (desenvolvimento): não manda nada; escreve no log local.
- Modo agente: o Agent ainda não leva e-mails; ``EmailIndisponivel``.

Campos ocultos de segredos viram ``***`` também no assunto e no corpo do e-mail.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

LIMITE_DOS_ANEXOS = int(2.5 * 1024 * 1024)


class EmailRecusado(ValueError):
    """O Portal recusou (domínio não permitido, anexo proibido, dados inválidos). O motivo vem na mensagem."""


class EmailIndisponivel(RuntimeError):
    """Não deu para pedir agora (Portal fora do ar, execução encerrada, modo agente)."""


def lista(valor: Any) -> list[str]:
    if valor is None:
        return []
    if isinstance(valor, str):
        return [valor]
    return [str(v) for v in valor]


def ler_anexos(anexos: Any) -> list[dict[str, str]]:
    """Caminhos de arquivo ou (nome, bytes). Confere o total antes de mandar."""
    saida: list[dict[str, str]] = []
    total = 0
    for anexo in anexos or []:
        if isinstance(anexo, tuple):
            nome, conteudo = str(anexo[0]), bytes(anexo[1])
        else:
            caminho = Path(anexo)
            nome, conteudo = caminho.name, caminho.read_bytes()
        total += len(conteudo)
        if total > LIMITE_DOS_ANEXOS:
            raise EmailRecusado("anexos acima de 2,5 MB no total: entregue com a.arquivo() e mande o link")
        saida.append({"nome": nome, "tipo": mimetypes.guess_type(nome)[0] or "application/octet-stream",
                      "conteudo_base64": base64.b64encode(conteudo).decode("ascii")})
    return saida
