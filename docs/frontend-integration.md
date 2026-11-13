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
| Auditoria | `/audit` | AuditEvent (`/governance/auditoria/*`) | Governance | Linha do tempo (12/11/2026) | Ver "Rotas da Auditoria" |
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
| Histórico | `GET /historico?busca=&automacao=&situacao=&dias=&antes=&limite=` (`dias`: últimos N dias contando hoje, fuso de São Paulo) | `/historico` | `ver_execucoes` |
| Resumo do período | `GET /historico/resumo?dias=7&automacao=` → `{total, concluidas, com_falha, canceladas, duracao_media_s}` (média só das que deram certo) | `/historico`, faixa do topo | `ver_execucoes` por automação |
| Quanto tempo leva | `GET /automations/{id}/tempos?item=` e a lista `GET /automations/{id}/itens?limite=500` | `/historico?aba=tempos` | `can_view` (já existia) |
| Itens | `GET/POST /automations/{id}/itens`, `PUT /automations/{id}/itens/{chave}`, `POST .../{chave}/situacao` | `/automations/[id]/itens` | ver: `executar` ou `editar_itens`; atributos e mudanças: `editar_itens` |
| Importação | `POST /automations/{id}/itens/importar/previa` (arquivo `empresas.db`), `POST /automations/{id}/itens/importar` | modal "Importar" | `editar_itens` |
| Pedido | `POST /automations/{id}/itens/pedir-execucao` | barra de pedido nos itens | `executar` |
| Máquinas e instâncias | `GET/POST /maquinas`, `GET /instancias-diretas`, `POST /automations/{id}/instancias-diretas/codigos`, `POST /instancias-diretas/{id}/{acao}` | `/maquinas` (botão "Gerenciar") | admin ou gestor |

Nenhuma rota aceita credencial na URL. O `EventSource` do navegador nao manda
cabecalho, por isso os streams sao lidos por `fetch` (`lib/stream.ts`).

## Parar e continuar (12/11/2026)

| Rota | Uso | Permissao |
|---|---|---|
| `POST /fila/execucoes/{id}/parar {modo: apos_item\|agora, motivo?}` | botão Parar (Painel e Acompanhar). Job na fila ou perdido: cancelado na hora. Rodando no modo direto: o comando vai para a automação; `agora` deixa o job em `cancelling`. No modo agente só `agora` (409 para `apos_item`) | concessão `controlar` |
| `POST /fila/execucoes/{id}/encerrar` | botão "Encerrar no Portal": só quando o cancelamento ficou 2 min sem resposta (409 antes); job cancelado com erro, máquina liberada, token revogado | concessão `controlar` |
| `GET /fila/execucoes/{id}/continuar` | prévia: `{pode, motivo, refazer[], pular, sem_itens, continuada_em}` | `ver_execucoes` |
| `POST /fila/execucoes/{id}/continuar` | execução nova só com o que não deu certo; responde `{execution_id, itens, pulados}` | concessão `controlar` |

Campos novos nas leituras:

- `GET /painel`: cada execução tem `situacao` e `pode_controlar`.
  - Os tipos de `situacao` são, nesta ordem: `cancelamento_sem_resposta`, `sem_comunicacao`, `cancelando`, `parando`, `pausa`, `espera`, `sem_sinal`.
  - `sem_comunicacao` (modo direto) aparece com 30 s sem nenhum pedido da instância e traz `cancela_em`.
  - `situacao` é `null` quando roda normal; senão `{tipo: cancelando|parando|pausa|espera|sem_sinal, desde, ...}`.
  - "Sem sinal" aparece depois de 10 minutos sem nenhum evento da automação.
  - O Painel também mostra os jobs em `cancelling`.
- `GET /painel/recentes`: `pode_controlar` e `ultima.continuada_em`.
- `GET /execucoes/{id}/acompanhar`: `situacao`, `execucao.continua_de` e `execucao.continuada_em`.

## Papéis, funcionalidades e Painel (12/11/2026)

O acesso fica separado assim:

| Camada | Responde | Onde se configura |
|---|---|---|
| **Papel** | Quais telas a pessoa usa | Papéis: tabela de funcionalidades com **—**, **Ver** ou **Gerenciar** |
| **Time** | Em quais automações ela trabalha | Times: categorias e ações (ver, executar, parar...) |
| **Usuário** | Quem é | Usuários: um papel e os times |
| **Automação** | Exceções | Automação, aba Acessos |

- **Funcionalidades:** são as 22 do menu, em `backend/modules/access/domain/funcionalidades.py`.
  - Cada nível dá a chave própria da área (`historico.ver`, `usuarios.gerenciar`...) e as permissões técnicas que ela já usava.
  - `GET /auth/me` traz essas chaves em `rbac_permissions`.
  - O menu, a busca (Ctrl+K) e a guarda das telas usam `podeVer` e `podeGerenciar` (`lib/permissions.ts`), com `funcionalidade` em cada item de `lib/navigation.ts`.
  - Sem o Painel, a entrada vai para a primeira tela do papel.
