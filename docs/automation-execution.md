# Como uma versao importada chega a ser executada

Status: compatibilidade. A arquitetura oficial esta em
`docs/execution-lifecycle.md`, `docs/protocol.md` e `docs/migration.md`.

Este documento descreve a ponte atual entre `AutomationVersion` publicada e o
protocolo legado do Agent. Novas implementacoes devem usar
`ExecutionOffer`, aceite/rejeicao, `execution.commit`, eventos estruturados e
leases.

## Ponte atual

`agent_gateway_service.claim_next_command()` monta o comando que o Agent legado
recebe, incluindo `package_url` e `package_sha256`. A resolucao do pacote fica
em `automation_package_resolver.py`.

Fluxo atual:

1. Procura a `AutomationVersion` mais recente com `status="published"`.
2. Gera URL temporaria pelo storage configurado.
3. Se nao houver versao publicada, usa temporariamente os campos legados
   `automation.package_url` e `automation.package_sha256`.
4. Envia comando legado `execution.assign` ao Agent.

## Limites conhecidos

- `execution.assign` mistura oferta, aceite e commit.
- Nao ha `ExecutionOffer` persistente.
- Nao ha `ExecutionLease`.
- Eventos do Agent ainda podem virar logs textuais.
- Queda de WebSocket pode marcar execucao como falha antes de reconciliacao.

## Direcao

Substituir a ponte por:

```text
Execution
-> TaskExecution
-> Scheduler
-> ExecutionAttempt
-> ExecutionOffer
-> execution.accepted ou execution.rejected
-> execution.commit
-> eventos estruturados
-> artefatos
```

Agents legados podem continuar recebendo `execution.assign` via adaptador ate a
remocao planejada em `docs/migration.md`.

