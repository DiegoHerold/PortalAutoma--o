# Storage

Ownership: artefatos, uploads, downloads, URLs temporarias, objetos
armazenados, retencao, binarios de pacotes, runtimes e diagnosticos.

Legado a migrar:

- `app/integrations/storage/`
- `app/services/manual_upload_service.py`
- `app/services/automation_package_resolver.py`

Binarios grandes nao devem passar pelo WebSocket nem ser armazenados no
PostgreSQL.

