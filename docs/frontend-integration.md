# Integracao do Frontend

Status: vigente.

O frontend atual deve preservar design, layout, navegacao visual, componentes,
temas, cores e tipografia. Esta etapa reorganiza o backend; a reconexao visual
sera feita depois, sem redesenhar as telas.

## Consumo atual de APIs

| Tela ou area | Endpoint atual | Contrato atual | Novo modulo responsavel | Mudanca necessaria | Momento recomendado |
|---|---|---|---|---|---|
| Login | `/auth/login`, `/auth/me` | `TokenResponse`, `CurrentUser` | Access | Manter adaptador enquanto Access e migrado | Etapa Access |
| Dashboard | `/jobs`, `/workers`, `/automations`, WS `/ws/executions` | `Job`, `Worker`, `Automation` | Orchestration, Fleet, Catalog, Telemetry | Renomear Jobs/Workers para Execution/Agent no contrato, preservando layout | Apos modelos persistentes |
| Automacoes | `/automations`, `/automations/{id}`, imports ZIP/GitHub | `Automation`, `AutomationVersion`, import preview | Catalog, Storage, Governance | Migrar services para casos de uso Catalog | Etapa Catalog |
| Jobs | `/jobs`, `/jobs/{id}`, `/jobs/{id}:cancel` | `Job` | Orchestration, Dispatch | Substituir por Execution/TaskExecution/Attempt/Offer | Etapa Orchestration/Dispatch |
| Execucoes | `/executions`, `/executions/{id}` | `Execution` legado | Orchestration, Telemetry | Separar Attempt e eventos estruturados | Etapa Telemetry |
| Workers | `/workers`, `/workers/{id}`, `/workers/installer-config` | `Worker` | Fleet | Migrar para Agent/AgentInstance mantendo tela visual | Etapa Fleet |
| Gatilhos | `/triggers` | Trigger legado | Orchestration | Converter para origem/flow/schedule conforme dominio | Etapa Orchestration |
| Agendamentos | `/schedules`, `/schedules/calendar` | Schedule legado | Orchestration | Preservar UX, trocar backend para Schedule/ScheduleExecution | Etapa Scheduling |
| Usuarios, roles, categorias | `/users`, `/roles`, `/categories` | Access atual | Access, Catalog | Reaproveitar auth/permissoes validas | Etapa Access |
| Auditoria | `/audit` | AuditEntry | Governance | Migrar para AuditEvent | Etapa Governance |
| GitHub integrations | `/integrations/github/*` | GitHubIntegration/discovery | Catalog infrastructure | Criar porta GitHubSourcePort | Etapa Catalog |

## Rotas Catalog migradas nesta etapa

| Area | Rota | Status |
|---|---|---|
| Automacoes | `GET/POST /automations`, `GET/PUT/DELETE /automations/{id}` | Compatibilidade delegando para Catalog |
| Importacao | `POST /automations/import/upload`, `POST /automations/import/{id}/confirm` | Producer legado + confirmacao modular |
| Versoes | `GET /automations/{id}/versions`, `POST /automations/{id}/versions` | Consulta/criacao modular |
| Versoes | `POST /automation-versions/{id}/validate|publish|deprecate|block` | Modular |
| Packages | `POST /automation-versions/{id}/package-uploads`, `PUT /package-uploads/{id}/bytes`, `POST /package-uploads/{id}/complete|abort` | Modular |
| Runtimes | `GET/POST /runtimes`, `POST /runtimes/{id}/versions`, `POST /runtime-versions/{id}/publish|deprecate|block` | Modular |

## Rotas Fleet migradas nesta etapa

| Area | Rota | Status |
|---|---|---|
| Agents | `GET /agents`, `GET /agents/{id}`, `PATCH /agents/{id}` | Modular |
| Registro | `POST /agents/registration-tokens`, `POST /agents/register` | Modular |
| Credenciais | `POST /agents/{id}/credentials/rotate`, `POST /agents/{id}/credentials/revoke` | Modular |
| Administracao | `POST /agents/{id}/enable|disable|drain|resume|maintenance` | Modular |
| Comandos administrativos | `POST /agents/{id}/diagnostics`, `POST /agents/{id}/capabilities/refresh`, `POST /agents/{id}/update` | Modular |
| Gateway | `WS /agent-gateway/connect`, `GET /agent-gateway/health`, `GET /agent-gateway/readiness` | Modular |
| Compatibilidade | `GET/POST/PUT/DELETE /workers`, `GET /workers/installer-config` | Adapter Worker -> Agent |

## Compatibilidade Fleet no frontend

O frontend atual continua consumindo `/workers`. Esse endpoint agora e uma
camada de compatibilidade sobre `Fleet.Agent` e entrega tambem:

- `connectivity_status`
- `administrative_status`
- `health_status`
- `occupancy_status`
- `desired_version`
- `cpu_percentage`
- `memory_percentage`
- `disk_free_mb`
- `interactive_session`
- `pools`
- `alerts`

O design das telas de workers nao foi redesenhado. O badge principal continua
usando `status`, que agora traduz `Agent.connectivity_status`.

## Garantias

- Nao redesenhar telas nesta etapa.
- Nao criar mocks para esconder backend ausente.
- Endpoints antigos podem permanecer como adaptadores quando chamarem a nova
  camada de aplicacao e nao duplicarem regra.
- Quando a adaptacao exigir manter modelo antigo como fonte oficial, a tela
  pode ficar temporariamente sem dados, mas o componente visual deve ficar.

## Plano de reconexao

1. Migrar Catalog e manter automacoes/imports operando.
2. Migrar Fleet e mapear Worker UI para Agent UI sem redesenho.
3. Migrar Orchestration/Dispatch e substituir Jobs por Execution/Task/Attempt.
4. Migrar Telemetry e trocar logs textuais por timeline estruturada.
5. Ajustar tipos TypeScript somente depois que o contrato backend estiver
   disponivel.
