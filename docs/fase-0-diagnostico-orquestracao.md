# Fase 0: diagnóstico e propostas

Status: **proposta revisada com as decisões de 09/11/2026, aguardando aprovação final**. Nenhum código, migration, contrato ou ADR
foi alterado nesta fase. Este é o único arquivo criado.

Missão: evoluir o Portal para acompanhar e comandar várias automações em várias
máquinas, com a clareza do portal local da Integração Contábil (tempos, estimativas,
logs e imagens), em dois modos de conexão (agente e direto), e com o frontend refeito
na identidade visual Biason.

## 1. Resumo

- **A base é boa e cobre metade do caminho.** Já existem `Execution`, `TaskExecution`,
  `ExecutionAttempt` e `ExecutionOffer` persistidos, um Scheduler com pools, reservas,
  locks e pontuação explicável, eventos numerados com detecção de lacuna e ACK,
  um stream SSE com retomada por `Last-Event-ID`, Storage com upload por sessão,
  auditoria, retenção, fluxos em DAG e um Agent em .NET que só abre conexão de saída.
- **O que falta é justamente o que o pedido prioriza.** Não existe estimativa
  (o código diz isso explicitamente), não existe o conceito de Item, Grupo ou Etapa,
  e não existe um canal estruturado da automação para o Agent: hoje ela só emite
  stdout e `progress N` em porcentagem.
- **Há conflitos com quatro decisões vigentes**, que exigem ADRs novos antes do código:
  o redesenho (ADR-017), o modo direto (ADR-002 e ADR-005), o executor genérico
  (as tabelas exigem `agent_id`) e a política de "perdido" (hoje volta sozinho à fila).
- **Há decisões que só você pode tomar** (seção 11). A mais importante: de onde vêm os
  itens e os grupos (empresas, matriz e filiais) antes da execução começar.

## 1.1 Decisões registradas (respostas de 09/11/2026)

| # | Pergunta | Decisão | Onde muda o desenho |
|---|---|---|---|
| 1 | Origem dos itens e grupos | **Cadastro de itens no portal, por automação**, com importação do cadastro atual da Integração Contábil (só o cadastro, não o histórico) | Seção 6.5 |
| 2 | Job sem estimativa | Mostrar **"Sem previsão" sempre com o motivo**, em linguagem de operação, e todos os motivos que se aplicarem | Seção 6.4 |
| 3 | TLS do portal | **uvicorn** com certificado da CA da empresa (`--ssl-certfile`, `--ssl-keyfile`, TLS 1.2+) | Fase 1 (`scripts/portal.ps1`) |
| 4 | Eventos `pausa.*` | **Aprovados** | Seção 5.2 |
| 5 | Máquina sem Agent | **Pode existir.** O administrador identifica a máquina ao registrar a automação. A máquina fica ocupada pela automação qualquer que seja o modo; o Agent só centraliza a comunicação em uma conexão | ADR-019, seção 7 |
| 6 | Permissão de telas e logs | **Por automação.** O administrador tem uma **Central de telas**: todas as máquinas ao vivo, em grade como câmeras, com o log ao lado de cada uma. Usuário comum só vê as telas dentro da automação | Seção 8.1 |
| 7 | Etapa partida em duas tentativas | **Soma as partes** como uma execução só | Seção 6.3 |
| 8 | Importar histórico de tempos | **Não.** A estimativa é sempre por etapa, e a da automação é a soma das etapas | Seção 6.3 (regra 10) |
| 9 | Escopo do redesenho | **Todas as telas.** O Biason Comunica é referência de identidade. Imagens ao vivo, logs e estimativas presentes em tudo | Seção 8 |
| 10 | Quem ocupa a máquina | **Depende do modo de execução da automação, obrigatório no registro** (`tela`, `navegador` ou `segundo_plano`). Tela: uma por máquina, somando os dois modos de conexão. Navegador e segundo plano: capacidade do pool. Hoje o manifesto assume `background` quando o modo falta; isso passa a ser **erro de validação** | Seções 3.2 e 6 |
| 11 | "Ao vivo" na Central de telas | **Igual ao portal local:** imagem a cada passo, e nas esperas a última imagem com "N s nesta tela". Sem captura periódica | Seção 8.3 |

## 2. Linha de base medida

Saída real, antes de qualquer alteração:

```
backend> python -m pytest -q
FAILED modules/dispatch/tests/test_dispatch_domain.py::test_resource_reservation_can_convert_or_release
FAILED tests/architecture/test_architecture_context.py::test_catalog_legacy_services_delegate_to_modules
FAILED tests/architecture/test_architecture_context.py::test_gateway_endpoint_does_not_access_orm_directly
3 failed, 156 passed in 6.48s
```

| Falha | Causa | Natureza |
|---|---|---|
| `test_resource_reservation_can_convert_or_release` | `ResourceReservation.create()` passou a exigir `task_execution_id`; o teste não foi atualizado | Teste desatualizado |
| `test_catalog_legacy_services_delegate_to_modules` | Lê `backend/app/services/automation_import_service.py`, removido no corte final | Teste obsoleto |
| `test_gateway_endpoint_does_not_access_orm_directly` | `gateway/agent_gateway/endpoint.py` importa `AgentCommandRecord` do ORM de Dispatch | **Violação real de fronteira** |

