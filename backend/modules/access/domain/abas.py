"""Nome do papel em slug ("Analista Fiscal" -> "analista-fiscal"). As abas da etapa anterior viraram
``domain.funcionalidades``."""

from __future__ import annotations

import re
import unicodedata

from modules.access.domain.funcionalidades import FuncionalidadeInvalida


def slug_do_nome(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")
    if not slug:
        raise FuncionalidadeInvalida("o nome precisa de letras ou números")
    return slug[:50]
