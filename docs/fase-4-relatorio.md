# Fase 4: Acompanhar uma execução, imagens, log ao vivo e acesso por automação

Status: entregue e aplicada no portal em 10/11/2026 (revisão `f4a5b6c7d8e9`), aguardando aprovação final. Plano em
[fase-0-diagnostico-orquestracao.md](fase-0-diagnostico-orquestracao.md).

## O que foi feito

| Item | Onde |
|---|---|
| **Tempo real entre processos** por `LISTEN/NOTIFY` do PostgreSQL. O aviso leva só o id; quem recebe relê o banco a partir do último evento (nada se perde numa reconexão). Substitui o publicador em memória, que só funcionava num processo | `backend/modules/telemetry/infrastructure/realtime/postgres.py` |
| **Nenhuma credencial em URL**: o stream antigo, os avisos novos e a fila leem o token só do cabeçalho `Authorization`; o WebSocket autentica na primeira mensagem. No frontend, os streams são lidos por `fetch` (o `EventSource` só aceita token na URL) | `modules/telemetry/api/routes.py`, `api/realtime.py`, `frontend/src/lib/stream.ts`, `hooks/use-realtime.ts` |
| **Imagens dos passos nos dois modos.** Modo direto: `PUT /direto/jobs/{job}/imagens/{id}` (contrato: 201, 413, 415, 422, 401). Modo agente: ao ver o `passo`, o Agent envia `passos/<id>.jpg` na hora, pelo caminho dos artefatos (HTTPS) | `gateway/direct_gateway/routes.py`, `gateway/agent_gateway/message_router.py`, `automation-agent/.../StepImageRegistrar.cs` |
| O Portal confere a imagem de novo (JPEG, não corrompida, não vazia, até 4 MB e 40 milhões de pixels) e guarda três medidas **sem metadados** (miniatura 320 px, média 960 px, cheia até 1920 px) pelo Storage. Recusa fica registrada com o motivo; repetir não duplica | `modules/telemetry/infrastructure/imagens.py`, `application/use_cases/imagens.py`, `modules/storage/application/use_cases/objetos.py` |
| **Imagens só pela API, com permissão**: sem URL pública; o navegador recebe os bytes e mostra por `blob:`. Ampliar é sempre auditado; ver miniaturas, uma vez a cada 10 min por pessoa e execução | `modules/telemetry/api/acompanhar.py`, `frontend/src/components/acompanhar/imagem-do-passo.tsx` |
| **Acompanhar** (`GET /execucoes/{id}/acompanhar`): etapa e item em andamento, progresso, tela atual com "N s nesta tela", passos, atenções, pausa, decorrido, falta, término previsto e as etapas com estimativa, tempo real e a base de cada número | `modules/telemetry/domain/acompanhamento.py` (função pura), `api/acompanhar.py` |
| **Log ao vivo** (`GET /execucoes/{id}/logs`): últimos N ou depois do cursor, esperas ocultáveis, segredos já removidos na gravação | `infrastructure/repositories/sqlalchemy_images.py` |
| **Concessões por automação** (decisão 6): `ver_execucoes`, `ver_telas_e_logs`, `editar_itens`, `executar`, `controlar`, por pessoa ou por time; telas e logs só por concessão explícita (ou admin); toda mudança auditada; permissão global `central_de_telas` criada para a Fase 5 | `modules/access/domain/concessao.py`, `application/concessoes.py`, `api/concessoes.py` |
| Migration aditiva `e3f4a5b6c7d8`: `automation_grants`, `step_images`, permissão `central_de_telas` | `backend/alembic/versions/` |
| Telas novas no visual Biason: **Acompanhar** (`/execucoes/[id]`) e **Acesso a telas e logs** (`/automations/[id]/acessos`). A tela técnica antiga ganhou o botão "Acompanhar ao vivo"; a da automação, "Acesso a telas e logs" | `frontend/src/components/acompanhar/`, `components/acessos/` |
| Fila em tempo real: relê quando a fila muda (avisos), com releitura de segurança a cada 30 s | `components/fila/fila-manager.tsx`, `modules/dispatch/api/fila.py` |
| Contrato e documentação atualizados | `contracts/automation-events/v1/README.md`, `docs/frontend-integration.md`, `docs/design-system.md` |

