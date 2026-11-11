"""Cadastro de itens (``automation_items``) e o manifesto que define o item. Só o Catalog escreve."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from modules.catalog.domain.formulario import (
    Campo,
    Formulario,
    da_automacao,
    de_esquema_json,
    de_guardados,
    para_esquema_json,
    validar_campos,
)
from modules.catalog.domain.itens import Item
from modules.catalog.domain.manifest import ItemSpec, parse_automation_manifest
from modules.catalog.infrastructure.orm.models import (
    AutomationFormRecord,
    AutomationItemProposalRecord,
    AutomationItemRecord,
    CatalogAutomationVersionRecord,
)


class SqlAlchemyItemRegistry:
    def __init__(self, db: Session) -> None:
        self.db = db

    def manifesto(self, automation_id: int) -> dict[str, Any] | None:
        manifesto = self.db.scalar(select(CatalogAutomationVersionRecord.manifest)
                                   .where(CatalogAutomationVersionRecord.automation_id == automation_id)
                                   .order_by(CatalogAutomationVersionRecord.id.desc()).limit(1))
        return manifesto if isinstance(manifesto, dict) else None

    def spec(self, automation_id: int) -> Any:
        """``ItemSpec`` da automação. As colunas editadas no Portal (Fase 7) valem no lugar
        do schema do manifesto; o nome do item, a chave e o grupo continuam do manifesto."""
        base = self.spec_do_manifesto(automation_id)
        form = self.db.get(AutomationFormRecord, automation_id)
        if form is None:
            return base
        if base is None:  # sem itens no manifesto: vale o que a automação declarou ao conectar (Fase 8)
            if not form.item:
                return None
            base = ItemSpec(label=form.item.get("nome") or "Item", key=form.item.get("chave") or "chave",
                            group_attribute=form.item.get("grupo"))
        colunas = de_guardados(form.colunas)
        return ItemSpec(label=base.label, key=base.key, label_attribute=base.label_attribute,
                        group_attribute=base.group_attribute, attributes_schema=para_esquema_json(colunas),
                        work_attributes=tuple(c.chave for c in colunas if c.afeta_trabalho))

    def spec_do_manifesto(self, automation_id: int) -> Any:
        """``ItemSpec`` da versão mais recente da automação (None se ela não declara itens)."""
        manifesto = self.manifesto(automation_id)
        if not manifesto:
            return None
        normalizado = manifesto.get("items") if isinstance(manifesto, dict) else None
        if isinstance(normalizado, dict) and normalizado.get("key"):
            # Guardado já normalizado pelo Catalog (chaves em inglês).
            return ItemSpec(label=normalizado.get("label") or "Item", key=normalizado["key"],
                            label_attribute=normalizado.get("label_attribute"),
                            group_attribute=normalizado.get("group_attribute"),
                            attributes_schema=normalizado.get("attributes_schema"),
                            work_attributes=tuple(normalizado.get("work_attributes") or ()))
        lido, _ = parse_automation_manifest(json.dumps(manifesto))  # manifesto ainda no formato de origem
        return getattr(lido, "items", None) if lido is not None else None

    # -- campos da automação (Fase 7) ---------------------------------------------------------
    def formulario(self, automation_id: int) -> Formulario:
        """Campos em vigor: os do Portal, se alguém já editou; senão, os que o manifesto sugere."""
        form = self.db.get(AutomationFormRecord, automation_id)
        if form is not None:
            return Formulario(de_guardados(form.entrada), de_guardados(form.colunas), "portal")
        manifesto = self.manifesto(automation_id) or {}
        try:
            entrada = da_automacao(validar_campos(manifesto.get("parameters") or []))
        except ValueError:
            entrada = []
        spec = self.spec_do_manifesto(automation_id)
        colunas = de_esquema_json(spec.attributes_schema, spec.work_attributes) if spec is not None else []
        return Formulario(entrada, colunas, "manifesto")

    def item_da_automacao(self, automation_id: int) -> dict[str, Any] | None:
        """Nome, chave e grupo do item: do manifesto ou, sem ele, da declaração."""
        spec = self.spec(automation_id)
        return None if spec is None else {"nome": spec.label, "chave": spec.key, "grupo": spec.group_attribute}

    def versao_do_formulario(self, automation_id: int) -> int:
        form = self.db.get(AutomationFormRecord, automation_id)
        return form.versao if form is not None else 0

    def gravar_formulario(self, automation_id: int, entrada: list[Campo], colunas: list[Campo], por: str,
                          item: dict[str, Any] | None = None) -> int:
        form = self.db.get(AutomationFormRecord, automation_id)
        if form is None:
            form = AutomationFormRecord(automation_id=automation_id, versao=0)
            self.db.add(form)
        form.entrada = [c.publico() for c in entrada]
        form.colunas = [c.publico() for c in colunas]
        if item is not None:
            form.item = item
        form.versao = (form.versao or 0) + 1
        form.updated_by = por
        self.db.flush()
        return form.versao

    # -- tabela que a automação mandou (Fase 8) ---------------------------------------------------
    def guardar_proposta(self, automation_id: int, linhas: list[dict[str, Any]], resumo: dict[str, Any],
                         instancia_id: str | None, agora: datetime) -> None:
        proposta = self.db.get(AutomationItemProposalRecord, automation_id)
        if proposta is None:
            proposta = AutomationItemProposalRecord(automation_id=automation_id)
            self.db.add(proposta)
        proposta.linhas, proposta.resumo, proposta.instancia_id, proposta.recebida_em = linhas, resumo, instancia_id, agora
        self.db.flush()

    def proposta(self, automation_id: int) -> AutomationItemProposalRecord | None:
        return self.db.get(AutomationItemProposalRecord, automation_id)

    def descartar_proposta(self, automation_id: int) -> bool:
        proposta = self.db.get(AutomationItemProposalRecord, automation_id)
        if proposta is None:
            return False
        self.db.delete(proposta)
        self.db.flush()
        return True

    def todos(self, automation_id: int) -> dict[str, Item]:
        return {r.chave: _item(r) for r in self.db.scalars(
            select(AutomationItemRecord).where(AutomationItemRecord.automation_id == automation_id))}

    def listar(self, automation_id: int, *, busca: str | None, ativos: bool | None, limite: int,
               pular: int = 0) -> list[dict[str, Any]]:
        consulta = select(AutomationItemRecord).where(AutomationItemRecord.automation_id == automation_id)
        if busca:
            termo = f"%{busca.strip()}%"
            consulta = consulta.where(or_(AutomationItemRecord.chave.ilike(termo), AutomationItemRecord.rotulo.ilike(termo),
                                          AutomationItemRecord.grupo_chave.ilike(termo)))
        if ativos is not None:
            consulta = consulta.where(AutomationItemRecord.ativo.is_(ativos))
        # Matriz e filiais juntas: ordena pelo grupo (ou pela própria chave) e depois pela chave.
        grupo = func.coalesce(AutomationItemRecord.grupo_chave, AutomationItemRecord.chave)
        linhas = self.db.scalars(consulta.order_by(grupo, AutomationItemRecord.grupo_chave.is_not(None),
                                                   AutomationItemRecord.chave).offset(pular).limit(limite)).all()
        return [_publico(r) for r in linhas]

    def contar(self, automation_id: int) -> dict[str, int]:
        ativos, total = self.db.execute(
            select(func.count().filter(AutomationItemRecord.ativo.is_(True)), func.count())
            .where(AutomationItemRecord.automation_id == automation_id)).one()
        return {"ativos": int(ativos), "total": int(total)}

    def obter(self, automation_id: int, chave: str) -> AutomationItemRecord | None:
        return self.db.scalar(select(AutomationItemRecord).where(AutomationItemRecord.automation_id == automation_id,
                                                                 AutomationItemRecord.chave == chave))

    def gravar(self, automation_id: int, item: Item, *, por: str, agora: datetime) -> tuple[AutomationItemRecord, dict | None]:
        """Cria ou altera. Devolve o registro e como ele era antes (None se é novo)."""
        registro = self.obter(automation_id, item.chave)
        antes = _publico(registro) if registro is not None else None
        if registro is None:
            registro = AutomationItemRecord(id=f"itm_{uuid4().hex}", automation_id=automation_id, chave=item.chave,
                                            created_by=por, created_at=agora)
            self.db.add(registro)
        registro.rotulo, registro.grupo_chave, registro.atributos, registro.ativo = item.rotulo, item.grupo, item.atributos, item.ativo
        registro.updated_by, registro.updated_at = por, agora
        self.db.flush()
        return registro, antes

    def selecionar(self, automation_id: int, chaves: list[str], com_filiais: bool) -> list[AutomationItemRecord]:
        """Os itens pedidos (ativos), e as filiais deles se ``com_filiais``."""
        consulta = select(AutomationItemRecord).where(AutomationItemRecord.automation_id == automation_id,
                                                      AutomationItemRecord.ativo.is_(True))
        alvo = AutomationItemRecord.chave.in_(chaves)
        if com_filiais:
            alvo = or_(alvo, AutomationItemRecord.grupo_chave.in_(chaves))
        return list(self.db.scalars(consulta.where(alvo).order_by(
            func.coalesce(AutomationItemRecord.grupo_chave, AutomationItemRecord.chave),
            AutomationItemRecord.grupo_chave.is_not(None), AutomationItemRecord.chave)))


def _item(r: AutomationItemRecord) -> Item:
    return Item(r.chave, r.rotulo, r.grupo_chave, dict(r.atributos or {}), bool(r.ativo))


def _publico(r: AutomationItemRecord) -> dict[str, Any]:
    return {"chave": r.chave, "rotulo": r.rotulo, "grupo": r.grupo_chave, "atributos": dict(r.atributos or {}),
            "ativo": bool(r.ativo), "atualizado_em": r.updated_at.isoformat() if r.updated_at else None}


def ler_empresas_db(conteudo: bytes) -> list[dict[str, Any]]:
    """Cadastro da Integração Contábil (``dados/empresas.db``) como itens, com as rubricas ignoradas.

    Só lê: o arquivo vai para uma cópia temporária aberta em modo somente leitura."""
    import sqlite3
    import tempfile
    from pathlib import Path

    if not conteudo.startswith(b"SQLite format 3\x00"):
        raise ValueError("o arquivo não é um banco SQLite (empresas.db)")
    with tempfile.TemporaryDirectory(prefix="importar_itens_") as pasta:
        arquivo = Path(pasta) / "empresas.db"
        arquivo.write_bytes(conteudo)
        con = sqlite3.connect(f"file:{arquivo.as_posix()}?mode=ro", uri=True)
        try:
            con.row_factory = sqlite3.Row
            tabelas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            if "empresas" not in tabelas:
                raise ValueError("o banco não tem a tabela empresas (é o empresas.db da Integração Contábil?)")
            rubricas: dict[int, list[dict[str, Any]]] = {}
            if "rubricas_ignoradas" in tabelas:
                for r in con.execute("SELECT empresa, codigo, descricao FROM rubricas_ignoradas ORDER BY empresa, codigo"):
                    rubricas.setdefault(int(r["empresa"]), []).append({"codigo": int(r["codigo"]), "descricao": r["descricao"] or ""})
            colunas = {r[1] for r in con.execute("PRAGMA table_info(empresas)")}
            saida = []
            for r in con.execute("SELECT * FROM empresas ORDER BY codigo"):
                codigo = int(r["codigo"])
                matriz = r["matriz_codigo"] if "matriz_codigo" in colunas else None
                tem_matriz = matriz not in (None, "") and str(matriz) != str(codigo)
                atributos = {
                    "codigo": str(codigo), "separar_por_custo": bool(r["separar_por_custo"]),
                    "caminho_saida": r["caminho_saida"] or "", "email": r["email"] or "",
                    "observacao": (r["observacao"] if "observacao" in colunas else "") or "",
                    "rubricas_ignoradas": rubricas.get(codigo, []),
                }
                if tem_matriz:
                    atributos["matriz_codigo"] = str(matriz)
                saida.append({"chave": str(codigo), "rotulo": r["nome"], "grupo": str(matriz) if tem_matriz else None,
                              "ativo": bool(r["ativa"]) if "ativa" in colunas else True, "atributos": atributos})
            return saida
        finally:
            con.close()
