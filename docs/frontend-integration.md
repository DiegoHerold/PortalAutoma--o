# Integracao do Frontend

Status: vigente.

O frontend atual deve preservar design, layout, navegacao visual, componentes,
temas, cores e tipografia. Esta etapa reorganiza o backend; a reconexao visual
sera feita depois, sem redesenhar as telas.

## Consumo atual de APIs

| Tela ou area | Endpoint atual | Contrato atual | Novo modulo responsavel | Mudanca necessaria | Momento recomendado |
|---|---|---|---|---|---|
| Login | `/auth/login`, `/auth/me` | `TokenResponse`, `CurrentUser` | Access | Manter adaptador enquanto Access e migrado | Etapa Access |
| Dashboard | `/jobs`, `/workers`, `/automations`, WS `/ws/executions` | `Job`, `Worker`, `Automation` | Orchestration, Fleet, Catalog, Telemetry | Renomear Jobs/Workers para Execution/Agent no contrato, preservando layout | Apos modelos persistentes |
| Automacoes | `/automations`, `/automations/{id}`, imports ZIP/GitHub | `Automation`, `AutomationVersion`, import preview | Catalog, Storage, Governance | Migrar services para casos de uso Catalog | Etapa Catalog |
| Jobs | `/jobs`, `/jobs/{id}`, `/jobs/{id}:cancel` | `Job` | Orchestration, Dispatch | Substituir por Execution/TaskExecution/Attempt/Offer | Etapa Orchestration/Dispatch |
| Execucoes | `/executions`, `/executions/{id}` | `Execution` legado | Orchestration, Telemetry | Separar Attempt e eventos estruturados | Etapa Telemetry |
| Workers | `/workers`, `/workers/{id}`, `/workers/installer-config` | `Worker` | Fleet | Migrar para Agent/AgentInstance mantendo tela visual | Etapa Fleet |
| Gatilhos | `/triggers` | Trigger legado | Orchestration | Converter para origem/flow/schedule conforme dominio | Etapa Orchestration |
| Agendamentos | `/schedules`, `/schedules/calendar` | Schedule legado | Orchestration | Preservar UX, trocar backend para Schedule/ScheduleExecution | Etapa Scheduling |
| Usuarios, roles, categorias | `/users`, `/roles`, `/categories` | Access atual | Access, Catalog | Reaproveitar auth/permissoes validas | Etapa Access |
| Auditoria | `/audit` | AuditEntry | Governance | Migrar para AuditEvent | Etapa Governance |
| GitHub integrations | `/integrations/github/*` | GitHubIntegration/discovery | Catalog infrastructure | Criar porta GitHubSourcePort | Etapa Catalog |

## Rotas Catalog migradas nesta etapa

| Area | Rota | Status |
|---|---|---|
| Automacoes | `GET/POST /automations`, `GET/PUT/DELETE /automations/{id}` | Compatibilidade delegando para Catalog |
| Importacao | `POST /automations/import/upload`, `POST /automations/import/{id}/confirm` | Producer legado + confirmacao modular |
| Versoes | `GET /automations/{id}/versions`, `POST /automations/{id}/versions` | Consulta/criacao modular |
| Versoes | `POST /automation-versions/{id}/validate|publish|deprecate|block` | Modular |
| Packages | `POST /automation-versions/{id}/package-uploads`, `PUT /package-uploads/{id}/bytes`, `POST /package-uploads/{id}/complete|abort` | Modular |
| Runtimes | `GET/POST /runtimes`, `POST /runtimes/{id}/versions`, `POST /runtime-versions/{id}/publish|deprecate|block` | Modular |

## Rotas Fleet migradas nesta etapa

| Area | Rota | Status |
|---|---|---|
| Agents | `GET /agents`, `GET /agents/{id}`, `PATCH /agents/{id}` | Modular |
| Registro | `POST /agents/registration-tokens`, `POST /agents/register` | Modular |
| Credenciais | `POST /agents/{id}/credentials/rotate`, `POST /agents/{id}/credentials/revoke` | Modular |
| Administracao | `POST /agents/{id}/enable|disable|drain|resume|maintenance` | Modular |
| Comandos administrativos | `POST /agents/{id}/diagnostics`, `POST /agents/{id}/capabilities/refresh`, `POST /agents/{id}/update` | Modular |
| Gateway | `WS /agent-gateway/connect`, `GET /agent-gateway/health`, `GET /agent-gateway/readiness` | Modular |
| Compatibilidade | `GET/POST/PUT/DELETE /workers`, `GET /workers/installer-config` | Adapter Worker -> Agent |

