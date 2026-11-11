"""Teste de mutação das regras críticas (estimativa e fila), com cosmic-ray.

    cd backend
    .venv\\Scripts\\python.exe tools\\mutacao\\rodar.py estimativas

Por que este executor existe: no Windows, com o caminho do projeto contendo espaços, o
cosmic-ray marcava todo mutante como "morto" mesmo sem mutação nenhuma (o comando de
teste não achava os arquivos). Aqui a configuração usa caminhos absolutos entre aspas,
e a execução é abortada se o código SEM mutação não passar nos testes. Sai com código 1
se sobrar mutante vivo ou incompetente.
"""

from __future__ import annotations

import collections
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from cosmic_ray.testing import run_tests
from cosmic_ray.work_item import TestOutcome

BACKEND = Path(__file__).resolve().parents[2]
ALVOS = {
    "estimativas": ("modules/telemetry/domain/estimativas.py", "modules/telemetry/tests/test_estimativas.py"),
    "fila": ("modules/dispatch/domain/fila.py", "modules/dispatch/tests/test_fila.py"),
    "acompanhamento": ("modules/telemetry/domain/acompanhamento.py", "modules/telemetry/tests/test_acompanhamento.py"),
    "concessao": ("modules/access/domain/concessao.py", "modules/access/tests/test_concessao.py"),
    "instancia_direta": ("modules/fleet/domain/instancia_direta.py", "modules/fleet/tests/test_instancia_direta.py"),
    "linha_do_tempo": ("modules/dispatch/domain/linha_do_tempo.py", "modules/dispatch/tests/test_linha_do_tempo.py"),
    "itens": ("modules/catalog/domain/itens.py", "modules/catalog/tests/test_itens.py"),
    "notificacoes": ("modules/telemetry/domain/notificacoes.py", "modules/telemetry/tests/test_notificacoes.py"),
    "retencao": ("modules/governance/domain/retencao_por_automacao.py",
                 "modules/governance/tests/test_retencao_por_automacao.py"),
    "formulario": ("modules/catalog/domain/formulario.py", "modules/catalog/tests/test_formulario.py"),
}
# Operadores excluídos por alvo, sempre com o motivo. Mutante equivalente não é falha de teste.
EXCLUIDOS = {
    "estimativas": {
        # Todo "|" do módulo está em anotação de tipo; com "from __future__ import annotations"
        # a anotação é texto e trocar o operador não muda comportamento.
        "core/ReplaceBinaryOperator_BitOr_.*": "| só aparece em anotações de tipo",
    },
    "fila": {
        "core/ReplaceBinaryOperator_BitOr_.*": "| só aparece em anotações de tipo",
    },
    "acompanhamento": {
        "core/ReplaceBinaryOperator_BitOr_.*": "| só aparece em anotações de tipo",
    },
    "concessao": {
        "core/ReplaceBinaryOperator_BitOr_.*": "| só aparece em anotações de tipo",
    },
    "instancia_direta": {
        "core/ReplaceBinaryOperator_BitOr_.*": "| só aparece em anotações de tipo",
    },
    "linha_do_tempo": {
        "core/ReplaceBinaryOperator_BitOr_.*": "| só aparece em anotações de tipo",
    },
    "itens": {
        "core/ReplaceBinaryOperator_BitOr_.*": "| só aparece em anotações de tipo",
    },
    "notificacoes": {
        "core/ReplaceBinaryOperator_BitOr_.*": "| só aparece em anotações de tipo",
    },
    "retencao": {
        "core/ReplaceBinaryOperator_BitOr_.*": "| só aparece em anotações de tipo",
    },
    "formulario": {
        "core/ReplaceBinaryOperator_BitOr_.*": "| só aparece em anotações de tipo",
    },
}


def comando_de_teste(testes: str) -> str:
    python = Path(sys.executable).as_posix()
    raiz = BACKEND.as_posix()
    return f'"{python}" -m pytest -x -q -p no:cacheprovider --rootdir "{raiz}" "{raiz}/{testes}"'


def main(nome: str) -> int:
    modulo, testes = ALVOS[nome]
    # O pytest escreve nomes acentuados; sem UTF-8 o cosmic-ray quebra ao ler a saída de um
    # teste que falhou e marca o mutante (que foi morto) como "incompetente".
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"
    comando = comando_de_teste(testes)
    resultado, saida = run_tests(comando, 60)
    if resultado != TestOutcome.SURVIVED:
        print(f"ABORTADO: sem mutação os testes não passam ({resultado}). Saída:\n{saida[-800:]}")
        return 2
    print("Linha de base: testes passam sem mutação.")

    sessao = BACKEND / "tools" / "mutacao" / f"{nome}.sqlite"
    cosmic_ray = Path(sys.executable).with_name("cosmic-ray.exe")
    with tempfile.TemporaryDirectory() as pasta:
        config = Path(pasta) / "config.toml"
        config.write_text(
            "[cosmic-ray]\n"
            f"module-path = \"{(BACKEND / modulo).as_posix()}\"\n"
            "timeout = 60.0\n"
            "excluded-modules = []\n"
            f"test-command = '{comando}'\n"
            "[cosmic-ray.distributor]\n"
            "name = \"local\"\n"
            "[cosmic-ray.filters.operators-filter]\n"
            f"exclude-operators = {list(EXCLUIDOS.get(nome, {}))!r}\n",
            encoding="utf-8",
        )
        subprocess.run([str(cosmic_ray), "init", str(config), str(sessao), "--force"], cwd=BACKEND, check=True)
        if EXCLUIDOS.get(nome):
            filtro = Path(sys.executable).with_name("cr-filter-operators.exe")
            subprocess.run([str(filtro), str(sessao), str(config)], cwd=BACKEND, check=True)
            for padrao, motivo in EXCLUIDOS[nome].items():
                print(f"Excluído: {padrao} ({motivo})")
        # O cosmic-ray troca o arquivo no lugar. Se um mutante estoura o tempo, ele pode não
        # devolver o original (aconteceu na Fase 6): guardamos uma cópia e conferimos no fim.
        arquivo = BACKEND / modulo
        original = arquivo.read_bytes()
        try:
            subprocess.run([str(cosmic_ray), "exec", str(config), str(sessao)], cwd=BACKEND, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        finally:
            if arquivo.read_bytes() != original:
                arquivo.write_bytes(original)
                print(f"ATENÇÃO: {modulo} ficou com um mutante; o original foi devolvido.")

    con = sqlite3.connect(sessao)
    linhas = con.execute("SELECT test_outcome, diff FROM work_results").fetchall()
    contagem = collections.Counter(o for o, _ in linhas)
    total = len(linhas)
    print(f"{nome}: {total} mutantes · " + " · ".join(f"{k}: {v}" for k, v in sorted(contagem.items(), key=lambda kv: str(kv[0]))))
    vivos = [d for o, d in linhas if o in ("SURVIVED", "INCOMPETENT")]
    for diff in vivos:
        mudou = [l.strip() for l in (diff or "").splitlines()
                 if l[:1] in "+-" and not l.startswith(("+++", "---")) and l[1:].strip()]
        print("  vivo:", "  =>  ".join(mudou))
    return 1 if vivos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "estimativas"))