Proposta: corrigir as três no início da Fase 1. A terceira é uma correção de código.

Também registrado: a árvore de trabalho já tinha alterações não commitadas antes desta
sessão (remoção do Docker, `scripts/portal.ps1`). Não mexi nelas.

## 3. O que existe versus o pedido

Legenda: ✅ atende · 🟡 parcial, reaproveitar · ❌ falta · ⚠️ conflita

### 3.1 Conceitos

| Pedido | Hoje | Situação |
|---|---|---|
| Automação e Versão | `automations`, `automation_versions`, manifest com hash, pacotes imutáveis | ✅ |
| Execução | `orchestration_executions` | ✅ |
| Job (vai para a fila, roda inteiro em uma máquina) | `task_executions`: unidade que o Scheduler despacha para um Agent | 🟡 Mapear Job = TaskExecution (seção 6.1) |
| Tentativa, nunca sobrescrita | `execution_attempts` com `attempt_number` | ✅ |
| Item (nome vindo do manifesto) | Não existe | ❌ |
| Grupo (chave declarada pela automação) | Não existe | ❌ |
| Etapa declarada no manifesto | Não existe. O manifest só tem `execution.mode`, recursos, capabilities e schemas | ❌ |
| Parâmetros que mudam o trabalho | Não existe | ❌ |
| Formulário gerado do manifesto | `schemas.input` existe no manifest (JSON Schema), mas o frontend não gera formulário | 🟡 |

### 3.2 Fila e despacho

| Pedido | Hoje | Situação |
|---|---|---|
| Pools tela, navegador, segundo plano | Fleet tem `interactive`, `browser`, `background`. O manifest só aceita `interactive` e `background` | 🟡 Falta `browser` no manifest |
| Só máquina com automação, requisitos e online | `FindEligibleAgents` com capabilities, pools, snapshot e sessão interativa | ✅ |
| Um job de tela por máquina, nos dois modos | `ResourceLock` existe, mas com `agent_id` obrigatório. Não cobre instância direta | ⚠️ Precisa de chave por máquina |
| Grupo nunca se divide | Não há grupo | ❌ |
| Sem duplicata (automação + item + parâmetros) | `idempotency_key` só por execução, enviada pelo cliente | 🟡 |
| Prioridade e reordenação manual | `priority` inteiro em `task_executions`. Sem posição manual | 🟡 |
| Sem nova tentativa automática para tela | `max_attempts: 1` por padrão, mas **`retry_on_lost: True`** | ⚠️ |
| Máquina sem sinal: "perdido", não volta sozinho | `resilience.py` marca `lost` e **devolve a tarefa para `ready`** | ⚠️ Conflita com o pedido |
| Continuar volta para a mesma máquina | `preferred_agent_id` é só um peso de pontuação | 🟡 Precisa de afinidade obrigatória |
| Fila de vários jobs, mais longos primeiro | Ordenação por prioridade e FIFO | ❌ |
| Sequência via fluxos (DAG) | `flows`, `flow_versions`, `flow_executions`, `flow_node_executions` | ✅ Falta só a estimativa pelo caminho mais longo |
| Motivo da espera | `dispatch_decisions` grava candidatos e motivo da rejeição | 🟡 Base boa para "por que está esperando" |

### 3.3 Telemetria e tempo real

| Pedido | Hoje | Situação |
|---|---|---|
| Eventos numerados, idempotentes, com lacuna | `execution_events.event_sequence`, `event_acknowledgements` (faixas faltantes e duplicatas), `inbox_messages` | ✅ |
| Tipos `etapa`, `item`, `passo`, `atencao`, `espera` | Só `task.progress`, `log`, `metric`, `artifact.*` etc. | ❌ Contrato novo |
| Canal automação → agente | stdout/stderr e `progress N` (0–100) lidos pelo ExecutionHost | ❌ Sem eventos estruturados nem comandos de volta |
| Tempo real para o navegador | SSE por execução em `/telemetry/{id}/stream` com `Last-Event-ID` | 🟡 Ver riscos abaixo |
| Recuperar o que perdeu ao reconectar | Reenvio do que veio depois do `Last-Event-ID` (até 500) | 🟡 Limite fixo de 500 e só por execução |
| Painel com todas as execuções em tempo real | O SSE é por execução. O WebSocket `/ws/executions` existe, mas nada publica nele | ❌ |

Riscos do tempo real atual:

1. O publicador é **em memória, no processo**. Eventos gravados por outro processo
   (Celery worker, beat, ou uvicorn com mais de um worker) não chegam ao navegador.
   Proposta: `LISTEN/NOTIFY` do PostgreSQL ou pub/sub do Redis como transporte. Os dois
   são transporte, não fonte de verdade, então não ferem o ADR-004.