- **API:** as checagens "admin ou gestor" e `admin.system` viraram chaves de funcionalidade:
  - Usuários, Times, Organizações e Contas de serviço;
  - Limites e Retenção;
  - Categorias (gerenciar) e Automações (importar, GitHub, acessos);
  - Máquinas (gerenciar).
- **Rotas de acompanhamento** liberadas pelo papel:
  - `/painel` exige `painel.ver`;
  - `/painel/linha-do-tempo` exige `maquinas.ver` ou `painel.ver`;
  - `/historico` exige `historico.ver` ou `automacoes.ver`;
  - `GET /fila` exige `fila.ver` ou `automacoes.ver`;
  - as ações da Fila exigem `fila.gerenciar`.
- **Papéis de antes** (sem tabela salva): o nível é deduzido das permissões gravadas e do nome do papel. Ninguém ganhou nem perdeu acesso.

| Rota | Uso | Permissão |
|---|---|---|
| `GET /papeis` | `{papeis: [{id, nome, slug, descricao, sistema, pessoas, funcionalidades, editavel, pode_apagar}], pode_editar}` | admin ou `papeis.ver` |
| `GET /papeis/funcionalidades` | o catálogo: `{chave, nome, grupo, href, niveis, o_que_gerenciar}` | admin ou `papeis.ver` |
| `POST /papeis {nome, descricao?, funcionalidades?, baseado_em?}` | sem base, o papel começa só com o Painel | só admin |
| `PUT /papeis/{id} {nome?, descricao?, funcionalidades?}` | `{"historico": "ver", "auditoria": null}`; o Admin não muda | só admin |
| `DELETE /papeis/{id}?substituto=` | os papéis do sistema não são apagados; um papel com pessoas exige o substituto | só admin |

**Times (etapa 2):**
- `PUT /teams/{id}/categorias` aceita `can_view`, `can_execute`, `can_edit` (que vale pelas três de cadastro: criar, editar e apagar), `can_approve` (publicar) e, se precisar separar, `can_create` e `can_delete`. Quem executa, edita ou publica também vê.
- A migration `b2c3d4e5f6a8` passou as permissões por categoria que estavam direto em cada pessoa para times "Acessos de \<nome\>". Pessoas com o mesmo conjunto ficaram no mesmo time. Ninguém ganhou nem perdeu acesso.
- O admin padrão não ganha mais permissões soltas na inicialização.

**Usuários (etapa 3):**
- `GET /acesso/pessoas`: os times de cada pessoa, para a coluna Times.
- `GET /acesso/pessoas/{id}`: o resumo de acesso, com `papel.telas` (funcionalidade e nível), `times` (categorias e concessões de cada time), `excecoes` (concessões direto na pessoa) e `permissoes_soltas`. Exige `usuarios.ver`.
- O formulário de usuário tem só papel e times.
- `PUT /users/{id}/permissions` responde **410**: permissão por categoria não fica mais na pessoa.

**Funcionalidade nova:**
1. Acrescente uma `Funcionalidade` em `FUNCIONALIDADES` (backend).
2. Proteja as rotas com `precisa("<chave>.ver")` ou `precisa("<chave>.gerenciar")` (`modules/access/api/authorization.py`).
3. Ponha `funcionalidade: "<chave>"` no item do menu.

Ela aparece na tabela de Papéis com "—" em todos os papéis menos o Admin.

`GET /painel` traz `aguardando: {fila, perdidos}`: os jobs esperando máquina e os perdidos, só das automações que a pessoa vê.

**Sessão vencida:** o login vale 60 minutos. Um 401 com token dispara `portal:sessao-expirada` (`lib/api.ts`): o AuthProvider sai, a tela de login avisa e, depois de entrar, volta para onde a pessoa estava.

## Rotas da Auditoria (12/11/2026)

| Rota | Uso | Permissao |
|---|---|---|
| `GET /governance/auditoria/eventos?de=&ate=&usuario=&tipo=&acao=&recurso_tipo=&recurso_id=&correlacao=&busca=&tecnicos=&antes=&limite=` | linha do tempo; `cursor` para "Carregar mais" | `audit.read` |
| `GET /governance/auditoria/grupos?por=dia\|usuario\|acao&...` | total de cada grupo (mesmos filtros) | `audit.read` |
| `GET /governance/auditoria/pessoas` | quem aparece no filtro de pessoa | `audit.read` |

Abrir uma tela **não** é registrado (removido em 12/11/2026, a pedido: detalhe demais). Os registros
`tela.aberta` antigos só aparecem com `tecnicos=true`.

