# Regras de Fila e Prioridade

## Níveis de Prioridade

O sistema suporta 4 níveis de prioridade para jobs:

1. **critical** - Prioridade máxima
2. **high** - Alta prioridade
3. **normal** - Prioridade padrão (usado quando não especificado)
4. **low** - Baixa prioridade

Cada prioridade corresponde a uma fila do Celery independente.

## Interação: Lista de Preferência × Prioridade

### Regra Principal
A **lista de preferência de workers** tem precedência sobre a **prioridade do job**.

### Como Funciona

1. **Job é criado** com uma prioridade (ex: `high`)
2. **Dispatcher busca a lista de preferência** da automação
3. **Para cada worker na lista** (em ordem de `priority_order`):
   - Verifica se está disponível
   - Se SIM: atribui o job e envia para a fila da prioridade
   - Se NÃO: tenta o próximo worker da lista

4. **Se nenhum worker disponível**:
   - Job fica em `status=queued`
   - Aguarda o **primeiro worker da lista** ficar disponível
   - **NÃO** é atribuído a outros workers fora da lista

### Exemplo

**Cenário:**
- Automation "Deploy Prod" tem preferência: `[Worker-A, Worker-B]`
- Job criado com prioridade `critical`
- Worker-A: offline
- Worker-B: busy (max concurrency atingida)
- Worker-C: online e disponível (mas não está na lista)

**Resultado:**
- Job fica em `queued`
- Aguarda Worker-A ou Worker-B ficarem disponíveis
- **NÃO** é atribuído ao Worker-C automaticamente

### Exceção: Sem Lista de Preferência

Se uma automação **não tem lista de preferência configurada**:
- Dispatcher tenta **qualquer worker disponível**
- Primeiro worker online e com capacidade recebe o job
- Comportamento de fallback padrão

## Ordenação da Fila

Quando múltiplos jobs estão aguardando o mesmo worker, a ordem de execução segue:

### 1. Prioridade do Job
Jobs com prioridade mais alta são executados primeiro:
```
critical > high > normal > low
```

### 2. FIFO dentro da Mesma Prioridade
Dentro do mesmo nível de prioridade, usa-se **First In, First Out** baseado em `created_at`:

```python
# Exemplo de ordenação
jobs.sort(key=lambda j: (priority_order[j.priority], j.created_at))

# Onde priority_order = {
#     "critical": 0,
#     "high": 1,
#     "normal": 2,
#     "low": 3
# }
```

### Exemplo de Fila

Jobs aguardando Worker-A:
```
Queue Position | Job ID | Priority | Created At
---------------|--------|----------|-------------
1              | 101    | critical | 10:00:00
2              | 103    | critical | 10:01:00
3              | 102    | high     | 10:00:30
4              | 105    | high     | 10:02:00
5              | 104    | normal   | 09:59:00
6              | 106    | low      | 09:58:00
```

Ordem de execução: `101 → 103 → 102 → 105 → 104 → 106`

## Promoção de Jobs

Quando um worker termina um job, o sistema:

1. **Chama `promote_next_job(worker_id)`**
2. **Busca jobs em fila** que preferem esse worker
3. **Ordena por prioridade + FIFO**
4. **Promove o primeiro** da fila
5. **Recalcula ETAs** dos jobs restantes

### Código Relevante

```python
def promote_next_job(self, worker_id: int) -> Job | None:
    # Buscar jobs que preferem este worker
    queued_jobs = get_queued_jobs_for_worker(worker_id)
    
    # Ordenar por prioridade e created_at
    queued_jobs.sort(
        key=lambda j: (priority_order[j.priority], j.created_at)
    )
    
    # Promover o primeiro
    next_job = queued_jobs[0]
    next_job.status = JobStatus.RUNNING
    next_job.assigned_worker_id = worker_id
    next_job.started_at = now()
    
    # Enviar para Celery
    celery_app.send_task("execute_job", queue=next_job.priority)
```

## Cálculo de Queue Position

O `queue_position` é calculado em tempo real para cada job em fila:

```python
def get_queue_position(self, job: Job) -> int | None:
    if job.status != "queued":
        return None
    
    # Buscar todos os jobs na fila do mesmo worker
    queued_jobs = get_queued_jobs_for_worker(job.assigned_worker_id)
    
    # Ordenar por prioridade + FIFO
    queued_jobs.sort(...)
    
    # Encontrar posição (1-based)
    for idx, queued_job in enumerate(queued_jobs, start=1):
        if queued_job.id == job.id:
            return idx
    
    return None
```

## Impacto no ETA

A posição na fila afeta diretamente o ETA:

```
estimated_start = now + soma das durações dos jobs à frente
estimated_end = estimated_start + estimated_duration
```

### Exemplo

Jobs na fila de Worker-A:
- Job 101 (position 1): duração estimada 5min → inicia em ~0min
- Job 102 (position 2): duração estimada 3min → inicia em ~5min
- Job 103 (position 3): duração estimada 8min → inicia em ~8min

## Configuração de Preferências

### Via API

```http
PUT /api/v1/automations/{id}/worker-preferences
Content-Type: application/json

{
  "preferences": [
    { "worker_id": 1, "priority_order": 1 },
    { "worker_id": 3, "priority_order": 2 },
    { "worker_id": 2, "priority_order": 3 }
  ]
}
```

### Regras de Validação

1. `priority_order` deve ser único por automação
2. Apenas usuários com `can_edit` na categoria podem alterar
3. Workers inativos podem estar na lista mas não receberão jobs
4. Lista vazia = comportamento de fallback (qualquer worker)

## Disponibilidade de Worker

Um worker é considerado **disponível** quando:

```python
def _is_worker_available(self, worker) -> bool:
    # 1. Worker ativo
    if not worker.is_active:
        return False
    
    # 2. Status online
    if worker.status != "online":
        return False
    
    # 3. Heartbeat recente (< 60s)
    if not worker.last_heartbeat_at:
        return False
    
    if now() - worker.last_heartbeat_at > 60s:
        return False
    
    # 4. Capacidade disponível
    running_jobs = count_running_jobs(worker.id)
    if running_jobs >= worker.max_concurrency:
        return False
    
    return True
```

## Considerações de Performance

### 1. Escalabilidade
- Cada worker processa jobs independentemente
- Filas do Celery são isoladas por prioridade
- Cálculo de queue_position é O(n log n) onde n = jobs em fila

### 2. Concorrência
- `max_concurrency` por worker limita execução paralela
- Evita sobrecarga de workers individuais
- Permite fine-tuning por capacidade do servidor

### 3. Rebalanceamento
- Sistema **não rebalanceia** jobs automaticamente
- Job atribuído a um worker permanece naquele worker
- Para mudar worker: cancelar job e criar novo

## Troubleshooting

### Job Preso em Queued

**Sintomas:** Job fica em `queued` indefinidamente

**Causas Possíveis:**
1. Todos os workers preferidos estão offline/busy
2. Worker com heartbeat antigo (>60s)
3. Workers atingiram `max_concurrency`
4. Lista de preferência contém apenas workers inativos

**Soluções:**
1. Verificar status dos workers: `GET /api/v1/workers`
2. Verificar heartbeat: `last_heartbeat_at` recente?
3. Aumentar `max_concurrency` do worker
4. Adicionar mais workers à lista de preferência
5. Remover job da fila e redispatch (admin only)

### Prioridade Não Respeitada

**Sintomas:** Job `high` executado depois de job `normal`

**Causas Possíveis:**
1. Jobs são de diferentes workers (filas independentes)
2. Job `normal` já estava `running` quando `high` chegou

**Verificação:**
```sql
-- Ver fila de um worker
SELECT id, priority, created_at, status
FROM jobs
WHERE assigned_worker_id = 1
  AND status IN ('queued', 'running')
ORDER BY 
  CASE priority
    WHEN 'critical' THEN 0
    WHEN 'high' THEN 1
    WHEN 'normal' THEN 2
    WHEN 'low' THEN 3
  END,
  created_at;
```

## Métricas Recomendadas

Para monitorar o sistema de filas:

1. **Queue Depth**: Número de jobs em `queued` por worker
2. **Average Queue Time**: Tempo médio em fila antes de `running`
3. **Worker Utilization**: `running_jobs / max_concurrency`
4. **ETA Accuracy**: Diferença entre `estimated_end` e `finished_at` real
5. **Starvation**: Jobs em fila há muito tempo (ex: >30min)