2. O JWT do usuário vai na **URL** (`?token=` no SSE e no WebSocket). Isso conflita com
   a regra "credenciais nunca em URL". Proposta: cookie `HttpOnly` de sessão ou um
   ticket de uso único de 30 s trocado antes de abrir o stream.

### 3.4 Imagens, logs e segurança

| Pedido | Hoje | Situação |
|---|---|---|
| Binários por HTTPS/armazenamento | Storage com `initiate-upload`, bytes, `complete`, MinIO/S3 | ✅ ADR-006 |
| URLs temporárias, nunca públicas | `download` redireciona para URL do storage | 🟡 Conferir expiração e se o bucket é privado |
| Permissão de imagens e logs por automação | Permissão por **categoria** (`ensure_automation_action` resolve a categoria) | 🟡 Decisão 6: concessão **por automação** (`automation_grants`: usuário ou time, automação, ações `ver_execucoes`, `ver_telas_e_logs`, `editar_itens`, `executar`, `controlar`), mais a permissão global `central_de_telas` para administradores |
| Auditoria de cada visualização | `audit_events` existe; ver imagem não é auditado | 🟡 |
| Retenção por automação, exclusão automática | `retention_policies` em Governance, sem exclusão de prints | 🟡 |
| Miniaturas no portal, recusar imagem corrompida | Não existe | ❌ |
| Remoção de segredos no log | Não encontrei no caminho de Telemetry | ❌ |
| HTTPS/WSS com TLS 1.2+ e CA da empresa | **O portal roda em HTTP puro** (`uvicorn` em `0.0.0.0:8000`, `BACKEND_PUBLIC_URL=http://...`). O Agent usa `ClientWebSocket` e valida o certificado quando a URL é `wss://` | ⚠️ Falta TLS do lado do portal (pergunta 3) |

### 3.5 Máquinas e notificações

| Pedido | Hoje | Situação |
|---|---|---|
| Conectividade, saúde, ocupação, sessão logada ou bloqueada, versão, automações | Estados multidimensionais (ADR-015), `interactive_session_snapshots.locked`, capabilities, snapshots | ✅ Base pronta |
| Instâncias diretas "não gerenciadas" | Não existe | ❌ |
| Notificações por usuário, sem duplicata | Não existe nada de e-mail no backend | ❌ |

### 3.6 Frontend

| Pedido | Hoje | Situação |
|---|---|---|
| Painel, Fila, Acompanhar, Nova execução, Histórico e tempos, Máquinas | Next.js 15 + Tailwind, sem biblioteca de UI. Páginas `dashboard`, `dispatch`, `executions/[id]`, `workers` existem, mas sem nada de estimativa, passos ou imagens | 🟡 Estrutura reaproveitável, telas novas |
| Identidade Biason | Paleta grafite + **marigold**, fontes Segoe/Trebuchet (o `design-system.md` cita Inter e Space Grotesk, mas o CSS usa Segoe) | ⚠️ ADR-017 proíbe redesenhar |
| Termos | Telas "Workers" e "Jobs" (legado) | 🟡 Trocar por "Máquinas" e por Job no sentido novo |
| Testes visuais | Nenhum teste no frontend, nem Playwright | ❌ |

## 4. Conflitos com ADRs e ADRs propostos

Nenhum destes foi gravado em `docs/adrs/`. Só entram depois da sua aprovação.

### ADR-018 (proposto): Modo direto de conexão

- **Conflita com:** ADR-002, porque o Agent deixa de ser o único execution plane, e
  ADR-005, que trata de conexão por Agent.
- **Decisão proposta:** existe um segundo tipo de executor, a *instância direta*
  (automação + máquina). Ela fala com o portal só por conexão de saída e usa o mesmo
  contrato de eventos. O Agent continua sendo o modo recomendado e o único que verifica
  a integridade do código. A instância direta é sempre marcada "não gerenciada".
- **Consequência de modelo:** `execution_attempts`, `execution_offers`,
  `execution_events`, `resource_reservations` e `resource_locks` hoje exigem `agent_id`
  e `agent_instance_id`. Proposta: introduzir `executor_type` (`agent` | `direct`) e
  `executor_id`, mantendo as colunas de Agent anuláveis, com restrição de "exatamente um
  dos dois" e migração aditiva.
- **Oferta e commit no modo direto:** a instância direta não negocia oferta. Ela
  recebe o job já reservado (equivalente a um commit implícito). `ExecutionOffer`
  continua exclusiva do Agent. Isso preserva o ADR-007: oferta rejeitada continua não
  sendo falha.

### ADR-019 (proposto): Máquina como entidade própria

- **Motivo:** a trava de tela precisa valer "por máquina, nos dois modos". Hoje "máquina"
  é implícita no Agent.
