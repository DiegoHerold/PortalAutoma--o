# Análise de Remoção do Legado — Fase 1 (Análise, sem remoção)

Status: análise concluída, nenhuma remoção executada ainda.
Data: 2026-07-28.

## 0. Achado principal (contradiz a premissa inicial)

A tarefa partiu da premissa de que "a migração funcional já foi executada" e que
`backend/app` conteria apenas resíduos. Isso é **parcialmente falso**. O core de
execução (Fleet/Agents, Catalog, Dispatch, Orchestration, Scheduling, Telemetry
outbox/SSE, Storage, Governance-tabelas) já está de fato servido por
`backend/modules` e ligado em `backend/bootstrap/api.py`. Mas **cinco áreas de
negócio ainda vivem inteiramente em `backend/app`, são consumidas pelo frontend
hoje, e não têm substituto funcional na nova arquitetura**:

1. **Jobs legados** (`/api/v1/jobs`) — fila de execução antiga (`JobDispatcherService`,
   `JobEnrichmentService`, tabela `jobs`). Frontend: Dashboard, página `/jobs`,
   `jobs-manager.tsx`, `dispatch-dialog.tsx`.
2. **Triggers/Webhooks** (`/api/v1/triggers`, `/api/v1/webhooks/trigger/*`) — não
   existe módulo novo equivalente (nenhum dos 8 contextos oficiais cobre
   "invocação por webhook com secret_token e parameter_mapping"). Frontend:
   página `/triggers`, `triggers-manager.tsx`, `automation-detail.tsx`.
3. **Integração GitHub (OAuth/discovery)** (`/api/v1/integrations/github/*`) —
   connect/callback/discover/list-repos/branches só existem em
   `app/api/v1/endpoints/github_integrations.py` + `app/services/github_discovery_service.py`.
   O Catalog novo só tem o *use case* de confirmação de import
   (`ConfirmStagedAutomationImport`), não o fluxo de descoberta/OAuth. Frontend:
   `github-integrations-panel.tsx`, `github-import-flow.tsx`.
4. **WebSocket `/ws/executions`** (`app/api/v1/endpoints/realtime.py`) — é o
   **único** canal de tempo real que o frontend usa hoje (`dashboard-view.tsx`,
   `jobs-manager.tsx`, `executions-manager.tsx`, `workers-manager.tsx` via
   `use-realtime.ts`). Existe substituto novo real (`modules/telemetry` expõe
   SSE em `/{execution_id}/stream`), mas o frontend **ainda não foi religado**
   a ele.
5. **Upload manual de automação** (`/api/v1/automations/import/upload`) —
   `ManualUploadService` + staging em memória; o `confirm` final já delega para
   `modules.catalog` (bom sinal), mas o upload/staging em si ainda é old-stack.

Nenhum destes pode ser apagado hoje sem quebrar produto. Classificação:
**RECREATE_IN_NEW_ARCHITECTURE / MOVE**, não DELETE.

## 1. O que já está genuinamente substituído (seguro avançar)

- `backend/app/main.py` já é só um shim de 4 linhas → `bootstrap.api.create_api_application()`.
- `app/core/database.py` já é um shim → reexporta `infrastructure.database` (mesmo `Base`).
- `app/services/automation_service.py`, `automation_import_service.py`,
  `automation_version_lifecycle_service.py`, `worker_service.py`,
  `agent_gateway_service.py` já são **fachadas de compatibilidade** que delegam
  para `modules.catalog`/`modules.fleet` (confirmado lendo o código e os testes
  de arquitetura que já garantem isso).
- `app/tasks/*.py` (Celery) são wrappers finos — só chamam
  `modules.dispatch`/`modules.orchestration`. `job_tasks.execute_job` já está
  desativado (retorna `"delegated_to_dispatch"`).
- `app/api/v1/router.py` — **morto**: nada importa esse arquivo (bootstrap/api.py
  reimplementa a montagem de rotas manualmente). DELETE seguro.
- `app/api/v1/endpoints/{agents,audit,auth,categories,roles,users,workers,schedules}.py`
  — não são montados em lugar nenhum (nem `router.py` nem `bootstrap/api.py`).
  Órfãos. Únicas exceções: `agents.py` tem seu *conteúdo* lido por
  `tests/architecture/test_architecture_context.py` (`test_worker_and_agent_legacy_services_delegate_to_fleet_gateway`)
  como string — o teste precisa ser adaptado antes de apagar o arquivo.
- `app/integrations/storage/*` e `app/integrations/github/client.py` são
  **cópias idênticas** (só o import path muda) de `infrastructure/storage/*` e
  `infrastructure/github/client.py`, que já são usadas pelo Catalog novo. MERGE
  trivial: trocar os 2 imports que ainda restam e apagar o antigo.
