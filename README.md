# Portal de Automacoes

Scaffold inicial do portal com:

- backend FastAPI com JWT, SQLAlchemy, Alembic, PostgreSQL, Redis e Celery
- frontend Next.js com login, layout de dashboard e guards
- infraestrutura Docker Compose com postgres, redis, backend, worker, frontend, nginx e flower
- documentacao inicial da arquitetura, fluxo e contrato de API

## Estrutura

- `backend/`: API, modelos, servicos, tasks e migrations
- `frontend/`: painel web com rotas do dashboard
- `infra/`: reverse proxy e monitoramento
- `docs/`: decisoes e contratos iniciais

## Primeiro uso

1. Copie `backend/.env.example` para `backend/.env` se quiser separar configuracao real.
2. Suba a stack com `docker compose up --build`.
3. Acesse o frontend em `http://localhost:3000`.
4. Entre com `admin@portal.local` / `admin123`.

## Observacoes

- O backend aplica `alembic upgrade head` ao iniciar no `docker compose`.
- A API cria automaticamente roles, categorias, permissoes do admin e um worker fake local no startup.