- **Decisão proposta:** entidade `Machine` em Fleet (nome, identidade, aprovação),
  cadastrada pelo administrador. Ela pode ter Agent, instâncias diretas ou os dois. O
  Agent aponta para a máquina; a instância direta também, escolhida pelo administrador
  na aprovação. A trava de tela usa a chave `machine:{id}:screen`, e a máquina aparece
  como "ocupada por <automação>" qualquer que seja o modo. O Agent não ganha prioridade
  sobre a instância direta: a diferença entre os modos é só o transporte (uma conexão
  centralizada) e a verificação do pacote.

### ADR-020 (proposto): Redesenho do frontend com a identidade Biason

- **Substitui:** ADR-017 (preservação do design).
- **Decisão proposta:** refazer a camada visual inteira (tokens, tipografia, shell,
  componentes e todas as telas) com a identidade Biason, usando o portal local da
  Integração Contábil como referência de arquitetura de informação. Componentes e
  contratos de API continuam reaproveitados onde fizer sentido. As regras de "sem mock
  permanente" e "estado vazio real" do ADR-017 continuam valendo.
- Também atualiza o `AGENTS.md` ("Preservar o design atual"), que precisa refletir a
  nova decisão.

### Ajuste de política (sem ADR novo, mas muda comportamento)

- `retry_on_lost` passa a ser `false` por padrão. Uma tentativa perdida leva o Job ao
  estado **perdido**, que exige decisão humana (Continuar ou Recomeçar).
- Automação de tela nunca tem nova tentativa automática, a menos que o manifesto
  declare `seguro_repetir: true`.

## 5. Contrato de telemetria da automação (proposta)

Fica em `contracts/automation-events/v1/`, separado do protocolo Portal–Agent, porque é
emitido pela automação e não pelo Agent. O Agent apenas o transporta dentro do
`execution.event.batch` que já existe.

### 5.1 Envelope de cada evento

```json
{
  "protocol_version": "automation-events/1",
  "event_id": "uuid",
  "sequence": 42,
  "type": "item.iniciado",
  "occurred_at": "2026-11-09T14:03:21.512Z",
  "payload": { }
}
```

- `sequence` começa em 1 por tentativa e é estritamente crescente. Repetição do mesmo
  `event_id` é ignorada; um buraco na sequência é registrado em `event_acknowledgements`
  (que já existe).
- Contexto (execução, job, tentativa, executor) **não vem da automação**: o portal
  deduz pelo token do job ou pela conexão do Agent. Assim uma automação não consegue
  escrever na execução de outra.
- Limites: 64 KB por evento, 500 eventos por lote, taxa por tentativa configurável.

### 5.2 Tipos

| Tipo | Payload | Observação |
|---|---|---|
| `etapa.iniciada` | `etapa`, `item?`, `tarefas_previstas?` | `etapa` é uma chave declarada no manifesto |
| `etapa.concluida` | `etapa`, `item?`, `situacao` (`ok`/`erro`/`interrompida`), `tarefas` | Base da estimativa |
| `item.iniciado` | `item`, `rotulo`, `grupo?`, `configuracao?` | `configuracao` leva os valores que mudam o trabalho (ex.: `separar_por_custo`) |
| `item.concluido` | `item`, `situacao`, `resumo` (até 300 caracteres, sem valores sensíveis) | |
| `progresso` | `atual`, `total`, `rotulo?` | "centro 18 de 50" |
| `log` | `nivel`, `texto`, `espera` (bool) | O portal remove segredos antes de gravar |
| `passo` | `rotulo`, `tipo` (`abriu`/`fechou`/`acao`/`falha`), `imagem_id?` | A imagem sobe antes por HTTPS; o evento só referencia |
| `atencao` | `item`, `motivo`, `tabela` (`colunas`, `linhas`, máx. 500 linhas) | Ex.: rubricas a parametrizar |
| `espera.atualizada` | `desde`, `rotulo` | Sem imagem nova |
| **`pausa.iniciada` / `pausa.concluida`** | `motivo` (`reinicio`, `espera_externa`) | **Adição minha**, necessária para a regra 7 da estimativa. Precisa de aprovação |

O fim e o início da tentativa continuam sendo `execution.started`, `execution.completed`
e `execution.failed`, que já existem. Automação simples emite só esses e `log`.

### 5.3 Transporte no modo agente

Hoje a automação só tem stdout. Proposta: o ExecutionHost abre um **named pipe local por
tentativa**, com nome e token entregues por variáveis de ambiente
(`AUTOMATION_EVENTS_PIPE`, `AUTOMATION_EVENTS_TOKEN`), no mesmo padrão dos pipes que ele
já usa com o Agent Service.

- É bidirecional: por ele chegam os comandos, como "parar depois do item atual".
- Não mistura com o stdout da automação, que continua virando `log`.
- A ACL do pipe restringe o acesso ao usuário da sessão, e o token impede outro
  processo do mesmo usuário de injetar eventos sem conhecê-lo.
- Imagens: o SDK grava o JPEG em `AUTOMATION_ARTIFACTS_PATH` e o Agent faz o upload pelo
  fluxo de Storage que já existe. Nada de imagem pelo WebSocket.

### 5.4 Transporte no modo direto

