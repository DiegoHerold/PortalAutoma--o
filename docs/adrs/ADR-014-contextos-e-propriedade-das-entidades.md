# ADR-014 - Contextos e Propriedade das Entidades

Status: aceito.

## Contexto

O codigo atual permite que services e handlers manipulem modelos de dominios
diferentes diretamente.

## Decisao

Definir oito contextos oficiais e ownership por entidade: Access, Catalog,
Fleet, Orchestration, Dispatch, Telemetry, Storage e Governance.

## Alternativas consideradas

- Organizar apenas por camada tecnica.
- Permitir qualquer service alterar qualquer tabela.

## Consequencias

Cada contexto altera diretamente apenas suas entidades. Integracoes internas
usam casos de uso, comandos ou contratos.

## Riscos

Fronteiras apenas documentadas podem ser ignoradas durante pressa de
implementacao.

## Impacto de migracao

Arquivos legados serao movidos para `backend/modules/` em etapas. Ate la,
`docs/modules.md` mapeia o destino e os testes protegem a existencia das
fronteiras.