- `app/workers/{capability_resolver,heartbeat,local_agent}.py` — **zero
  consumidores** em todo o repositório (confirmado por busca estática). Fleet
  Gateway oficial (`backend/gateway/agent_gateway`) já cobre isso. DELETE
  seguro, após checagem manual rápida de cada arquivo.
- `app/domain/automation_manifest.py` / `automation_package.py` — Catalog novo
  já tem `modules/catalog/domain/manifest.py` equivalente; único consumidor
  externo são os próprios testes de domínio antigos. MOVE/MERGE dos testes,
  depois DELETE.

## 2. Problema de modelagem já existente (não introduzido por mim)

`alembic/env.py` importa **ao mesmo tempo** `app.models.*` e `modules/*/infrastructure/orm/models.py`.
Isso não quebra porque os models novos usam `__table_args__ = {"extend_existing": True}` —
ou seja, **não são tabelas duplicadas**: `users`, `roles`, `categories`, `workers`,
`automation_worker_preferences`, `automation_versions`, `automation_sources`,
`automations` são a **mesma tabela física**, com a classe nova "estendendo" as
colunas da classe antiga. Isso significa:

- Não há dado órfão para migrar nessas tabelas — é a mesma tabela.
- Mas há **duas classes ORM mapeadas para a mesma tabela** (ex.: `app.models.user.User`
  e `modules.access.infrastructure.orm.models.AccessUserRecord`), o que é
  exatamente o "models ORM duplicados" que a tarefa pede para eliminar.
- `categories` tem uma **terceira** duplicação: é declarada em `app.models`, em
  `modules/access` E em `modules/catalog` (as três com `extend_existing=True`).
  Isso precisa de decisão de ownership (Access ou Catalog é dono de Category?)
  antes de qualquer remoção de classe.
- Confirmado empiricamente (importei os três conjuntos de models num script
  Python isolado): nenhum erro de tabela duplicada ocorre hoje.

`app.models.*` só é importado por `alembic/env.py` — nenhum código de aplicação
usa essas classes fora de `backend/app` (o `app.models` importado pelos serviços
antigos é usado só dentro dos próprios serviços antigos, que ainda estão vivos —
ver seção 0).

## 3. Bug arquitetural pré-existente encontrado (não relacionado à remoção)

Rodei a suíte de testes de arquitetura. `test_gateway_endpoint_does_not_access_orm_directly`
**já falha hoje**, antes de qualquer mudança minha:

```
gateway/agent_gateway/http_compat.py:
  from modules.fleet.infrastructure.orm.models import FleetWorkerRecord
```

O Gateway oficial está acessando ORM diretamente, violando a própria regra
arquitetural do projeto (controllers não devem acessar ORM). Isso é uma
inconsistência da arquitetura *nova*, não do legado — deixo registrado para
vocês decidirem se corrigimos nesta iniciativa ou abrimos à parte.

## 4. Limitações do ambiente desta sessão

- **Sem Docker/Postgres/Redis** disponíveis neste sandbox — não é possível
  subir a stack real, rodar migrations contra um banco de verdade, nem
  executar os testes E2E ponta a ponta descritos na tarefa (seções 25/26).
- **Python 3.10** é o único disponível aqui (sem privilégio para instalar
  outra versão); o código novo usa recursos de 3.11+ (`enum.StrEnum`,
  `datetime.UTC`). O ambiente real do projeto usa **3.12** (visto nos
  `__pycache__`). Por isso 7 módulos de teste (`catalog`, `dispatch`, `fleet`,
  `orchestration`, `orchestration/flows`, `orchestration/scheduling`,
  `storage`) não coletam aqui — é um artefato deste sandbox, não um bug do
  código.
- Com essas ressalvas, rodei o que colide: **58 passaram, 4 falharam** (2 por
  `StrEnum` em cascata, 1 é o bug real do `http_compat.py` acima, 1 é
  `test_github_client` — a chamar sem `GITHUB_APP_ID`/`GITHUB_APP_PRIVATE_KEY`
  configurados, precisa investigação separada).
- **Deleção de arquivos no diretório do projeto** exige aprovação explícita via
  o gate de segurança do Cowork (já habilitada para esta pasta nesta sessão).
- `git`: havia um `.git/index.lock` órfão que impedia qualquer operação de
  escrita (commit/tag); já removido com aprovação de deleção. As 248
  entradas "modified" no `git status` são **100% diferença de final de linha
  (CRLF vs LF)** — confirmado comparando um diff (`13446 insertions(+), 13446
  deletions(-)` para 248 arquivos) — não é trabalho em andamento do usuário.
  Não commitei nada ainda.

