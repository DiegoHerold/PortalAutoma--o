# Catálogo de automações (GitHub + upload manual)

Visão geral do subsistema que importa automações de `biason-automations` (via
GitHub App) ou de um pacote `.zip` enviado manualmente, valida seus
manifestos sem executar código, empacota tudo de forma imutável e disponibiliza
o pacote para o Automation Agent baixar e rodar.

## Modelos

- `Automation` (existente) — ganhou um campo opcional `key`, que é o `id`
  declarado no `automation.yaml`. O identificador técnico estável continua
  sendo o `id` numérico (FK usada por jobs, triggers, schedules,
  worker-preferences) — não trocamos isso, só documentamos a associação.
- `AutomationSource` — de onde a automação veio: GitHub (`owner`,
  `repository`, `branch`, `automation_path`, `manifest_path`,
  `last_commit_sha`, `sync_status`) ou upload manual (`original_filename`,
  `uploaded_by_user_id`, `source_sha256`).
- `AutomationVersion` — cada versão importada é uma linha imutável: manifesto
  completo (JSONB), hash do artefato, localização no storage
  (`artifact_bucket`/`artifact_object_key`), e `status` (`validating` →
  `ready`/`invalid` → `published` → `deprecated`/`disabled`). Restrição única
  em `(automation_id, version)` — nunca sobrescrevemos uma versão.
- `GithubIntegration` — só guarda `installation_id` + metadados da conta;
  nunca um token de usuário.

## Fluxo (idêntico para GitHub e ZIP)

1. **Staging**: o pacote é validado e empacotado, e o resultado fica em Redis
   por um tempo limitado (`IMPORT_STAGING_TTL_SECONDS`), aguardando
   confirmação do usuário. Nada é persistido no Postgres ainda.
2. **Confirmação**: `POST /automations/import/{staging_id}/confirm` cria (ou
   reaproveita) a `Automation`, grava a `AutomationSource` e a
   `AutomationVersion` com `status=ready`.
3. **Publicação**: `POST /automations/{id}/versions/{version_id}:activate`
   marca a versão como `published`. É essa versão que o dispatcher do
   Agent Gateway usa a partir daí (`automation_package_resolver.py`).
4. **Descontinuação**: `POST /automations/{id}/versions/{version_id}:deprecate`.

Ver `docs/github-automation-discovery.md` e `docs/manual-automation-import.md`
para o detalhe de cada origem, e `docs/automation-package.md` para o formato
do pacote.

## Onde fica o código

- Lógica pura (sem I/O), testada com pytest: `app/domain/automation_manifest.py`,
  `app/domain/automation_package.py`.
- Serviços: `app/services/manual_upload_service.py`,
  `app/services/github_discovery_service.py`,
  `app/services/automation_import_service.py`,
  `app/services/automation_version_lifecycle_service.py`,
  `app/services/automation_package_resolver.py`.
- Storage plugável: `app/integrations/storage/` (local ou S3/MinIO conforme
  `STORAGE_BACKEND`).
- Endpoints: `app/api/v1/endpoints/automation_imports.py`,
  `app/api/v1/endpoints/github_integrations.py`, e as rotas novas em
  `app/api/v1/endpoints/automations.py` (sources/versions/activate/deprecate/sync).
- Frontend: `NewAutomationDialog` (escolha entre GitHub/ZIP/formulário manual),
  `GithubImportFlow`, `ZipImportFlow`, painel de versões/origem na página de
  detalhe da automação, e `/settings/integrations` para conectar o GitHub.

## O que fica de fora deste subsistema (por decisão explícita)

- O executável do Automation Agent (processo Windows) — o Portal só fala o
  protocolo já existente (`agents.py` + `agent_gateway_service.py`) e resolve
  qual pacote entregar. Ver `docs/agent-distribution.md`.
- Execução automática de uma automação ao detectar atualização no GitHub — o
  webhook só marca `sync_status=update_available`; reimportar é sempre uma
  ação manual do operador.