## Testes (saída real)

Rodada final, depois de tudo o que está em "Depois da primeira entrega":

```
backend   (pytest, suíte inteira)                    454 passed in 94.48s
sdk/python                                            41 passed in 22.08s
Agent     Agent.UnitTests                            Aprovado: 206, Com falha: 0
Agent     Agent.IntegrationTests                     Aprovado: 112, Com falha: 0
Agent     dotnet build AutomationAgent.sln           0 Aviso(s), 0 Erro(s)
frontend  tsc --noEmit                               sem erros
frontend  npx playwright test                        17 passed (Fila 10 + Acompanhar 7)
```

### Cenários desta fase (PostgreSQL, `pytest -s tests/db/test_fase4_acompanhar.py`)

```
imagem do passo (modo direto): 201; medidas {'miniatura': 320, 'media': 960, 'cheia': 1280}; sem EXIF
modo agente: passos/img_agente.jpg subiu como artefato -> imagem do passo pronta (origem agente)
acompanhar: etapa rubricas, item 5066, progresso 18/50, tela img_b há 33 s; sem concessão de telas:
  tela, passos, logs e imagens negados
logs: últimos 2 sem as esperas; segredo mascarado ('senha=*** não pode aparecer'); cursor traz só os 10 novos
concessão ao time Fiscal: imagem 403 -> 200 -> retirada -> 403; auditoria: automacao.concessao.definida,
  automacao.concessao.retirada
LISTEN/NOTIFY: evento gravado pela API -> aviso em 31 ms; aviso de outra execução não chega
token na URL: stream 401, avisos 401, fila/avisos 401, WebSocket fecha 4001; WebSocket com a
  autenticação na 1ª mensagem: conectado
10 execuções simultâneas: 500 eventos gravados (nenhum perdido); primeiro aviso de cada uma:
  mediana 328 ms, p95 360 ms
15 passed in 24.03s
```

O tempo das 10 simultâneas vai do início de cada automação até o primeiro aviso, então
inclui o envio HTTP e a gravação do primeiro lote com as 10 concorrendo (numa rodada
anterior deu mediana 726 ms e p95 859 ms; varia com a carga da máquina).

Também passam: imagem recusada com o código do contrato (corrompida, não JPEG, de uma cor
só → 422 e fica registrada; acima de 4 MB → 413; tipo errado → 415), imagem repetida não
duplica, token de outro job → 401, ver imagem é auditado.

### Testes de tela (Playwright, API simulada só dentro do teste)

```
ok acompanhar ao vivo — desktop/celular, tema claro/escuro (4)
ok sem a concessão de telas e logs, a tela não pede log nem imagem
ok ampliar a tela abre a imagem cheia e voltar ao vivo depois de ver um passo antigo
ok acesso por automação: marcar telas e logs manda a concessão
```

Cada teste também confere que nenhum pedido levou `token=` na URL e que não houve erro
no console.

## Telas

As imagens nos prints são telas sintéticas geradas para o teste (`frontend/e2e/fixtures`).
"Reconectando" e "Conectando" no topo aparecem porque o servidor simulado do teste fecha o
stream logo depois de abrir.

| Tela | Arquivo |
|---|---|
| Acompanhar, desktop, claro | [acompanhar-desktop-claro.png](fase-4-telas/acompanhar-desktop-claro.png) |
| Acompanhar, desktop, escuro | [acompanhar-desktop-escuro.png](fase-4-telas/acompanhar-desktop-escuro.png) |
| Acompanhar, celular, claro e escuro | [claro](fase-4-telas/acompanhar-celular-claro.png), [escuro](fase-4-telas/acompanhar-celular-escuro.png) |
| Acompanhar sem a concessão de telas e logs | [acompanhar-sem-concessao.png](fase-4-telas/acompanhar-sem-concessao.png) |
| Acesso a telas e logs da automação | [acessos-da-automacao.png](fase-4-telas/acessos-da-automacao.png) |

