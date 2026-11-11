"""Grava os campos de entrada de uma automação a partir do manifesto dela (no servidor do Portal).

    .venv\\Scripts\\python -m tools.campos_da_automacao 1 "C:\\...\\Integração contabil\\portal\\automacao.json"

Serve para automação cadastrada antes de o manifesto ter ``parametros`` (Fase 7): a versão
já publicada não tem os campos e a janela Executar não pede nada. As colunas dos itens ficam
como estão. Fica na auditoria (``automacao.campos.alterados``, ator ``system``), como se
alguém tivesse salvo na aba Campos. Se a automação já tem campos de entrada, só troca com
``--substituir``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from infrastructure.database import SessionLocal
from modules.catalog.domain.formulario import validar_campos
from modules.catalog.infrastructure.orm.models import CatalogAutomationRecord
from modules.catalog.infrastructure.repositories.sqlalchemy_itens import SqlAlchemyItemRegistry
from modules.governance.domain.audit import AuditEvent
from modules.governance.infrastructure.adapters import build_governance_adapters


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("automation_id", type=int)
    p.add_argument("manifesto", type=Path)
    p.add_argument("--substituir", action="store_true", help="troca campos de entrada que já existem")
    a = p.parse_args(argv)

    manifesto = json.loads(a.manifesto.read_text(encoding="utf-8"))
    entrada = validar_campos(manifesto.get("parametros") or manifesto.get("parameters") or [])
    if not entrada:
        print("O manifesto não tem 'parametros': nada a gravar.")
        return 1
    with SessionLocal() as db:
        automacao = db.get(CatalogAutomationRecord, a.automation_id)
        if automacao is None:
            print(f"Automação {a.automation_id} não encontrada.")
            return 1
        registro = SqlAlchemyItemRegistry(db)
        antes = registro.formulario(a.automation_id)
        if antes.entrada and not a.substituir:
            print(f"{automacao.name} já tem campos de entrada: {[c.chave for c in antes.entrada]}. Use --substituir.")
            return 1
        versao = registro.gravar_formulario(a.automation_id, entrada, antes.colunas, "sistema: campos_da_automacao")
        build_governance_adapters(db).audit.append(AuditEvent(
            id=f"aud_{uuid4().hex}", actor_type="system", actor_id=None, action="automacao.campos.alterados",
            resource_type="automation", resource_id=str(a.automation_id),
            before={"entrada": [c.publico() for c in antes.entrada], "colunas": [c.publico() for c in antes.colunas],
                    "origem": antes.origem},
            after={"entrada": [c.publico() for c in entrada], "colunas": [c.publico() for c in antes.colunas],
                   "versao": versao, "fonte": str(a.manifesto.name)},
            occurred_at=datetime.now(UTC)))
        db.commit()
        print(f"{automacao.name}: campos de entrada gravados (versão {versao}): "
              + ", ".join(f"{c.rotulo} ({c.chave})" for c in entrada))
        print(f"Colunas dos itens mantidas: {', '.join(c.chave for c in antes.colunas) or 'nenhuma'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
