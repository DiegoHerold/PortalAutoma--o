"""Fila local em disco dos eventos ainda sem confirmação.

Se o Agent ou o Portal ficarem fora do ar, os eventos esperam aqui e são reenviados na
ordem. O reenvio é idempotente: quem recebe ignora sequência repetida.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

LIMITE_EVENTOS = 50_000  # proteção do disco: acima disso, os mais antigos são descartados


class FilaLocal:
    def __init__(self, arquivo: Path) -> None:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        # A Automacao serializa o acesso (trava); outras threads podem emitir (ex.: monitor de tela).
        self._con = sqlite3.connect(arquivo, timeout=10, isolation_level=None, check_same_thread=False)
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.execute("CREATE TABLE IF NOT EXISTS pendentes (sequencia INTEGER PRIMARY KEY, evento TEXT NOT NULL)")
        self._con.execute("CREATE TABLE IF NOT EXISTS estado (chave TEXT PRIMARY KEY, valor INTEGER NOT NULL)")
        self.descartados = 0

    def ultima_sequencia(self) -> int:
        """Maior sequência já gerada nesta fila (para continuar depois de reabrir o processo)."""
        linha = self._con.execute("SELECT valor FROM estado WHERE chave = 'ultima'").fetchone()
        return int(linha[0]) if linha else 0

    def adicionar(self, evento: dict[str, Any]) -> None:
        self._con.execute("INSERT OR IGNORE INTO pendentes (sequencia, evento) VALUES (?, ?)",
                          (evento["sequence"], json.dumps(evento, ensure_ascii=False)))
        self._con.execute("INSERT INTO estado (chave, valor) VALUES ('ultima', ?) "
                          "ON CONFLICT (chave) DO UPDATE SET valor = MAX(valor, excluded.valor)", (evento["sequence"],))
        excesso = self.quantidade() - LIMITE_EVENTOS
        if excesso > 0:
            self._con.execute("DELETE FROM pendentes WHERE sequencia IN "
                              "(SELECT sequencia FROM pendentes ORDER BY sequencia LIMIT ?)", (excesso,))
            self.descartados += excesso

    def pendentes(self, limite: int = 500) -> list[dict[str, Any]]:
        linhas = self._con.execute("SELECT evento FROM pendentes ORDER BY sequencia LIMIT ?", (limite,)).fetchall()
        return [json.loads(l[0]) for l in linhas]

    def confirmar_ate(self, sequencia: int) -> None:
        self._con.execute("DELETE FROM pendentes WHERE sequencia <= ?", (sequencia,))

    def quantidade(self) -> int:
        return int(self._con.execute("SELECT COUNT(*) FROM pendentes").fetchone()[0])

    def fechar(self) -> None:
        self._con.close()