## Mutantes sobreviventes (aceitos por você em 10/11/2026)

```
concessao:      31 mutantes · KILLED: 30 · SURVIVED: 1
acompanhamento: 226 mutantes · KILLED: 188 · None: 33 · SURVIVED: 5
```

A primeira rodada do `acompanhamento` deixou 56 vivos: os testes tinham uma etapa e um item
só. Reforcei com cenário misturado, várias tentativas e textos criados em tempo de execução.
Os 6 que sobram não mudam o comportamento:

| Mutante | Por que não muda nada |
|---|---|
| `*` → `/` na assinatura de `permitido` e de `estado` | todos os chamadores passam os argumentos por nome |
| `e.tipo == "progresso"` → `>=` | nenhum tipo do contrato vem depois de "progresso" em ordem alfabética |
| `e.tipo == "atencao"` → `<=` | nenhum tipo do contrato vem antes de "atencao" |
| `sequencia: int = 0` → `1` e `-1` | é só o padrão; os eventos do banco sempre trazem a sequência |

## Defeitos encontrados durante a fase

- **Horários dos eventos 3 horas adiantados.** `parse_datetime` e `utcnow` da Telemetry
  gravavam horário sem fuso, e o PostgreSQL do portal está em `America/Sao_Paulo`. Corrigido
  na Telemetry (UTC com fuso). O banco real ainda não tinha eventos. Ver riscos: o mesmo
  padrão existe em outros 59 pontos.
- **Logs embaralhados dentro de um lote.** O lote chega com o mesmo `received_at`, e o
  desempate era pelo id aleatório. Agora é pela sequência da automação.
- **Cursor dos logs podia travar** quando as linhas lidas eram todas passos. Agora avança
  pela última linha lida.
- **Imagem dava 404 em execução sem snapshot da versão.** A automação agora é buscada pela
  tarefa.
- Na Fase 3, o reinício do portal mostrou que o `next build` trava se o `server.js` estiver
  de pé (Windows não remove a pasta em uso). Registrado na memória e no relatório da Fase 3.

## Depois da primeira entrega (pedidos de 10/11/2026)

### Horários gravados com fuso (decisão: daqui em diante)

O banco tem 251 colunas de data, todas `timestamptz`, e roda em `America/Sao_Paulo`. 59
pontos do backend gravavam horário sem fuso, que o PostgreSQL lia como horário de Brasília
(3 h adiantado em UTC). Agora todos gravam UTC com fuso, e os auxiliares que "tiravam o
fuso" para comparar passaram a converter para UTC. Os dados antigos ficaram como estavam,
como você decidiu.

### Ligação com a Integração Contábil: preparada, não conectada

Você escolheu "a Integração envia ao Portal" (SDK, HTTPS de saída, sem porta aberta na
.194) e depois pediu para não conectar agora. O que ficou pronto:

| Item | Onde |
|---|---|
| **Modo direto completo, antecipado da Fase 6**: código de inscrição de uso único (30 min, só o hash guardado), inscrição com chave pública ECDSA P-256, aprovação escolhendo a máquina, quarentena, revogação, sessão de 10 min por desafio assinado (60 s, uso único) e próximo job com espera de até 30 s. Tudo auditado; recusa responde só 401 | `modules/fleet/domain/instancia_direta.py`, `modules/fleet/application/use_cases/instancias_diretas.py`, `modules/fleet/infrastructure/assinatura.py`, `gateway/direct_gateway/instancias.py`, `modules/fleet/api/instancias_diretas.py` |
| Entrega do job só enquanto a automação não mandou nenhum evento; pedir de novo troca o token e revoga o anterior; depois do primeiro evento, ninguém recebe o mesmo job | `modules/dispatch/application/use_cases/entrega_direta.py` |
| Cadastro de máquina sem Agent (`POST /maquinas`) | `modules/fleet/api/instancias_diretas.py` |
| Migration aditiva `f4a5b6c7d8e9` | `backend/alembic/versions/` |
| **SDK**: `Instancia.inscrever` (chave gerada na máquina, privada cifrada pelo DPAPI no escopo do usuário), `Instancia.carregar`, `trabalhar` (espera jobs e roda um por vez) | `sdk/python/portal_automacoes/instancia.py` |
| SDK para automações que já existem: `iniciar_item`, `concluir_item`, `iniciar_etapa`, `concluir_etapa`, e emissão de mais de uma thread (o monitor de prints do `dfolha` roda à parte) | `sdk/python/portal_automacoes/automacao.py`, `fila.py` |
| **TLS**: com a `Biason Intranet Root CA` (já confiável nesta máquina), gerei o pedido de certificado do Portal para `MAQ65.intranet.biason.net`, `MAQ65` e `192.168.1.109`. Chave privada em `%LOCALAPPDATA%\PortalAutomacoes\tls\portal-api.key` (acesso só do seu usuário e do SYSTEM), CSR em `portal-api.csr` | fora do repositório |

Teste de ponta a ponta, com o mesmo código que vai rodar na .194 (uvicorn real em HTTPS,
CA de teste, banco de teste):

```
ponta a ponta (HTTPS + CA validada): inscrição -> aprovação em mch_da276bc43c16 -> job tsk_5490ff… ->
  eventos e imagem -> succeeded; tela img_c2f2fb66… pronta; máquina livre
modo direto: código -> inscrição pendente -> sessão -> aprovada em mch_b5076a3c2d90 -> job entregue;
  token trocado na 2ª entrega (o 1º dá 401); depois do 1º evento o job não sai de novo
```

Também passam: código reaproveitado, inexistente ou de outra curva recusado; assinatura de
outra chave recusada; desafio reaproveitado ou vencido recusado; duas inscrições
simultâneas com o mesmo código, só uma passa; quarentena sem jobs; revogada perde a
sessão aberta; só admin ou gestor gera código, aprova e cadastra máquina.

Mutação do domínio da instância direta: `87 mutantes · KILLED: 61 · None: 22 · SURVIVED: 4`.
Os 4 são equivalentes: `len != 16` → `> 16` e `range(0, 15, 4)` (a expressão regular final
já recusa), `*` → `/` na assinatura e `acao <= "aprovar"` (ação desconhecida é recusada
antes).

Para ligar de fato, quando você pedir: assinar a CSR com a CA e me devolver o `.crt`;
decidir se a API inteira vai para HTTPS ou uma porta só para automações; cadastrar a
automação e a máquina .194; gerar o código; instrumentar o `dfolha` (ganchos já mapeados:
`Lote.registrar`, `Cronometro.etapa`, o laço por empresa e `Monitor.capturar`).

### Defeitos encontrados nesta rodada

- **Testes tocavam o banco real.** Rotas que abrem sessão curta (streams, espera do próximo
  job) usavam `SessionLocal` direto e ignoravam a troca de banco dos testes; o
  `LISTEN/NOTIFY` também usava o motor global. Nada foi gravado no banco real (a tabela
  nova não existia lá e as rotas de stream recusavam antes de consultar), mas os testes não
  provavam o que diziam. Agora há `get_session_factory` e `usar_motor`, trocados no
  `conftest`.
- **Fila local do SDK presa a uma thread** (SQLite): emitir de outra thread falhava. Achado
  pelo teste de concorrência e corrigido.
- **Inscrição criava a instância antes de ler o código** (chave estrangeira). Agora o código
  é travado com `FOR UPDATE`, a instância é criada e o código é marcado como usado.
- O reinício pelo `portal.ps1` parou no meio uma vez porque eu o chamei com `2>&1` (o
  PowerShell trata o aviso do alembic como erro). Rodado de novo sem isso.

