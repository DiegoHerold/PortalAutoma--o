"""Comando ``portal-automacoes``: liga qualquer automação ao Portal no modo direto.

    portal-automacoes inscrever --portal https://MAQ65.intranet.biason.net --codigo ABCD-EFGH-JKLM-NPQR --nome folha
    portal-automacoes status --nome folha
    portal-automacoes trabalhar --nome folha -- python -m minha_automacao
    portal-automacoes trabalhar --nome folha --declaracao portal/declaracao.json -- python -m minha_automacao

``trabalhar`` espera os jobs do Portal (um por vez) e, para cada um, roda o comando com:

- ``PORTAL_MODO``, ``PORTAL_URL``, ``PORTAL_JOB_ID`` e ``PORTAL_JOB_TOKEN`` (o
  ``Automacao.conectar()`` do SDK lê sozinho) e ``PORTAL_ENVIO_EM_SEGUNDO_PLANO=1``;
- ``PORTAL_JOB_ARQUIVO``: JSON com ``parametros`` e ``itens`` do job (``job_atual()`` lê).

``--declaracao``: JSON com o que a automação pede para executar, o que é um item e a tabela
(ver ``Instancia.declarar``). Lido e enviado sempre que a instância passa a receber jobs.

O token do job vai por variável de ambiente do processo filho, nunca na linha de comando.
Automação em Python pode, em vez do comando, chamar ``trabalhar(instancia, executar)``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .instancia import Instancia, Job, trabalhar


def job_atual(ambiente: dict[str, str] | None = None) -> dict[str, Any]:
    """``parametros`` e ``itens`` do job em andamento (vazio fora de um job)."""
    env = os.environ if ambiente is None else ambiente
    arquivo = env.get("PORTAL_JOB_ARQUIVO")
    if not arquivo:
        return {"parametros": {}, "itens": []}
    return json.loads(Path(arquivo).read_text(encoding="utf-8"))


def gravar_job(job: Job, pasta: Path) -> Path:
    arquivo = pasta / f"{job.job_id}.json"
    arquivo.write_text(json.dumps({"job_id": job.job_id, "execucao_id": job.execucao_id, "tentativa": job.tentativa,
                                   "parametros": job.parametros, "itens": job.itens}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return arquivo


def rodar_comando(comando: list[str], job: Job, ambiente: dict[str, str], avisar: Any = print) -> int:
    """Roda o comando para um job. Se ele sair com erro sem ter encerrado a execução, o
    Portal fica sabendo (execução concluída com erro), em vez de esperar para sempre."""
    from .automacao import Automacao

    with tempfile.TemporaryDirectory(prefix="portal-job-") as pasta:
        arquivo = gravar_job(job, Path(pasta))
        env = {**os.environ, **ambiente, "PORTAL_JOB_ARQUIVO": str(arquivo), "PORTAL_ENVIO_EM_SEGUNDO_PLANO": "1"}
        codigo = subprocess.run(comando, env=env, check=False).returncode
    if codigo == 130:  # o SDK encerrou o processo depois de cancelar: o fim já foi registrado
        avisar(f"job {job.job_id}: encerrado pelo cancelamento")
    elif codigo != 0:
        avisar(f"job {job.job_id}: o comando saiu com {codigo}")
        automacao = Automacao.conectar(ambiente=ambiente)
        automacao._emitir("execucao.concluida", {"situacao": "erro",
                                                 "resumo": f"a automação saiu com o código {codigo}"})
        automacao.fechar()
    return codigo


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="portal-automacoes", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="comando_cli", required=True)

    s = sub.add_parser("inscrever", help="inscreve esta máquina com o código de uso único gerado no Portal")
    s.add_argument("--portal", required=True, help="endereço do Portal (https://...)")
    s.add_argument("--codigo", help="código de uso único (ou PORTAL_CODIGO_INSCRICAO)")
    s.add_argument("--nome", required=True, help="nome local da credencial (ex.: integracao-contabil)")
    s.add_argument("--ca", help="arquivo da CA da empresa, se não estiver no Windows")
    s.add_argument("--permitir-http", action="store_true",
                   help="provisório: aceita http:// só na rede interna (sem TLS)")

    s = sub.add_parser("status", help="mostra se a instância está aprovada e recebe jobs")
    s.add_argument("--nome", required=True)

    s = sub.add_parser("trabalhar", help="espera jobs e roda o comando para cada um")
    s.add_argument("--nome", required=True)
    s.add_argument("--declaracao", type=Path, help="JSON da declaração (parâmetros, itens, tabela)")
    s.add_argument("comando", nargs=argparse.REMAINDER, help="-- comando da automação")

    a = p.parse_args(argv)
    if a.comando_cli == "inscrever":
        codigo = a.codigo or os.environ.get("PORTAL_CODIGO_INSCRICAO")
        if not codigo:
            p.error("informe --codigo ou PORTAL_CODIGO_INSCRICAO")
        if a.permitir_http:
            print("ATENÇÃO: conexão sem TLS (http), aceita só na rede interna e provisoriamente.", file=sys.stderr)
        instancia = Instancia.inscrever(a.portal, codigo=codigo, nome=a.nome, arquivo_ca=a.ca,
                                        permitir_http=a.permitir_http)
        print(f"Inscrita: instância {instancia.id}. Agora aprove no Portal (Máquinas > Gerenciar) escolhendo a máquina.")
        return 0
    instancia = Instancia.carregar(a.nome)
    if a.comando_cli == "status":
        print(json.dumps(instancia.status(), ensure_ascii=False, indent=2))
        return 0
    comando = a.comando[1:] if a.comando[:1] == ["--"] else a.comando
    if not comando:
        p.error("informe o comando da automação depois de --")
    declaracao = None
    if a.declaracao is not None:
        arquivo = a.declaracao
        if not arquivo.is_file():
            p.error(f"declaração não encontrada: {arquivo}")
        declaracao = lambda: json.loads(arquivo.read_text(encoding="utf-8"))  # noqa: E731 - lida a cada envio
    trabalhar(instancia, lambda job, ambiente: rodar_comando(comando, job, ambiente) and None, declaracao=declaracao)
    return 0


if __name__ == "__main__":
    sys.exit(main())