## Rotas da Fila (Fase 3)

| Area | Rota | Tela | Permissao |
|---|---|---|---|
| Fila | `GET /fila` | `/fila` (`components/fila/fila-manager.tsx`), relida a cada 5 s ate o tempo real da Fase 4 | `can_view` por automacao; `rodando[].job_id` so para admin |
| Pedido | `POST /fila/execucoes` | ainda sem tela (Fase 6, junto com o pedido pela automacao) | `can_execute` |
| Prioridade | `PATCH /fila/jobs/{id}` | botoes de prioridade na linha do job | `can_execute`, so job `queued` |
| Cancelar | `POST /fila/jobs/{id}/cancelar` | botao com confirmacao do efeito | `can_execute`, so job `queued` |
| Job perdido | `POST /fila/jobs/{id}/decisao` (`continuar` ou `recomecar`) | secao "Jobs perdidos" com confirmacao do efeito | `can_execute` |
| Despacho | `POST /fila/despachar` | sem tela; o Celery roda o mesmo ciclo a cada 5 s | admin |

Os tipos TypeScript ficam em `frontend/src/lib/fila.ts` e seguem
`VerFila.execute` em `backend/modules/dispatch/application/use_cases/queue.py`.

## Rotas do Acompanhar e do acesso por automacao (Fase 4)

| Area | Rota | Tela | Permissao |
|---|---|---|---|
| Acompanhar | `GET /execucoes/{id}/acompanhar` | `/execucoes/[id]` (`components/acompanhar/`) | `ver_execucoes`; tela e passos so com `ver_telas_e_logs` |
| Log ao vivo | `GET /execucoes/{id}/logs?depois=&limite=&esconder_espera=` | painel "Log ao vivo" | `ver_telas_e_logs` |
| Imagem do passo | `GET /execucoes/{id}/imagens/{imagem_id}?tamanho=miniatura\|media\|cheia` | lida por `fetch` com o token e mostrada por `blob:`; nunca URL publica | `ver_telas_e_logs`; ver e auditado |
| Avisos | `GET /execucoes/{id}/avisos`, `GET /fila/avisos` (SSE) | `lib/stream.ts` | token no cabecalho `Authorization` |
| Stream antigo | `GET /executions/{id}/stream` | tela tecnica `/executions/[id]` | token so no cabecalho; logs so com `ver_telas_e_logs` |
| WebSocket | `WS /ws/executions` | `hooks/use-realtime.ts` | token na primeira mensagem `{"type":"auth","token":...}` |
| Acesso | `GET/PUT /automations/{id}/acessos`, `GET /automations/{id}/acessos/minhas` | `/automations/[id]/acessos` | admin ou gestor para mudar |

## Rotas do Painel, Máquinas, Histórico e Itens (Fase 5)

| Area | Rota | Tela | Permissao |
|---|---|---|---|
| Painel | `GET /painel`, `GET /painel/avisos` (SSE) | `/dashboard` (`components/painel/`) | `ver_execucoes` por automação; tela e log com `ver_telas_e_logs`; `central_de_telas` vê todas (Central de telas) |
| Linha do tempo | `GET /painel/linha-do-tempo?horas_antes=&horas_depois=` | `/maquinas` | idem; job de automação alheia aparece só como "ocupada" |
| Histórico | `GET /historico?busca=&automacao=&situacao=&antes=&limite=` | `/historico` | `ver_execucoes` |
| Tempos por item | `GET /automations/{id}/tempos?item=` | `/historico`, aba "Tempos por item" | `can_view` (já existia) |
| Itens | `GET/POST /automations/{id}/itens`, `PUT /automations/{id}/itens/{chave}`, `POST .../{chave}/situacao` | `/automations/[id]/itens` | ver: `executar` ou `editar_itens`; atributos e mudanças: `editar_itens` |
| Importação | `POST /automations/{id}/itens/importar/previa` (arquivo `empresas.db`), `POST /automations/{id}/itens/importar` | modal "Importar" | `editar_itens` |
| Pedido | `POST /automations/{id}/itens/pedir-execucao` | barra de pedido nos itens | `executar` |
| Máquinas e instâncias | `GET/POST /maquinas`, `GET /instancias-diretas`, `POST /automations/{id}/instancias-diretas/codigos`, `POST /instancias-diretas/{id}/{acao}` | `/maquinas` (botão "Gerenciar") | admin ou gestor |

