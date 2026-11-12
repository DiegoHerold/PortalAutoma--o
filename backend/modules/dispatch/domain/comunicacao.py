"""Prazos de comunicação entre o Portal e a automação no modo direto (decisão de 12/11/2026).

A instância direta dá sinal a cada pedido que faz ao Portal (eventos e consulta de comandos;
o SDK em segundo plano consulta a cada 2 s). Sem sinal:

- a partir de ``AVISO_SEM_COMUNICACAO``: o Painel mostra "comunicação não está ativa" e quem
  pediu é avisado (notificação de erro);
- em ``SEM_COMUNICACAO``: a execução é cancelada com erro e a máquina é liberada. O SDK, do
  lado da máquina, também se cancela depois do mesmo tempo sem falar com o Portal.

Cancelamento pedido sem resposta em ``PRAZO_DO_CANCELAMENTO``: o Painel mostra o erro e oferece
"Encerrar no Portal". O SDK 0.4.0 interrompe a automação em 60 s, então isso só acontece com
SDK antigo ou automação presa fora do Python.
"""

from __future__ import annotations

from datetime import timedelta

AVISO_SEM_COMUNICACAO = timedelta(seconds=30)
SEM_COMUNICACAO = timedelta(minutes=2)
PRAZO_DO_CANCELAMENTO = timedelta(minutes=2)