## 5. Classificação resumida (arquivos "seguros" hoje)

| Item | Classificação | Ação |
|---|---|---|
| `app/api/v1/router.py` | DELETE | Nenhum consumidor |
| `app/api/v1/endpoints/{auth,users,roles,categories,workers}.py` | DELETE | Não montados; superseded por `modules/access`, `modules/fleet` |
| `app/api/v1/endpoints/audit.py` | DELETE | Não montado; superseded por `modules/governance` |
| `app/api/v1/endpoints/schedules.py` | DELETE | Não montado; superseded por `modules/orchestration/scheduling` |
| `app/api/v1/endpoints/agents.py` | REVIEW_MANUALLY | Não montado, mas conteúdo lido por teste de arquitetura — migrar teste primeiro |
| `app/workers/*` (3 arquivos) | DELETE | Zero consumidores; Fleet Gateway já cobre |
| `app/integrations/storage/*`, `app/integrations/github/client.py` | MERGE→DELETE | Duplicata exata de `infrastructure/*`; trocar 2 imports remanescentes |
| `app/domain/automation_manifest.py`, `automation_package.py` | MERGE→DELETE | `modules/catalog/domain` já cobre; migrar 2 testes |
| `app/tasks/*.py` | MOVE | Já delegam 100% para `modules.*`; só precisam de novo endereço e nomes sem prefixo `app.` |
| `app/services/{automation_service,automation_import_service,automation_version_lifecycle_service,worker_service,agent_gateway_service}.py` | KEEP_TEMPORARILY | Fachadas de compatibilidade documentadas e testadas — remover só quando frontend parar de depender das rotas antigas |
| `app/models/*`, `app/repositories/*`, `app/schemas/*` ligados a Job/Trigger/Webhook/GithubIntegration | KEEP_TEMPORARILY | Vivos via rotas de compatibilidade — ver seção 0 |
| `app/services/{job_dispatcher_service,job_enrichment_service,trigger_service,manual_upload_service,github_discovery_service}.py` | RECREATE_IN_NEW_ARCHITECTURE | Sem substituto funcional — precisa construir em `modules/` antes de tocar |
| `app/api/v1/endpoints/realtime.py` | RECREATE_IN_NEW_ARCHITECTURE + MOVE (frontend) | Substituto existe (`modules/telemetry` SSE) mas frontend não foi religado |

Isso cobre a maior parte de `backend/app`; itens menores (`app/core/{constants,logging,permissions,security}.py`,
`app/utils/*`, `app/integrations/{http,n8n,playwright,power_automate,scripts}/*`)
ainda precisam de checagem individual de consumidores antes de classificar —
não fiz isso ainda para não estourar o escopo desta primeira passada.

## 6. Plano de lotes proposto (nenhum executado ainda)

1. **Lote 1 — Morto/duplicado sem risco**: `app/api/v1/router.py`; endpoints
   órfãos (`auth`, `users`, `roles`, `categories`, `workers`, `audit`,
   `schedules`); `app/workers/*`. Risco: baixo. Teste obrigatório: suíte
   completa + boot da API.
2. **Lote 2 — Merge de duplicatas de infraestrutura**: trocar os imports
   restantes de `app.integrations.storage/github` para `infrastructure.*` e
   apagar os antigos; mover `app/domain/automation_manifest.py`/`automation_package.py`
   (migrando os 2 testes que os usam).
3. **Lote 3 — Mover tasks Celery**: relocar `app/tasks/*.py` para
   `backend/workers/tasks/` (ou local equivalente), renomear `celery_app` para
   fora de `app.core`, atualizar `docker-compose.yml`.
4. **Lote 4 — Corrigir o gateway oficial**: trocar os 2 imports que o Gateway
   novo ainda faz de `app.core.*` (`gateway/agent_gateway/limits.py`,
   `endpoint.py`) para `infrastructure.*`.
5. **Lote 5 (o grande) — Recriar Jobs/Triggers/Webhooks/GitHub-import/Realtime
   na arquitetura nova**, religar o frontend aos endpoints novos, então só
   depois apagar `app/services/job_*`, `trigger_service`, `github_discovery_service`,
   `realtime.py` e os models/schemas/repositories associados.
6. **Lote 6 — `backend/app` final**: o que sobrar (provavelmente quase nada)
   vira revisão manual antes de remover o diretório.

Os lotes 1–4 são mecânicos e de baixo risco. O lote 5 é engenharia real
(múltiplas sessões), não uma limpeza.