- Eventos: `POST /api/v1/direto/jobs/{job_id}/eventos` em lotes, com o token do job.
- Imagens: o mesmo fluxo de Storage (`initiate-upload`, bytes, `complete`) autorizado
  pelo token do job.
- Jobs e comandos: **long-poll HTTPS** (`GET .../comandos?espera=30`). Escolhi isso em vez
  de WSS para a primeira versão porque atravessa proxy sem ajuste e é mais simples de
  revogar. Também é conexão de saída. Dá para trocar por WSS depois sem mudar o SDK.

### 5.5 SDK Python

```python
from portal_automacoes import Automacao

with Automacao.conectar() as a:          # modo vem de configuração, não do código
    with a.etapa("iniciar"):
        ...
    for empresa in empresas:
        with a.item(empresa.codigo, rotulo=empresa.nome, grupo=empresa.matriz,
                    configuracao={"separar_por_custo": empresa.separa}):
            with a.etapa("rubricas", tarefas_previstas=len(centros)):
                for i, c in enumerate(centros, 1):
                    a.progresso(i, len(centros), f"centro {c}")
                    a.passo("Gerar acionado", tipo="acao", imagem=print_da_janela())
            if pendentes:
                a.atencao("Rubricas a parametrizar", colunas=[...], linhas=[...])
        if a.deve_parar():               # pedido de "parar depois do item atual"
            break
```

- Dois transportes atrás da mesma interface: `TransporteAgente` (pipe) e
  `TransporteDireto` (HTTPS). A escolha vem de `PORTAL_MODO` ou arquivo de configuração.
- Fila local em disco para eventos não confirmados, com reenvio idempotente.
- O SDK recusa imagem vazia ou de cor única antes de enviar, como o portal local já faz.

## 6. Modelo de dados (proposta)

### 6.1 Mapeamento dos conceitos

| Conceito do pedido | Entidade | Contexto | Novo? |
|---|---|---|---|
| Execução | `Execution` | Orchestration | Já existe |
| Job | `TaskExecution` | Orchestration | Já existe; ganha `grupo`, `chave_dedup`, `posicao_manual`, `maquina_prevista_id`, estado `perdido` |
| Tentativa | `ExecutionAttempt` | Orchestration | Já existe; ganha executor genérico e `machine_id` |
| Item | `ExecutionItem` | Orchestration | **Novo** |
| Etapa medida | `StepRun` | Telemetry | **Novo**, projeção dos eventos |
| Plano de tarefas | `StepPlan` | Orchestration | **Novo**: tarefas previstas e feitas por item e etapa (para a retomada) |
| Estimativa congelada | `EstimateSnapshot` | Telemetry | **Novo** |
| Máquina | `Machine` | Fleet | **Novo** (ADR-019) |
| Instância direta | `DirectInstance` | Fleet | **Novo** (ADR-018) |

"Job" é o nome na tela e na documentação; no código continua `TaskExecution`, para não
colidir com a tabela legada `jobs`.

### 6.2 `step_runs`: o histórico que alimenta a estimativa

| Coluna | Uso |
|---|---|
| `automation_id`, `automation_version_id` | Base é por automação (regra 2) |
| `item_chave` (nulo em etapa sem item) | Regras 1 e 5 |
| `etapa` | Regra 2 |
| `assinatura_trabalho` | Hash da `configuracao` do item, só das chaves declaradas no manifesto (regra 6) |
| `situacao` (`ok`/`erro`/`interrompida`) | Só `ok` é base (regra 4) |
| `tarefas` | Regra 3 |
| `duracao_bruta_s`, `pausas_s`, `duracao_s` | `duracao_s` = bruta − pausas (regra 7) |
| `execution_id`, `attempt_id`, `machine_id`, `modo` | Rastreio e comparação futura de máquinas, sem ajustar a estimativa por máquina |
| `inicio`, `fim` | Regra 8 (corte temporal) |

Índice principal: `(automation_id, etapa, item_chave, assinatura_trabalho, fim DESC)
WHERE situacao = 'ok'`.

### 6.3 As 11 regras no modelo

1. Consulta sempre filtra `item_chave` = item do job. Nunca existe fallback para outro item.
2. Mediana das 5 últimas linhas `ok` daquela automação, etapa e item.
3. Etapa marcada `por_tarefa` no manifesto: mediana de `duracao_s / tarefas` vezes as
   tarefas restantes do `StepPlan`.
4. `erro` e `interrompida` ficam em `step_runs`, mas fora da consulta.
5. Etapa com `por_item: false` ignora `item_chave` e usa todas as execuções da automação.
6. Mudou a `assinatura_trabalho`, não há linha compatível: começa sem histórico.
7. `pausa.*` alimenta `pausas_s` e não entra em `duracao_s`.
8. Só entram linhas com `fim` anterior ao início da tentativa. A estimativa calculada é
   gravada em `estimate_snapshots` no início da tentativa e é ela que a tela mostra
   depois. Assim nem uma limpeza por retenção muda o número.