O que fica registrado:

- Toda alteração feita por uma pessoa (POST, PUT, PATCH, DELETE na API) vira um evento
  `api.<metodo>` com rota, resposta e duração, pelo middleware
  `modules/governance/api/registro_de_requisicoes.py`. Ficam fora: o login (já tem
  evento próprio) e o que vem de Agent, automação direta e gateway.
- Cada requisição tem um número de correlação (`x-request-id`). Os eventos de negócio
  da mesma requisição recebem o mesmo número, e assim "Na mesma ação" junta tudo o que
  um clique fez.
- O registro técnico `api.*` some da linha do tempo quando a mesma requisição já tem um
  evento de negócio. Ele aparece em "Na mesma ação", em "Do item" e com `tecnicos=true`.
- O login guarda o número da pessoa, e não o e-mail. Os registros antigos, que guardavam o
  e-mail, continuam aparecendo na pessoa certa.

## Rotas de Notificações e Retenção (Fase 6)

| Area | Rota | Tela | Permissao |
|---|---|---|---|
| Avisos | `GET /notificacoes?limite=`, `POST /notificacoes/lidas` (`{ids?}`; sem `ids` marca todos) | sino no topo (`components/layout/sino-de-avisos.tsx`), relê a cada minuto | a própria pessoa |
| Preferências | `GET` e `PUT /notificacoes/preferencias` (`{tipos, fila_minutos}`) | Configurações > Notificações | a própria pessoa; `maquina_offline` e `fila_parada` só admin ou gestor (422 para os outros) |
| Retenção por automação | `GET /governance/retencao-por-automacao`, `PUT /governance/retencao-por-automacao/{automation_id}` (`{imagens_dias, logs_dias, arquivos_dias}`, `null` = sem prazo) | `/governance/retention` | `admin.system` |
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
| Cartões do Catálogo (12/11/2026) | `GET /painel/recentes?limite=200` (última execução de cada cartão; o limite vai de 1 a 200, padrão 3), `GET /fila` ("N na fila") e `GET /painel/executaveis` (quem vê Executar) | `/automations` | como no Painel; Editar/Arquivar/Nova só com `automacoes.gerenciar` |
| Segredos da automação (13/11/2026) | `GET /segredos/da-automacao/{id}`; `POST`/`DELETE /segredos/da-automacao/{id}/{segredo_id}` | aba Técnico, bloco "Segredos que usa" | `segredos.ver`; ligar e desligar com `segredos.gerenciar` |
| Técnico (12/11/2026) | `GET /automations/{id}`, `/automations/{id}/sources`, `/schedules`, `/triggers`, `/instancias-diretas` (filtrados por `automation_id` no navegador; sem `maquinas.gerenciar` a lista de máquinas diz que não pode ver) | aba Técnico | `automacoes.ver` |

Erros de validação vêm como `{"error": {"details": {"campos": {"<chave>": "<motivo>"}}}}`; o
frontend lê com `enviar()` de `lib/campos.ts` e mostra cada motivo embaixo do campo.

## O que a automação declara e os arquivos dela (Fase 8)

| Area | Rota | Tela | Permissao |
|---|---|---|---|
| Entradas | `GET /automations/{id}/formulario`: cada campo traz `origem` (`automacao`/`portal`) e `fora_de_uso`. O `PUT` ignora essas duas marcas vindas do navegador e mantém as gravadas | aba **Entradas** (antes "Campos", mesma âncora `#campos`), Executar (esconde `fora_de_uso`), "Para executar" na Visão geral | como na Fase 7 |
| Tabela da automação | `GET /automations/{id}/itens/proposta` (`null` sem prévia; senão `recebida_em`, `instancia_id`, `total`, `novos`, `alterados`, `iguais`, `erros`, recalculada contra o cadastro atual) | aviso e janela na aba Itens | `editar_itens` |
| Aprovar | `POST /automations/{id}/itens/proposta/aprovar` (`{chaves?}`; sem `chaves`, todas). 422 se o escolhido quebrar um grupo (filial sem a matriz); 404 sem prévia | aba Itens | `editar_itens` |
| Descartar | `DELETE /automations/{id}/itens/proposta` (204) | aba Itens | `editar_itens` |
| Arquivos | `GET /automations/{id}/arquivos?busca=&antes=&limite=` (`{arquivos, cursor}`; sem as imagens dos passos) | aba **Arquivos** | `ver_telas_e_logs` |
| Baixar | `GET /automations/{id}/arquivos/{arquivo_id}/baixar` com o token no cabeçalho (`apiDownload`); 410 se a retenção apagou; auditado | aba Arquivos | `ver_telas_e_logs` |
| Retenção | `PUT /governance/retencao-por-automacao/{id}` aceita `arquivos_dias` | `/governance/retention` | `admin.system` |

