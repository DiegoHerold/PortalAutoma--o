# Fluxos do Sistema

## 1. Fluxo Completo: Webhook → Dispatcher → Worker → ETA → WebSocket

```
┌─────────────┐
│   n8n ou    │
│  Sistema    │
│  Externo    │
└──────┬──────┘
       │ POST /webhooks/trigger/{route_path}?secret=xxx
       │ + payload JSON
       ▼
┌─────────────────────────────────────────────┐
│  Webhook Endpoint                           │
│  - Valida secret_token                      │
│  - Rate limit (100 req/min/IP)              │
│  - Cria payload com webhook_data            │
└──────┬──────────────────────────────────────┘
       │ JobDispatcherService.dispatch_system()
       ▼
┌─────────────────────────────────────────────┐
│  Job Dispatcher                             │
│  1. Cria Job (status=pending)               │
│  2. Busca lista de preferência              │
│  3. Para cada worker (ordem prioritária):   │
│     - Verifica disponibilidade              │
│     - Se disponível: assign + publish       │
│     - Se não: próximo                       │
│  4. Se nenhum: status=queued                │
└──────┬──────────────────────────────────────┘
       │
       ├─────────────────┐
       │                 │
       ▼                 ▼
┌──────────────┐   ┌─────────────────┐
│ Celery Queue │   │  WebSocket      │
│ (priority)   │   │  Broadcast      │
└──────┬───────┘   │  - Job created  │
       │           │  - Status: queue│
       │           │  - ETA calc     │
       │           └─────────────────┘
       ▼
┌─────────────────────────────────────────────┐
│  Celery Worker (execute_job task)           │
│  1. Recebe job                              │
│  2. Atualiza status → running               │
│  3. Emite WS update                         │
│  4. Executa automação                       │
│  5. Salva resultado                         │
│  6. Atualiza status → success/failed        │
│  7. Emite WS update                         │
│  8. Chama promote_next_job()                │
└──────┬──────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│  Promote Next Job                           │
│  1. Busca próximo job na fila do worker     │
│  2. Considera prioridade + FIFO             │
│  3. Promove job → running                   │
│  4. Publica na fila Celery                  │
│  5. Recalcula ETAs dos jobs restantes       │
│  6. Emite WS updates                        │
└─────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│  WebSocket Clients (Frontend)               │
│  - Recebe atualizações em tempo real        │
│  - Atualiza UI automaticamente              │
│  - Mostra ETA, queue_position               │
└─────────────────────────────────────────────┘
```

## 2. Fluxo de Seleção de Worker (Afinidade)

```
Job criado para Automation X
       │
       ▼
Buscar AutomationWorkerPreference
onde automation_id = X
ordenado por priority_order
       │
       ▼
┌──────────────────────────────────────┐
│ Lista de Workers Preferidos          │
│ [Worker A (priority 1),              │
│  Worker B (priority 2),              │
│  Worker C (priority 3)]              │
└──────┬───────────────────────────────┘
       │
       ▼
Para cada Worker na lista:
       │
       ▼
┌──────────────────────────────────────┐
│ Verificar Disponibilidade            │
│ - status == "online" ?               │
│ - last_heartbeat < 60s atrás ?       │
│ - running_jobs < max_concurrency ?   │
└──────┬───────────────────────────────┘
       │
       ├─── SIM ──────┐
       │              ▼
       │        ┌─────────────────┐
       │        │ Atribuir Worker │
       │        │ status=running  │
       │        │ started_at=now  │
       │        └─────────────────┘
       │
       └─── NÃO ─────┐
                     ▼
              Próximo Worker
              na lista
                     │
           (todos indisponíveis?)
                     │
                     ▼
              ┌──────────────┐
              │ status=queued│
              │ Aguarda slot │
              └──────────────┘
```

## 3. Fluxo de Cálculo de ETA

```
Job precisa de ETA
       │
       ▼
┌─────────────────────────────────────────┐
│ DurationEstimationService               │
│ estimate_duration(automation_id,        │
│                   worker_id)            │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ Buscar últimas N execuções              │
│ (N = eta_window = 20)                   │
│ - automation_id = X                     │
│ - worker_id = Y (se disponível)         │
│ - status = "success"                    │
│ - ordenado por finished_at DESC         │
└──────┬──────────────────────────────────┘
       │
       ├─── Tem >= 3 execuções? ───┐
       │                            │
       │ NÃO                        │ SIM
       │                            ▼
       │                   ┌─────────────────┐
       │                   │ Calcular p75    │
       │                   │ das durações    │
       │                   └────────┬────────┘
       │                            │
       ▼                            │
Fallback 1:                         │
Tentar automation_id                │
em qualquer worker                  │
       │                            │
       ├─── Tem >= 3? ──────────────┤
       │                            │
       │ NÃO                        │
       ▼                            │
Fallback 2:                         │
automation.timeout_seconds          │
       │                            │
       └────────────────────────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │ Retorna duração (s)  │
         └──────────┬───────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
    Job RUNNING           Job QUEUED
         │                     │
         ▼                     ▼
estimated_end =       estimated_start = now +
started_at +          soma das durações dos
duration              jobs à frente na fila
                              │
                              ▼
                      estimated_end =
                      estimated_start +
                      duration
```

