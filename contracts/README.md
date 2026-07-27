# Contratos Compartilhados

Status: fonte oficial dos contratos Portal-Agent.

Este diretorio deve ser distribuido para Portal e Automation Agent como pacote
versionado gerado a partir dos JSON Schemas. Enquanto os projetos estiverem no
mesmo workspace, ele e a fonte local de schemas.

Regras:

- Todo contrato possui versao.
- Toda mensagem usa envelope com `message_id`.
- Eventos sao idempotentes e podem ser entregues mais de uma vez.
- Mudanca incompatibil exige nova versao de protocolo.
- Exemplos validos e invalidos devem acompanhar novas mensagens.
- Clientes do Portal e do Agent devem ser gerados a partir destes schemas
  quando a automacao de build existir.

## Estrategia de compatibilidade

- Versao inicial: `1.0`.
- Versao minima aceita pelo Portal nesta etapa: `1.0`.
- Versao maxima aceita pelo Portal nesta etapa: `1.0`.
- Agents legados que usam `execution.assign` devem ser marcados por adaptador
  e nao devem criar novo contrato divergente.
- Descontinuacoes devem ser documentadas em `docs/migration.md`.