9. Sem base: `null`, com o rótulo "Sem histórico", fora da soma, e a contagem de etapas
   sem base é mostrada.
10. Job = soma das etapas; Execução = soma dos jobs (e, em fluxo, caminho mais longo).
11. Toda estimativa carrega `base`: `{tipo: "item" | "automacao", amostras: n}`.

Retomadas (decisão 7): quando a etapa roda em duas tentativas da mesma execução, as
partes `ok` são somadas e contam como uma execução só na mediana. Se alguma parte terminou
em `erro` e a etapa não foi concluída depois, a execução inteira fica fora da base.

Sem importação de histórico (decisão 8): toda automação começa sem base, e a estimativa
vai se formando etapa por etapa, item por item.

### 6.4 Estimativa da fila

Simulação determinística, rodada a cada evento relevante e quando a fila ou as máquinas
mudam:

1. Ordem da fila: prioridade, depois posição manual, depois lote de enfileiramento e,
   dentro do mesmo lote, **maior estimativa primeiro**.
2. Para cada máquina: livre em `agora + restante do job atual`. Restante = estimativa −
   decorrido. Se já passou da estimativa, o restante é desconhecido.
3. Cada job vai para a máquina compatível que fica livre antes (algoritmo LPT guloso).
4. Término da execução = término do último job dela.

O Scheduler real segue a **mesma ordem**: quando uma máquina libera, ela pega o primeiro
job compatível da fila. Assim a previsão e o despacho não divergem.

"Sem previsão" nunca aparece sozinho (decisão 2). A previsão guarda uma lista de motivos
estruturados, e a tela mostra todos os que se aplicam, por exemplo:

| Código | Texto na tela |
|---|---|
| `sem_historico_etapa` | "Integração Contábil · 5066: etapa Rubricas rodando pela primeira vez, sem histórico de estimativas (2 de 7 etapas sem base)" |
| `aguardando_job_sem_previsao` | "Aguardando o término de Integração Contábil · 5081 na Máquina DP-01, que roda pela primeira vez sem histórico" |
| `acima_da_estimativa` | "Integração Contábil · 5066 já passou 12 min da estimativa na Máquina DP-01" |
| `configuracao_mudou` | "A empresa 5066 mudou 'Separar por custo': o histórico anterior não vale mais" |
| `maquina_sem_sinal` | "Máquina DP-01 sem sinal desde 14:05" |
| `sessao_bloqueada` | "Máquina DP-01 com a sessão do Windows bloqueada" |
| `sem_maquina_compativel` | "Nenhuma máquina aprovada tem a Integração Contábil instalada" |
| `job_perdido_na_maquina` | "Máquina DP-01 tem um job perdido aguardando decisão" |

Quando há estimativa parcial (algumas etapas com base, outras sem), a tela mostra o valor
conhecido como **mínimo** ("pelo menos 18 min") junto com os motivos, em vez de esconder
o número.

### 6.5 Cadastro de itens por automação (decisão 1)

O portal passa a guardar os itens de cada automação, e a prévia, os grupos e o despacho
saem dele.

- **O manifesto declara o item:** nome na tela ("Empresa"), campo chave (`codigo`), campo
  de grupo (`matriz_codigo`), JSON Schema dos atributos (nome, pasta de destino, e-mail,
  separar por custo, rubricas ignoradas...) e quais atributos mudam o trabalho
  (`separar_por_custo`), que alimentam a regra 6.
- **Tabela `automation_items`** em Catalog: `automation_id`, `chave`, `rotulo`,
  `grupo_chave`, `atributos` (JSONB validado pelo schema), `ativo`, auditoria de quem
  alterou. Grupo de um nível só, como no portal local (matriz e filiais).
- **Formulários gerados do schema**, na tela da automação: lista, filtros, edição,
  ativar e inativar, importar e exportar planilha com prévia antes de gravar (a mesma
  experiência do portal local).
- **Na execução:** o job leva os itens e os atributos no momento do pedido
  (`input.json` no modo agente, resposta do job no modo direto). Mudar o cadastro depois
  não altera um job que já está na fila.
- **Ações a partir da atenção:** o evento `atencao` pode declarar ações por linha, por
  exemplo "Ignorar" → adicionar a rubrica à lista `rubricas_ignoradas` do item (ou da
  matriz). O portal executa a ação no cadastro, com permissão e auditoria, e o
  "Continuar de onde parou" já usa o valor novo.
- **Importação inicial da Integração Contábil:** só o cadastro (`dados/empresas.db`:
  empresas, matriz e filiais, rubricas ignoradas), com prévia. O histórico de tempos não
  é importado (decisão 8).
- **Privacidade:** atributos têm e-mails e caminhos de clientes; ver e editar o cadastro
  segue a permissão por automação.

## 7. Modo direto: segurança

