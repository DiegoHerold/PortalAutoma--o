# Backend

API FastAPI do Portal de Automacoes. O backend esta em migracao arquitetural
para monolito modular: `backend/modules/` define os contextos oficiais.
`backend/app/` foi removido no corte final da migracao.

O Portal e o Control Plane. O Automation Agent e o Execution Plane. Redis,
Celery e WebSocket sao mecanismos de transporte/execucao interna, nao fonte
oficial de estado.

## Rodando localmente

1. Copie `.env.example` para `.env`.
2. Instale os requisitos de `requirements/dev.txt`.
3. Rode `alembic upgrade head`.
4. Inicie `uvicorn main:app --reload`.

## Arquitetura

- Fonte oficial: `../docs/architecture.md`.
- Modulos: `../docs/modules.md`.
- Contratos Portal-Agent: `../contracts/`.
- Migracao: `../docs/migration.md`.

## Bootstrap automatico

- Roles padrao, categorias e usuario admin sao criados no startup da API.
- Credenciais iniciais: `admin@portal.local` / `admin123`.
