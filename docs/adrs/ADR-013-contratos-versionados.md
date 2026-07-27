# ADR-013 - Contratos Versionados

Status: aceito.

## Contexto

Portal e Agent podem evoluir em ritmos diferentes. Contratos copiados
manualmente criariam divergencia e falhas dificeis de diagnosticar.

## Decisao

Manter `contracts/` como fonte oficial versionada, com JSON Schema, exemplos e
estrategia de compatibilidade. A distribuicao futura sera por pacote versionado
gerado a partir desses schemas.

## Alternativas consideradas

- Duplicar schemas em cada repositorio.
- Documentar mensagens apenas em Markdown.
- Acoplar contratos a classes internas do backend.

## Consequencias

Toda mensagem Portal-Agent possui envelope e versao. Clientes podem ser gerados
a partir dos schemas quando o build estiver pronto.

## Riscos

Schemas sem testes podem ficar validos sintaticamente, mas incoerentes com a
documentacao.

## Impacto de migracao

`execution.assign` legado continua somente via adaptador. Novas mensagens usam
`execution.offer`, `execution.accepted/rejected` e `execution.commit`.

