# Corte final de `backend/app`

Status: `backend/app` removido.

As responsabilidades que ainda eram consumidas foram movidas antes da remocao:

| Responsabilidade | Destino definitivo |
| --- | --- |
| Health legado `/api/v1/health` | `backend/api/health.py` |
| Logging do bootstrap | `backend/infrastructure/logging.py` |
| WebSocket `/api/v1/ws/executions` | `backend/modules/telemetry/api/realtime.py` |
| Importacao manual/GitHub e staging | `backend/modules/catalog/api/imports.py`, `backend/modules/catalog/infrastructure/import_packaging.py`, `backend/modules/catalog/infrastructure/import_staging_store.py` |
| GitHub App integrations | `backend/modules/catalog/api/github_integrations.py` |
| Entrypoint ASGI | `backend/main.py` |
| Metadata Alembic | ORMs oficiais em `backend/modules/*/infrastructure/orm` |

Nao ha arquivo mantido em `backend/app`.
