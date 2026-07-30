# Webhooks de entrada

Status: vigente a partir da Fase 5.

## Contrato HTTP

Webhooks HTTP de entrada sao `TriggerCompatRecord` com `trigger_type="https"`.

Invocacao publica:

```text
POST {backend_public_url}/api/v1/triggers/invoke/{route_path}
```

Headers:

```text
X-Trigger-Secret: <secret>
Content-Type: application/json
Idempotency-Key: <opcional>
X-Correlation-ID: <opcional>
```

O endpoint publico nao exige usuario autenticado, mas valida o secret do webhook.
Uma invocacao real cria uma `Execution` com `origin="trigger"` e vincula o
registro legado de `jobs.trigger_id` para permitir filtros por Webhook em
`/executions?origin=trigger&trigger_id={id}`.

## Secrets

O secret completo e retornado somente na criacao ou em rotacao:

```text
POST /api/v1/triggers
POST /api/v1/triggers/{id}/rotate-secret
```

Listagem e detalhe retornam apenas metadados:

```text
secret_configured
secret_last_four
secret_created_at
secret_rotated_at
```

O banco armazena `secret_hash`; `secret_token` legado e mantido somente como
campo compatibilizado/redigido para registros antigos.

## Mapping

O mapping de webhook segue exatamente `apply_parameter_mapping`:

```json
{
  "company_id": "body.company_id",
  "customer": "headers.x-customer",
  "force": "query_params.force"
}
```

Quando a origem nao e informada, o backend assume `body`.
Constantes nao fazem parte deste contrato de Webhook nesta fase.

Sem mapping, a automacao recebe:

```json
{
  "webhook_data": {},
  "headers": {},
  "query_params": {}
}
```

## Dry-run

Teste de mapping usa:

```text
POST /api/v1/triggers/{id}/test
```

Esse endpoint nao cria `Execution` e nao chama `/invoke`.

## Gatilhos legados

Registros `trigger_type="chained"` continuam suportados no backend para
compatibilidade, mas nao podem ser criados pela UI principal.

Fluxos (`Flow`, `FlowVersion`, `FlowNode`, `FlowEdge`) sao o mecanismo oficial
para orquestracao e encadeamento entre automacoes. Registros legados devem ser
avaliados manualmente antes de exclusao ou desativacao.