| Requisito | Proposta |
|---|---|
| Inscrição com código de uso único | Reaproveita o padrão de `agent_registration_tokens`: o administrador gera um código de uso único com validade curta |
| Par de chaves na máquina | O SDK gera ECDSA P-256. A chave privada é cifrada com DPAPI **escopo do usuário** (`CryptProtectData` sem `LOCAL_MACHINE`) |
| Aprovação | A inscrição fica "pendente". O administrador aprova e **escolhe a máquina** na lista de `Machine`, que ele mesmo cadastrou (com ou sem Agent). O nome informado pela automação aparece só como dica |
| Sessão | Desafio com nonce, assinado pela chave privada, trocado por um token de acesso de 10 minutos com escopo `instancia:{id}` |
| Token do job | Opaco, guardado como hash, válido só para aquele job e até o fim do lease |
| Segredos | Entregues só no início do job, pelo token do job, cifrados no portal como já é feito em Governance |
| Escopo mínimo | A credencial só alcança `registrar`, `meus jobs`, `eventos e arquivos dos meus jobs` e `meus comandos` |
| Revogação e quarentena | Revogada: nenhuma rota responde. Quarentena: conecta, mas não recebe jobs |
| Versão mínima | Configurável por automação; abaixo dela a instância é recusada |
| Auditoria | Inscrição, aprovação, conexão, recusa, revogação e quarentena |

Avaliação: o fluxo de desafio cabe em uma fase. A alternativa de segredo por instância
com hash fica só como plano B, registrado como dívida se for necessária.

Limite que será documentado: no modo direto o portal não impede que alguém abra outra
automação de tela manualmente na mesma sessão. O Agent consegue. **Recomendação: modo
agente para automações de tela.**

## 8. Frontend com a identidade Biason

Todas as telas são refeitas (decisão 9). Referências, nesta ordem de peso:

1. **Portal da Integração Contábil:** a experiência. Imagens ao vivo, logs e estimativas
   são o centro, não um detalhe escondido numa aba.
2. **Biason Comunica:** a identidade já aplicada a um sistema interno (navy, Barlow,
   eyebrow com tracinho, barra superior em degradê, cartões, selos de status).
3. **Skill `identidade-biason`:** as regras de família. A parte de site institucional
   (hero com foto, WhatsApp, rodapé com CNPJ, fotos de pessoas) não se aplica a um
   console de operações.

### 8.1 Tokens e tipografia

| Elemento | Decisão | Origem |
|---|---|---|
| Âncora | `#142845` como `--primary`, substituindo o marigold | Skill |
| Navy de superfície | `--noite #141e37`, `--noite-2 #0e1729`, `--marinho #102947`, `--marinho-2 #1b3a63` | Comunica |
| Acento frio | `--nevoa #b5ccde` (borda da barra superior, eyebrow, foco) | Comunica |
| Acento quente | `--areia #d7bf91`, só em detalhes. Nunca como cor de status | Skill e Comunica |
| Fundo e texto | `--fundo #eef2f6`, `--titulo #141e37`, `--texto #2e3a52`, `--apoio #5e6b84` | Comunica |
| Status | ok, aviso, erro e info com fundo e borda (`--ok #1d7a4c` / `#e7f5ee`...), mais "perdido", "atenção" e "na fila" | Comunica + portal local |
| Fonte | **Barlow** (é o desenho do logotipo) no corpo; **Barlow Condensed** em títulos e nos números grandes de tempo (decorrido, falta, término), com `tabular-nums`; mono só para log, IDs e horários | Comunica |
| Títulos | Peso 600–700, eyebrow em maiúsculas com tracinho acima | Skill e Comunica |
| Logo | `logo-biason-branco.png` sobre navy, `logo-biason-azul.png` sobre claro (copiados do Comunica) | Comunica |
| Tema escuro | **Novo** (o Comunica não tem): superfícies em navy `#0e1729`/`#141e37`, texto névoa, status com fundo escuro. Claro e escuro via tokens, com contraste AA | Proposta |
| Fontes servidas pelo próprio portal | `next/font` com os arquivos no build, para o portal interno não depender da internet ao abrir | Proposta |

### 8.2 Estrutura

- **Barra superior** em navy com degradê e borda névoa, como no Comunica: logo,
  "Portal de Automações", busca e o usuário. **Menu lateral** com contadores de atenção
  (como o portal local) e o ambiente atual.
- **Faixa de execução** fixa abaixo da barra quando há algo rodando: automação, item,
  etapa, progresso, decorrido, falta e término previsto. Clique leva ao Acompanhar.
- **Imagens, logs e estimativas em tudo:**
  - Toda linha de execução (Painel, Histórico, página da automação, Máquinas) mostra a
    miniatura da tela atual, a etapa e "falta ~N min" ou "Sem previsão" com o motivo.
  - Toda fila mostra início e término previstos.
  - Toda página de máquina mostra a tela atual e o log ao vivo do que está rodando nela.
  - Toda página de automação mostra as execuções dela ao vivo, com tela e log.

### 8.3 Central de telas (decisão 6)

Para administradores, no Painel: todas as máquinas ao vivo, como uma central de câmeras.