## Decisões que tomei e que você pode mudar

- **A tela Acompanhar é uma rota nova** (`/execucoes/[id]`). A tela técnica antiga
  (`/executions/[id]`) continua, com um botão para a nova, porque o AGENTS.md proíbe apagar
  tela sem pedido. Quando quiser, a antiga pode sair.
- **Compatibilidade:** `ver_execucoes` e `executar` continuam valendo também pela permissão
  antiga da categoria. **Telas e logs, nunca**: só por concessão explícita ou para admin.
  Consequência: o papel `viewer` tem `automation.read` global, então todo viewer vê o
  **andamento** de qualquer automação (não as telas nem o log).
- Dar acesso pela tela começa com "Ver execuções"; as outras ações se marcam na linha.
  Quem tem "Ver telas e logs" também vê as execuções; quem tem "Controlar" também executa.
- Ver miniaturas é auditado uma vez a cada 10 minutos por pessoa e execução (por processo
  da API); ampliar é auditado sempre.
- A imagem fica no cache do navegador só daquela pessoa (`Cache-Control: private`), por 1 h.

## Aplicada no portal

Com a sua autorização, o portal real foi parado, o frontend reconstruído (com o portal
parado) e as migrations `e3f4a5b6c7d8` e `f4a5b6c7d8e9` aplicadas. Conferido depois:
revisão `f4a5b6c7d8e9 (head)`, tabelas novas presentes, `/api/v1/health` 200, rotas novas
401 sem credencial, `/fila`, `/execucoes/...` e `/automations/.../acessos` 200.

No modo agente, a imagem ao vivo exige a **versão nova do Agent** nas máquinas. Um Agent
antigo continua mandando a pasta `passos/` no fim da execução, e o Portal registra as
imagens nessa hora: funciona, mas não ao vivo.

## O que falta (fases seguintes)

- Fase 5: Painel com a Central de telas (usa `central_de_telas`), Gantt por máquina,
  Histórico e tempos, Máquinas (incluindo as telas de instâncias diretas e do cadastro de
  máquinas, hoje só por API), cadastro de itens com importação da Integração Contábil.
- Fase 6: notificações, **retenção e exclusão automática das imagens**, migração visual
  das telas administrativas. (A inscrição do modo direto saiu da Fase 6: já está pronta.)
- Ligar a Integração Contábil: quando você pedir (ver a seção acima).
- Os comandos de controle (parar após o item etc.) existem no contrato; a tela para usá-los
  ainda não existe (`controlar` já é concedível).

## Riscos e limitações abertos

- **Dados antigos com horário 3 h adiantado**, gravados antes da correção. Ficaram como
  estavam, por decisão sua.
- **TLS ainda não ativo**: aguarda o certificado assinado. Sem ele, o SDK recusa o Portal
  (`http://`), por regra.
- **Instâncias diretas e máquinas só por API**: ainda não há tela para gerar o código,
  aprovar ou cadastrar máquina.
- O `fechar()` do SDK ainda não usa a trava (a alteração foi interrompida). Só importa se
  uma thread emitir enquanto outra fecha a automação.
- O gateway do Agent (anterior a esta fase) também abre sessões com `SessionLocal` direto;
  um teste de banco dele precisaria da mesma troca.
- A `Biason-Intranet-Root-CA.crt` está na raiz do repositório e fora do `.gitignore`. É a
  parte pública (não é segredo), mas convém decidir se ela entra no Git.
- **Imagens acumulam** até a retenção da Fase 6.
- O WebSocket `/ws/executions` autentica direito, mas continua sem nada publicando nele
  (o indicador do topo).
- `next@15.4.6` com a vulnerabilidade CVE-2025-66478 (aviso do `npm ci`).
- O frontend continua em HTTP; a API também, enquanto `PORTAL_TLS_CERT` e
  `PORTAL_TLS_KEY` não estiverem no `backend\.env` (aviso do `portal.ps1 start`).
- O portal **não** está pronto para produção.
