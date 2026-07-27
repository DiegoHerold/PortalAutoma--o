# Workers Entry Point

Futuro ponto de entrada para workers internos do Portal. Workers internos nao
executam automacoes como comportamento padrao; execucao pertence ao Automation
Agent.

- `outbox_worker.py`: worker PostgreSQL para a outbox transacional. Busca lote
  disponivel com bloqueio seguro, marca `processing`, publica internamente,
  marca `published`, aplica retry/backoff e recupera mensagens presas apos
  reinicio.
