# Storage

Ownership: artefatos, uploads, downloads, URLs temporarias, objetos
armazenados, retencao, binarios de pacotes, runtimes e diagnosticos.

Legado a migrar:

- `app/integrations/storage/` — cópia idêntica de `infrastructure/storage/`
  (só o import path muda); falta trocar os 2 imports remanescentes e apagar.
- `app/services/manual_upload_service.py` — staging de upload manual ainda
  não tem casa em `modules/catalog`.

Removido (Fase de remoção do legado): `app/services/automation_package_resolver.py`
— sem consumidores (a resolução de pacote já acontece via `modules.catalog`).

Binarios grandes nao devem passar pelo WebSocket nem ser armazenados no
PostgreSQL.

