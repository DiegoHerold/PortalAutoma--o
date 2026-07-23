# Architecture

## Overview
Portal de Automações é um sistema de orquestração e execução de automações com suporte a múltiplos workers, priorização de filas e estimativa de tempo de execução (ETA).

## Stack Tecnológica

### Backend
- **FastAPI**: Framework web para APIs RESTful
- **SQLAlchemy 2**: ORM com Mapped types para type safety
- **PostgreSQL**: Banco de dados relacional
- **Redis**: Cache, pub/sub para WebSockets e backend do Celery
- **Celery**: Sistema de filas para execução assíncrona de jobs
- **Alembic**: Gerenciamento de migrations do banco
- **JWT**: Autenticação e autorização

### Frontend
- **Next.js 15**: Framework React com App Router
- **TypeScript**: Type safety no frontend
- **Tailwind CSS**: Estilização
- **shadcn/ui**: Componentes UI

### Infraestrutura
- **Docker Compose**: Orquestração de containers
- **Nginx**: Reverse proxy e suporte a WebSockets
- **Flower**: Monitoramento do Celery

## Camadas da Aplicação

```
┌─────────────────────────────────────────────┐
│           Frontend (Next.js)                │
│   - UI Components                           │
│   - Real-time WebSocket client              │
│   - State management                        │
└─────────────────────────────────────────────┘
                    │
                    │ HTTP/WS
                    ▼
┌─────────────────────────────────────────────┐
│         API Layer (FastAPI)                 │
│   - REST endpoints                          │
│   - WebSocket endpoint (/ws/executions)     │
│   - Authentication & Authorization          │
└─────────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌──────────────┐      ┌──────────────────┐
│   Services   │      │   Repositories   │
│              │      │                  │
│ - Dispatcher │◄─────┤ - Job           │
│ - ETA calc   │      │ - Worker        │
│ - Audit      │      │ - Automation    │
│ - Realtime   │      │ - Preferences   │
└──────────────┘      └──────────────────┘
        │                       │
        ▼                       ▼
┌─────────────────────────────────────────────┐
│          Database (PostgreSQL)              │
│   - Jobs, Workers, Automations              │
│   - Audit logs, Execution history           │
│   - Worker preferences                      │
└─────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│       Task Queue (Celery + Redis)           │
│   - Job execution tasks                     │
│   - Priority queues (critical/high/normal/  │
│     low)                                    │
│   - Worker pool management                  │
└─────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│            Workers                          │
│   - Local agent                             │
│   - Remote workers                          │
│   - Heartbeat monitoring                    │
└─────────────────────────────────────────────┘
```

## Principais Componentes

### Job Dispatcher
Responsável por atribuir jobs aos workers baseado em:
- **Lista de preferência ordenada**: Cada automação pode ter uma lista de workers preferidos
- **Disponibilidade real**: Status online, heartbeat recente, capacidade disponível
- **Fallback**: Se nenhum worker preferido está disponível, job fica em fila

### ETA Calculation Service
Calcula estimativas de duração e tempo de início/término usando:
- **Percentil configurável** (default p75) do histórico de execuções
- **Histórico por par (automação, worker)** para maior precisão
- **Fallback**: automação em qualquer worker → timeout da automação

### Real-time Service
Sistema de atualizações em tempo real via WebSocket:
- **Redis pub/sub**: Suporte a múltiplas instâncias do backend
- **Broadcast de eventos**: Mudanças de status de jobs e recálculo de ETA
- **Autenticação**: JWT via query parameter

### Audit Service
Registro completo de ações no sistema:
- CRUD de entidades (Automations, Workers, Users, etc.)
- Transições de status de jobs
- Login/logout e tentativas de autenticação
- Campos: actor, actor_type, action, entity_type, before/after JSON

## Segurança

### Autenticação
- **JWT tokens** com tempo de expiração configurável
- Tokens incluem `sub` (user ID) e `roles`

### Autorização
- **Roles globais**: admin, manager, operator, viewer
- **Permissões por categoria**: can_view, can_create, can_edit, can_delete, can_execute
- Admin tem acesso total

### Webhooks
- **Secret token** validação para gatilhos externos
- **Rate limiting**: 100 requisições por minuto por IP
- **Auditoria** de todas as chamadas

## Fluxos de Dados

### Fluxo de Dispatch de Job
1. User/System cria job → API recebe request
2. Dispatcher busca lista de preferência da automação
3. Para cada worker na lista (ordem de prioridade):
   - Verifica disponibilidade (status, heartbeat, concurrency)
   - Se disponível: atribui job e envia para Celery
   - Se não: tenta próximo
4. Se nenhum disponível: job fica em `queued`
5. Emite evento WebSocket com status e ETA

### Fluxo de Execução de Job
1. Celery task recebe job
2. Worker executa automação
3. Atualiza status para `running` → emite WS
4. Ao terminar: atualiza para `success/failed` → emite WS
5. Dispatcher promove próximo job da fila
6. Recalcula ETAs dos jobs restantes → emite WS

### Fluxo de Webhook Trigger
1. Requisição POST em `/webhooks/trigger/{route_path}`
2. Valida secret_token
3. Cria job via `dispatch_system`
4. Auditoria do disparo
5. Retorna job_id

## Configurações

Via `app/core/config.py` (Settings):
- `eta_percentile`: Percentil para cálculo de ETA (default: 75)
- `eta_window`: Número de execuções para calcular ETA (default: 20)
- `worker_heartbeat_window_seconds`: Janela de heartbeat (default: 60)
- `access_token_expire_minutes`: Expiração do JWT
- Database, Redis, Celery URLs

## Filas do Celery

- **critical**: Prioridade máxima
- **high**: Alta prioridade
- **normal**: Prioridade padrão
- **low**: Baixa prioridade

Dentro da mesma prioridade: FIFO por `created_at`