Nenhuma rota aceita credencial na URL. O `EventSource` do navegador nao manda
cabecalho, por isso os streams sao lidos por `fetch` (`lib/stream.ts`).

## Rotas de Notificações e Retenção (Fase 6)

| Area | Rota | Tela | Permissao |
|---|---|---|---|
| Avisos | `GET /notificacoes?limite=`, `POST /notificacoes/lidas` (`{ids?}`; sem `ids` marca todos) | sino no topo (`components/layout/sino-de-avisos.tsx`), relê a cada minuto | a própria pessoa |
| Preferências | `GET` e `PUT /notificacoes/preferencias` (`{tipos, fila_minutos}`) | Configurações > Notificações | a própria pessoa; `maquina_offline` e `fila_parada` só admin ou gestor (422 para os outros) |
| Retenção por automação | `GET /governance/retencao-por-automacao`, `PUT /governance/retencao-por-automacao/{automation_id}` (`{imagens_dias, logs_dias}`, `null` = sem prazo) | `/governance/retention` | `admin.system` |
| Imagem apagada | `GET /execucoes/{id}/imagens/{imagem_id}` responde **410** depois da retenção; a situação da imagem vem `apagada` | Acompanhar e Painel ("Imagem apagada pela retenção em ...") | `ver_telas_e_logs` |

## Rotas da automação no Catálogo (Fase 7)

| Area | Rota | Tela | Permissao |
|---|---|---|---|
| Campos | `GET /automations/{id}/formulario` (`entrada`, `colunas`, `item`, `origem`, `versao`, `tipos`) | `/automations/[id]#campos`, janela Executar, edição de item | `executar` ou `editar_itens` |
| Editar campos | `PUT /automations/{id}/formulario` (`{entrada, colunas, versao}`; 409 se outra pessoa gravou antes; 422 com `campos`) | aba Campos | `editar_itens` |
| Executar | `POST /automations/{id}/itens/pedir-execucao` (`{chaves, com_filiais, parametros}`): `parametros` conferidos pelos campos de entrada (padrão, obrigatório, tipo; chave desconhecida é 422). Automação sem itens aceita `chaves` vazio | botão Executar | `executar` |
| Itens | `POST/PUT /automations/{id}/itens...`: com campos editados no Portal, os atributos passam pelas colunas (o que não é coluna fica guardado) | aba Itens | `editar_itens` |
| Ao vivo | `GET /painel` e `GET /fila`, filtrados por `automation_id` no navegador | aba Visão geral, selo "Rodando" no Catálogo | como no Painel |
| Histórico | `GET /historico?automacao={id}` | abas Visão geral e Histórico | `ver_execucoes` |

Erros de validação vêm como `{"error": {"details": {"campos": {"<chave>": "<motivo>"}}}}`; o
frontend lê com `enviar()` de `lib/campos.ts` e mostra cada motivo embaixo do campo.

## Compatibilidade Fleet no frontend

O frontend atual continua consumindo `/workers`. Esse endpoint agora e uma
camada de compatibilidade sobre `Fleet.Agent` e entrega tambem:

- `connectivity_status`
- `administrative_status`
- `health_status`
- `occupancy_status`
- `desired_version`
- `cpu_percentage`
- `memory_percentage`
- `disk_free_mb`
- `interactive_session`
- `pools`
- `alerts`

O design das telas de workers nao foi redesenhado. O badge principal continua
usando `status`, que agora traduz `Agent.connectivity_status`.

## Garantias

- O redesenho com a identidade Biason foi pedido explicitamente (ADR-020) e
  acontece por tokens em `globals.css`; fora dele, nao redesenhar telas.
- Nao criar mocks para esconder backend ausente.
- Endpoints antigos podem permanecer como adaptadores quando chamarem a nova
  camada de aplicacao e nao duplicarem regra.
- Quando a adaptacao exigir manter modelo antigo como fonte oficial, a tela
  pode ficar temporariamente sem dados, mas o componente visual deve ficar.

## Plano de reconexao

1. Migrar Catalog e manter automacoes/imports operando.
2. Migrar Fleet e mapear Worker UI para Agent UI sem redesenho.
3. Migrar Orchestration/Dispatch e substituir Jobs por Execution/Task/Attempt.
4. Migrar Telemetry e trocar logs textuais por timeline estruturada.
5. Ajustar tipos TypeScript somente depois que o contrato backend estiver
   disponivel.
