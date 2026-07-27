# Backend Modules

Status: fronteira fisica inicial do monolito modular.

Os modulos abaixo sao a estrutura-alvo do Portal. Nesta etapa eles documentam
ownership e destino de migracao; o codigo legado em `backend/app/` permanece
ativo ate que adaptadores e migrations sejam introduzidos.

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

