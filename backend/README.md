# Backend

API FastAPI do portal de automacoes com JWT, PostgreSQL, Redis e Celery.

## Rodando localmente

1. Copie `.env.example` para `.env`.
2. Instale os requisitos de `requirements/dev.txt`.
3. Rode `alembic upgrade head`.
4. Inicie `uvicorn app.main:app --reload`.

## Bootstrap automatico

- Roles padrao, categorias e usuario admin sao criados no startup da API.
- Credenciais iniciais: `admin@portal.local` / `admin123`.