## Painel prático (11/11/2026)

| Area | Rota | Tela | Permissao |
|---|---|---|---|
| Executar automação | `GET /painel/executaveis` (`{automacoes: [{id, nome, descricao}]}`, sem as arquivadas) → abre a janela Executar de sempre | Painel: botão "Executar automação" (atalho **E**) | lista só o que a pessoa pode `executar` |
| Últimas automações | `GET /painel/recentes?limite=3&maquina=` (`automacoes`: uma por automação, a execução mais recente, com `pode_executar`, `ultima.{execucao_id, status, quando, maquinas, itens}`; `maquinas` para o filtro) | Painel: "Últimas automações", "Executar" e "Repetir" (mesmos itens marcados); filtro por máquina lembrado no navegador | `ver_execucoes` para aparecer; `executar` para os botões |

## Máquinas e times (11/11/2026)

| Area | Rota | Tela | Permissao |
|---|---|---|---|
| Vínculos da máquina | `GET /maquinas/{id}/vinculos` (`maquina`, `automacoes`, `agents`, `fila`, `rodando`) | Máquinas > Gerenciar > Apagar | admin ou gestor |
| Apagar máquina | `DELETE /maquinas/{id}?confirmar=true`: sem `confirmar` e com vínculos, 409 com `error.details.vinculos`; com execução rodando, 409 sempre; apagada some de `GET /maquinas` | idem | admin ou gestor |
| Time por dentro | `GET /teams/{id}/detalhes` (`membros`, `categorias`, `automacoes`, `acoes_possiveis`) | Times > Membros e permissões | `admin.users` |
| Membros | `POST /teams/{id}/membros` (`{usuarios: [ids]}`), `DELETE /teams/{id}/membros/{user_id}` | idem | `admin.users` |
| Categorias do time | `PUT /teams/{id}/categorias` (`{categorias: [{category_id, can_view, can_execute}]}`, substitui) | idem | `admin.users` |
| Automações do time | `PUT /automations/{id}/acessos` com `team_id` (lista vazia retira) | idem | admin ou gestor |
| Times da pessoa | `GET` e `PUT /users/{id}/times` (`{times: [ids]}`, substitui) | Usuários > criar/editar | `admin.users` |

As permissões por categoria dos times ativos entram no `GET /auth/me` (`permissions`) somadas às
da pessoa.

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

## Segredos e contas de serviço (13/11/2026)

| Area | Rota | Tela | Permissao |
|---|---|---|---|
| Lista de segredos | `GET /segredos` (`chave`, `nome`, `situacao`, `versao`, `expira_em`, `vencido`, `automacoes[{id, nome, ultimo_uso}]`, `ultimo_uso`) | `/secrets` | `segredos.ver` |
| Criar e trocar valor | `POST /secrets` (chave normalizada; 422 se inválida, 409 se repetida), `POST /secrets/{id}/rotate` | `/secrets` | `segredos.gerenciar` |
| Situação, nome | `PUT /segredos/{id}` (`situacao` `active`/`disabled`, `nome`, `descricao`) | `/secrets` | `segredos.gerenciar` |
| Automações que usam | `PUT /segredos/{id}/automacoes` (`{"automacoes": [ids]}`) | `/secrets` | `segredos.gerenciar` |
| Versões | `GET /segredos/{id}/versoes` (sem valor) | `/secrets` | `segredos.ver` |
| Concessão genérica | `POST /secrets/{id}/grants` só aceita `grantee_type=automation`, `permission=use` (422 no resto) | nenhuma | `segredos.gerenciar` |
| Contas | `GET /contas-de-servico` (`papel`, `times`, `credencial_final`, `ultimo_uso`, `situacao`, `vencida`) | `/service-accounts` | `contas_de_servico.ver` |
| Criar | `POST /contas-de-servico` (`nome`, `descricao`, `papel_id`, `times`, `expira_em`) → `{conta, credencial}` uma vez, sem cache | `/service-accounts` | `contas_de_servico.gerenciar` |
| Mudar | `PUT /contas-de-servico/{id}` (mesmos campos + `situacao`) | `/service-accounts` | `contas_de_servico.gerenciar` |
| Nova credencial | `POST /contas-de-servico/{id}/credencial` → `{conta, credencial}` | `/service-accounts` | `contas_de_servico.gerenciar` |
| Apagar | `DELETE /contas-de-servico/{id}` (409 se a conta tem registros ligados) | `/service-accounts` | `contas_de_servico.gerenciar` |

`/service-accounts` (API antiga) responde 410. Papéis para o formulário vêm de `GET /roles`
(sem `admin`); times de `GET /teams` (sem `times.ver`, a tela avisa).
