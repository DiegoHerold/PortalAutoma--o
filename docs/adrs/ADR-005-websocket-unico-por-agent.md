# ADR-005 - WebSocket Unico por Agent

Status: aceito.

## Contexto

Um WebSocket por execucao aumenta complexidade, consumo e risco de estados
divergentes.

## Decisao

Cada Agent mantem uma unica conexao WebSocket ativa com o Portal.

## Alternativas consideradas

- WebSocket por automacao.
- WebSocket por tentativa.

## Consequencias

O protocolo precisa multiplexar comandos, ofertas, eventos, ACK e leases pela
mesma conexao. Downloads/uploads grandes usam HTTPS.

## Riscos

Um canal unico mal implementado pode bloquear comandos urgentes atras de lotes
grandes de eventos.

## Impacto de migracao

O endpoint atual `/agents/ws` permanece; o contrato evolui de `execution.assign`
para oferta, aceite/rejeicao e commit.
