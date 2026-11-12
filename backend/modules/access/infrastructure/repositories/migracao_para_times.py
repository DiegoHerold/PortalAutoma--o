"""Passa as permissões por categoria que ficavam direto em cada pessoa para times (12/11/2026).

Chamada pela migration ``b2c3d4e5f6a8`` (e pelos testes). Ninguém ganha nem perde acesso:

- Pessoas (que não são admin) com o **mesmo conjunto** de permissões por categoria ficam num só
  time "Acessos de <nome>" (ou "de <nome> e <nome>", "de N pessoas"), com exatamente essas
  permissões; depois as permissões soltas saem da pessoa. O administrador pode renomear e
  reorganizar os times.
- Admin vê tudo de qualquer jeito: as permissões soltas dele só saem.
- Pessoa sem organização, num Portal sem nenhuma organização: fica como está (não há onde pôr o time).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from sqlalchemy import text

MARCAS = ("can_view", "can_execute", "can_create", "can_edit", "can_delete", "can_approve")


def _chave(nome: str, usadas: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()).strip("-")
    base = (base or "acessos")[:100]
    chave, n = base, 2
    while chave in usadas:
        chave, n = f"{base}-{n}", n + 1
    usadas.add(chave)
    return chave


def _nome(pessoas: list[str]) -> str:
    if len(pessoas) == 1:
        return f"Acessos de {pessoas[0]}"[:180]
    if len(pessoas) == 2:
        return f"Acessos de {pessoas[0]} e {pessoas[1]}"[:180]
    return f"Acessos de {len(pessoas)} pessoas"


def migrar(conn: Any) -> dict[str, int]:
    linhas = conn.execute(text(
        "SELECT p.user_id, p.category_id, " + ", ".join(f"p.{m}" for m in MARCAS) + ", u.name, u.organization_id, r.slug "
        "FROM user_category_permissions p JOIN users u ON u.id = p.user_id JOIN roles r ON r.id = u.role_id "
        "ORDER BY p.user_id, p.category_id")).all()
    padrao = conn.execute(text("SELECT id FROM access_organizations ORDER BY (key = 'default') DESC, id LIMIT 1")).scalar()
    usadas = set(conn.execute(text("SELECT key FROM access_teams")).scalars().all())

    por_pessoa: dict[int, dict[str, Any]] = {}
    admins: set[int] = set()
    for linha in linhas:
        user_id, categoria, *marcas, nome, organizacao, slug = linha
        if slug == "admin":
            admins.add(user_id)
            continue
        if not any(marcas):
            continue
        pessoa = por_pessoa.setdefault(user_id, {"nome": nome, "org": organizacao or padrao, "permissoes": []})
        pessoa["permissoes"].append((categoria, *marcas))

    grupos: dict[tuple, list[int]] = {}
    for user_id, pessoa in por_pessoa.items():
        if pessoa["org"] is None:
            continue
        grupos.setdefault((pessoa["org"], tuple(sorted(pessoa["permissoes"]))), []).append(user_id)

    times = movidas = 0
    for (org, permissoes), membros in grupos.items():
        nome = _nome([por_pessoa[u]["nome"] for u in membros])
        team_id = conn.execute(text(
            "INSERT INTO access_teams (organization_id, key, name, status) VALUES (:o, :k, :n, 'active') RETURNING id"),
            {"o": org, "k": _chave(nome, usadas), "n": nome}).scalar_one()
        for categoria, *marcas in permissoes:
            conn.execute(text(
                "INSERT INTO access_team_category_permissions (team_id, category_id, " + ", ".join(MARCAS) + ") "
                "VALUES (:t, :c, " + ", ".join(f":{m}" for m in MARCAS) + ")"),
                {"t": team_id, "c": categoria, **dict(zip(MARCAS, marcas))})
        for user_id in membros:
            conn.execute(text("INSERT INTO access_team_memberships (team_id, user_id) VALUES (:t, :u)"), {"t": team_id, "u": user_id})
            movidas += conn.execute(text("DELETE FROM user_category_permissions WHERE user_id = :u"), {"u": user_id}).rowcount
        times += 1
    for user_id in admins:
        movidas += conn.execute(text("DELETE FROM user_category_permissions WHERE user_id = :u"), {"u": user_id}).rowcount
    return {"times": times, "pessoas": sum(len(m) for m in grupos.values()), "permissoes_retiradas": movidas}
