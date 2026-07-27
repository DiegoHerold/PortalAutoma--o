# ADR-006 - HTTPS para Binarios e Grandes Sincronizacoes

Status: aceito.

## Contexto

Pacotes, runtimes, artefatos, diagnosticos e grandes lotes podem bloquear
comandos urgentes se trafegarem pelo WebSocket.

## Decisao

Usar HTTPS/S3/MinIO para downloads, uploads e sincronizacoes grandes.

## Alternativas consideradas

- Enviar binarios pelo WebSocket.
- Armazenar binarios grandes no PostgreSQL.

## Consequencias

O Portal deve emitir URLs temporarias/pre-assinadas. O Agent verifica hash e
assinatura localmente.

## Riscos

URLs expiradas ou policies incorretas podem falhar execucoes durante
preparacao.

## Impacto de migracao

A ponte atual de `package_url` continua como compatibilidade ate Storage
formalizar pacotes, runtimes, artefatos e diagnosticos.
