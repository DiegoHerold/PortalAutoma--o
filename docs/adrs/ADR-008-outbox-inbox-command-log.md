# ADR-008 - Outbox, Inbox e Command Log

Status: aceito.

## Contexto

O protocolo e sujeito a repeticao, queda de rede e mensagens fora de ordem.

## Decisao

Persistir comandos enviados, mensagens recebidas e eventos de saida em command
log, inbox e outbox.

## Alternativas consideradas

- Confiar apenas no WebSocket.
- Deduplicar somente em memoria.

## Consequencias

Toda mensagem tem `message_id`; comandos tem sequencia; eventos podem ser
reenviados e confirmados por ACK.

## Riscos

Implementacao parcial em memoria daria falsa confiabilidade e perderia dados
em queda de processo.

## Impacto de migracao

A etapa atual cria contratos e docs. A persistencia real entra na proxima etapa
com migrations proprias.
