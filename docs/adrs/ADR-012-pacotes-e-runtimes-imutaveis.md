# ADR-012 - Pacotes e Runtimes Imutaveis

Status: aceito.

## Contexto

Execucao reproduzivel depende de artefatos versionados, verificaveis e nao
mutaveis.

## Decisao

O Portal publica pacotes e runtimes imutaveis com hash/assinatura. O Agent
baixa, verifica, prepara cache local e executa somente apos commit.

## Alternativas consideradas

- Agent executar direto do GitHub.
- Sobrescrever pacote na mesma versao.

## Consequencias

Mudanca de codigo exige nova versao. Storage guarda binarios; PostgreSQL guarda
metadados e estado.

## Riscos

Agentes legados podem tentar executar pacotes sem validar hash se o adaptador
nao for restritivo.

## Impacto de migracao

Campos legados `automation.package_url` e `package_sha256` continuam como
fallback temporario ate `AutomationPackage` e `RuntimeVersion` serem completos.