- Grade de 1, 2, 4, 6 ou 9 telas, escolhida pelo administrador e lembrada no navegador.
- Cada quadro: máquina, automação · item, etapa, barra de progresso, decorrido, falta e
  término previsto, a tela do último passo com "N s nesta tela" durante as esperas, e o
  **log ao lado**, com as últimas linhas, cores por nível e esperas ocultas.
- Borda pela situação: rodando, aguardando uma pessoa, erro, máquina sem sinal.
  Máquina livre aparece como "Livre" e mostra o próximo job da fila e quando começa.
- Clique em um quadro: amplia com as setas de passos, ou abre o Acompanhar completo.
- Só carrega imagem de tamanho médio a cada passo novo; a imagem cheia só abre quando
  ampliada. Isso mantém 9 quadros fluidos.
- Auditoria: abrir a Central registra o administrador e as execuções visíveis, e cada
  mudança do conjunto também é registrada. Ampliar uma tela registra a visualização.
- Usuário comum não tem a Central. Ele vê as telas só dentro da automação em que tem a
  permissão `ver_telas_e_logs`.

## 9. Testes: o que precisa ser preparado

| Pedido | Situação | Proposta |
|---|---|---|
| Unitários das 11 regras | Fácil: a estimativa será uma função pura no domínio de Telemetry | Um teste por regra, com nome da regra |
| Mutação | `mutmut` não roda nativo no Windows | `cosmic-ray`, que roda no Windows, só nos módulos de estimativa e fila |
| Agente simulado e automação direta simulada | O repositório já tem um harness de certificação em .NET e Python | Agente simulado em Python falando o protocolo real pelo WebSocket, mais uma automação direta usando o SDK |
| 18 cenários com saída legível | Não existe | Um comando `python -m tools.cenarios` que roda os 18 e imprime ✅/❌ com o motivo |
| Playwright desktop e celular, claro e escuro | Não instalado | `@playwright/test` como dependência de desenvolvimento, com capturas em `frontend/test-results/` |
| 10 execuções simultâneas | Não existe | Gerador de carga com 10 automações simuladas emitindo eventos, medindo a latência da tela |

## 10. Plano de migração e fases

Ajustes às fases do pedido (em negrito o que muda):

| Fase | Conteúdo |
|---|---|
| 0 | Este diagnóstico |
| 1 | **Corrigir os 3 testes quebrados; gravar ADR-018, 019 e 020 e atualizar o `AGENTS.md`; TLS no uvicorn com o certificado da CA;** contrato `automation-events/v1` (com `pausa.*`); SDK Python com os dois transportes; **pipe de eventos no ExecutionHost (.NET)**; agente simulado e automação direta simulada |
| 2 | `ExecutionItem`, `StepRun`, `StepPlan`, `EstimateSnapshot`, `Machine`, executor genérico, **`automation_items` e item no manifesto** (migrations aditivas); regras de estimativa com testes e mutação, incluindo os motivos de "Sem previsão" |
| 3 | Fila, despacho LPT, estimativa da fila, trava de tela por máquina, estado "perdido", dedup; **design system Biason (tokens, fontes, shell, componentes, tema claro e escuro)** e tela Fila já no visual novo |
| 4 | Acompanhar uma execução: tempo real via `LISTEN/NOTIFY`, stream sem token na URL, imagens com miniatura, log; **concessões por automação** para telas e logs |
| 5 | Painel com a **Central de telas**, Gantt por máquina, Histórico e tempos, Máquinas, **cadastro de itens com importação da Integração Contábil** |
| 6 | Inscrição e revogação do modo direto, notificações, retenção, remoção de segredos, **migração visual das telas administrativas restantes** (usuários, papéis, segredos, auditoria, agendamentos...), documentação |

Princípios de migração:

- Toda migration é aditiva. Colunas de Agent viram anuláveis, nada é apagado.
- A tabela legada `jobs` e as telas "Jobs" e "Workers" continuam até a tela nova as
  substituir, conforme o `docs/migration.md`.
- A Integração Contábil vira a primeira automação real. O portal local dela continua
  funcionando até a versão pelo portal central ser validada em lote real.

## 11. Perguntas

Nenhuma pendente. Todas as respostas estão na seção 1.1 (decisões 1 a 11).

## 12. Riscos que continuam abertos

- **O Agent é .NET e o SDK é Python.** O pipe de eventos exige mudança no ExecutionHost,
  que tem certificação própria. Isso aumenta a Fase 1.
- **Estimativa só fica útil com histórico.** Nas primeiras execuções de cada item, o
  correto é "Sem histórico", e o painel vai parecer vazio.
- **A Integração Contábil nunca rodou o caminho completo até o TXT em lote real.**
  Usá-la como automação de referência traz junto as pendências dela.
- **Tela no modo direto** depende de disciplina operacional, como documentado acima.
- **SSE em memória** precisa ser trocado antes do teste de 10 execuções simultâneas,
  senão o teste passa num processo só e falha em produção.
- Não verifiquei expiração real das URLs do Storage nem a política do bucket. Fica para
  a Fase 4, com teste.