## 4. Fluxo de Gerenciamento de Fila

```
Worker X termina um job
       │
       ▼
┌─────────────────────────────────────┐
│ promote_next_job(worker_id=X)       │
└──────┬──────────────────────────────┘
       │
       ▼
Worker X está disponível?
(online, heartbeat ok, slots livres)
       │
       ├─── NÃO ──→ return None
       │
       └─── SIM
              │
              ▼
┌─────────────────────────────────────┐
│ Buscar jobs em fila para Worker X  │
│ - Considerar automations que        │
│   preferem Worker X                 │
│ - Ordenar por:                      │
│   1. Prioridade (critical > low)    │
│   2. created_at (FIFO)              │
└──────┬──────────────────────────────┘
       │
       ├─── Nenhum job ──→ return None
       │
       └─── Tem jobs
              │
              ▼
       Pegar primeiro job
              │
              ▼
┌─────────────────────────────────────┐
│ Promover job                        │
│ - status = running                  │
│ - assigned_worker_id = X            │
│ - started_at = now                  │
│ - Publicar na fila Celery           │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ Emitir WebSocket update             │
│ - Job promovido                     │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ Recalcular ETAs                     │
│ - Jobs restantes na fila de X       │
│ - Emitir WS updates                 │
└─────────────────────────────────────┘
```

## 5. Fluxo de Auditoria

```
Qualquer ação no sistema
       │
       ▼
┌─────────────────────────────────────┐
│ AuditService.record()               │
│ - action: string                    │
│ - actor_email: string | None        │
│ - actor_type: user|system|trigger   │
│ - entity_type: job|automation|...   │
│ - entity_id: string                 │
│ - before/after: JSON (opcional)     │
│ - details: string                   │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ Salvar no banco (audit_logs)        │
│ - created_at automaticamente        │
│ - Indexado por: event_type,         │
│   actor_email, resource_type        │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ Disponível via GET /audit           │
│ - Filtros: actor, entity_type,      │
│   action, limit                     │
│ - Ordenado por created_at DESC      │
└─────────────────────────────────────┘
```

## 6. Fluxo de WebSocket Real-time

```
Frontend conecta
       │
       ▼
WS /ws/executions?token=JWT
       │
       ▼
┌─────────────────────────────────────┐
│ Validar JWT token                   │
│ - Extrair user_id                   │
└──────┬──────────────────────────────┘
       │
       ├─── Inválido ──→ Close (4001)
       │
       └─── Válido
              │
              ▼
┌─────────────────────────────────────┐
│ ConnectionManager.connect()         │
│ - Adicionar WebSocket à lista       │
│ - Iniciar Redis listener (se novo)  │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ Enviar confirmação de conexão       │
│ {"type": "connected"}               │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ Loop: aguardar mensagens            │
│ - ping/pong para keep-alive         │
└──────┬──────────────────────────────┘
       │
       │ (Em paralelo)
       │
       ▼
┌─────────────────────────────────────┐
│ Redis Listener                      │
│ - Subscribe "job_updates"           │
│ - Quando recebe mensagem:           │
│   → Broadcast para todos WS         │
└─────────────────────────────────────┘
       │
       │ Job muda de status
       │
       ▼
┌─────────────────────────────────────┐
│ RealtimeService.emit_job_update()   │
│ - Serializar job + ETA + position   │
│ - redis.publish("job_updates")      │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ Todos os backends recebem via       │
│ Redis pub/sub                       │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ Cada backend envia para seus        │
│ WebSocket clients conectados        │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ Frontend recebe update              │
│ - Atualiza UI em tempo real         │
│ - Mostra ETA, status, position      │
└─────────────────────────────────────┘
```

## Observações Importantes

1. **Fallback de Worker**: Se todos os workers preferidos estão indisponíveis, o job permanece em `queued` aguardando. Não há fallback automático para workers fora da lista.

2. **Prioridade de Fila**: Dentro da mesma prioridade (critical, high, normal, low), os jobs são processados em ordem FIFO baseado em `created_at`.

3. **Recálculo de ETA**: Toda vez que um job muda de status (criado, iniciado, concluído), os ETAs dos jobs na fila são recalculados e atualizados via WebSocket.

4. **Multi-instância**: O sistema suporta múltiplas instâncias do backend através do Redis pub/sub para broadcast de WebSocket.

5. **Heartbeat**: Workers devem enviar heartbeat a cada ~30s. Se não enviar em 60s (configurável), é considerado offline.