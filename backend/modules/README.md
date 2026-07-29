# Backend Modules

Status: fronteira oficial do monolito modular.

Os modulos abaixo sao a estrutura oficial do Portal. O codigo legado em
`backend/app/` foi removido; compatibilidade HTTP deve viver em rotas finas
dentro do contexto proprietario correspondente.

- `access`
- `catalog`
- `fleet`
- `orchestration`
- `dispatch`
- `telemetry`
- `storage`
- `governance`

Cada modulo pode evoluir para:

```text
domain/
application/
infrastructure/
api/
tests/
```

Dominio nao deve depender de FastAPI, SQLAlchemy, Celery ou Redis.
