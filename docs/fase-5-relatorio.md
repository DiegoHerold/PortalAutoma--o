# Fase 5: Painel, Central de telas, Máquinas, Histórico e cadastro de itens

Status: entregue e aplicada no portal em 10/11/2026 (revisão `a5b6c7d8e9f0`; conferido:
tabela `automation_items` criada, `/dashboard`, `/maquinas`, `/historico`, `/fila` e
`/automations/.../itens` 200, `/api/v1/health` 200, `/painel` e `/historico` 401 sem login). Plano em
[fase-0-diagnostico-orquestracao.md](fase-0-diagnostico-orquestracao.md).

## O que foi feito

### Visual (seus pedidos de 10/11/2026)

| Pedido | O que mudou |
|---|---|
| "Textos muito pequenos", "pequeno para telas grandes" | O portal inteiro cresce com a tela: 17px até 1280px, ~18px em 1440px, ~20px em 1920px, até 22px. Texto, ícones, espaços e menu crescem juntos. Nenhum texto abaixo de 13px; tamanhos fixos em pixel foram trocados (66 + 3) |
| "Poluído, muitos elementos" | Menu com **Monitorar** (Painel, Fila, Máquinas, Histórico) e **Automações**; as 18 telas administrativas ficam em **Administração**, recolhido. Uma ação principal por tela |
| "Filtros demais; poderiam ficar escondidos" | Só a busca à mostra; o resto atrás de "Filtros", com a contagem de filtros ativos |
| "Foco em monitores, progresso, logs, estimativas" | O Painel é feito disso: tela ao vivo, barra de progresso, falta e término grandes, e as últimas linhas do log |
| Ajuste seguinte: "ficou grande demais; em 80% fica ótimo" | Escala em 80% da anterior: ~13,6px em 1280px, ~15,9px em 1920px, até 17,6px |
| "Organize a administração por categoria; tudo de Auditoria a Contas de serviço nas Configurações" | Menu por categoria (Monitorar, Operação, Catálogo, Infraestrutura), por padrão até Agents e sem rolagem em 1366×768. O resto em **Configurações → Administração**, em cartões por categoria |
| "Opção para pôr e tirar itens do menu, escolhida nas Configurações" | **Configurações → Menu lateral**: uma caixa por item e "Restaurar padrão" (fica no navegador) |
| "Tire o BY BIASON; arrume o logo e Portal de Automações" | Rodapé só com Configurações e recolher; logo com "Portal de Automações" numa linha abaixo |
| "Modo claro: azul-escuro e branco ruins de ver" | As faixas de resumo (Painel, Fila, Acompanhar) seguem o tema: brancas com texto azul-marinho no claro |
| "Ícones do menu recolhido podem ser maiores" | De 18px para ~23px, ainda sem rolagem em 1366×650 |
| "Máquinas em 24 h ficou errado; deixe rolar" | Largura fixa por hora: 24 h rola na horizontal, nome da máquina fixo, abre no "agora", "AMANHÃ" só sobre 00:00 |

### Telas

| Tela | Rota | O que mostra |
|---|---|---|
| **Painel** (substitui o Dashboard) | `/dashboard` | Uma faixa curta (rodando, telas livres, na fila e quando termina, perdidos) e um **monitor por execução**: a tela com "N s nesta tela", automação, máquina, etapa e item, barra de progresso, falta, término e há quanto tempo roda, e as 3 últimas linhas do log. Clique leva ao Acompanhar |
| **Central de telas** (admin) | `/dashboard`, aba "Central de telas" | Todas as máquinas como câmeras, em grade de 1, 2, 4, 6 ou 9 (lembrada no navegador), cada uma com o **log ao lado**. Máquina livre mostra o próximo job e quando começa |
| **Máquinas** | `/maquinas` | Linha do tempo (Gantt) de 3, 12 ou 24 h: concluído, rodando (até a previsão, ou tracejado sem previsão) e previsto pela fila, com a marca de "agora". Admin: cadastrar máquina, conectar automação direta (código de uso único) e aprovar, pôr em quarentena ou revogar instâncias |
| **Histórico** | `/historico` | Execuções terminadas com quanto levaram ao lado do previsto no início (âmbar se passou mais de 10%). Aba **Tempos por item**: típico, por tarefa e última vez de cada etapa |
| **Itens da automação** | `/automations/[id]/itens` | Cadastro (matriz com as filiais logo abaixo), edição por formulário gerado do schema do manifesto, **importação do `empresas.db`** da Integração Contábil com prévia, e **pedir execução**: marcar itens, "incluir filiais", parâmetros em "Mais opções" |

### Backend

| Item | Onde |
|---|---|
| `GET /painel`: execuções rodando com o agora de cada uma; tela e log só com `ver_telas_e_logs`; `central_de_telas` vê todas; máquina com job de automação alheia aparece "ocupada", sem dizer com o quê | `modules/telemetry/api/painel.py` |
| Avisos do Painel: uma assinatura curinga no `LISTEN/NOTIFY` acorda com qualquer execução ou com a fila | `modules/telemetry/infrastructure/realtime/postgres.py` |
| Linha do tempo como regra pura (recorte na janela, posição, fim nunca inventado) | `modules/dispatch/domain/linha_do_tempo.py` |
| Histórico com real × previsto (a estimativa congelada no início, da Fase 2), paginação pelo último lido | `modules/telemetry/infrastructure/repositories/sqlalchemy_painel.py` |
| **Cadastro de itens** (seção 6.5 da Fase 0): atributos validados pelo schema do manifesto, grupo de um nível só, prévia de importação, auditoria de cada mudança; e-mails e pastas só para quem tem `editar_itens` | `modules/catalog/domain/itens.py`, `infrastructure/repositories/sqlalchemy_itens.py`, `api/itens.py` |
| Importação do `empresas.db` (aberto só para leitura, numa cópia temporária), com as rubricas ignoradas | idem |
| Pedido de execução pelo cadastro: o job leva o **retrato dos itens** no momento do pedido; mudar o cadastro depois não altera o job na fila | `modules/orchestration/application/use_cases/queue.py` |
| Lista de todas as instâncias diretas para o admin | `modules/fleet/api/instancias_diretas.py` |
| Migration aditiva `a5b6c7d8e9f0` (`automation_items`) | `backend/alembic/versions/` |

## Testes (saída real)

```
backend   (pytest, suíte inteira)                    491 passed in 151.80s
sdk/python                                            41 passed in 24.32s
frontend  tsc --noEmit                               sem erros
frontend  npx playwright test                        27 passed (Fila 10, Acompanhar 7, Fase 5 10)
```

### Cenários desta fase (PostgreSQL, `pytest -s tests/db/test_fase5_painel_itens.py`)

```
importação do empresas.db: prévia 3 novos -> gravados -> nova prévia 3 iguais; ordem ['5066', '5081', '5076']
pedido pelo cadastro: 5081 com filiais -> 1 job (5081, 5076) com o retrato dos itens; mudar o cadastro
  depois não mexe no job
painel: admin vê etapa, progresso 18/50 e as últimas 6 linhas; sem concessão a máquina aparece ocupada
  sem dizer com o quê; com ver_execucoes vê o andamento, sem tela e log
linha do tempo: rodando -> feito depois de concluir; histórico: succeeded, 300 s, previsto None
6 passed
```

Também: quem só executa não vê e-mail nem pasta e não edita; chave repetida 409; grupo de
dois níveis e atributo fora do schema 422; ativar e inativar auditados. O `empresas.db`
**real** da Integração Contábil foi lido aqui (só leitura, nada gravado): 18 empresas,
11 matrizes, 7 filiais, 2 com rubricas ignoradas, nenhum erro na prévia.

### Testes de tela

```
ok painel com monitores — 1920 e celular, claro e escuro (4)
ok texto cresce com a tela, na escala de 80%
ok menu lateral: padrão sem rolagem, administração nas Configurações e itens escolhidos lá
ok central de telas em grade de 4 com o log ao lado
ok sem permissão de telas o monitor mostra só o andamento (nenhum pedido de imagem)
ok máquinas: linha do tempo e automações diretas
ok histórico: filtros escondidos até pedir
ok itens: escolher, pedir execução e importar com prévia
```

## Telas

Dados e telas dos prints são do teste. "Reconectando"/"Conectando" vêm do servidor
simulado, que fecha o stream logo depois de abrir.

| Tela | Arquivo |
|---|---|
| Painel, 1920px, claro e escuro | [claro](fase-5-telas/painel-1920-claro.png), [escuro](fase-5-telas/painel-1920-escuro.png) |
| Painel no celular | [claro](fase-5-telas/painel-celular-claro.png), [escuro](fase-5-telas/painel-celular-escuro.png) |
| Central de telas, grade de 4 | [central-de-telas-1920.png](fase-5-telas/central-de-telas-1920.png) |
| Painel sem permissão de telas | [painel-sem-telas-1440.png](fase-5-telas/painel-sem-telas-1440.png) |
| Máquinas com a linha do tempo | [maquinas-1920.png](fase-5-telas/maquinas-1920.png), [24 h rolando](fase-5-telas/maquinas-24h-1920.png), [menu recolhido](fase-5-telas/menu-recolhido-1366.png) |
| Histórico | [historico-1920.png](fase-5-telas/historico-1920.png) |
| Menu padrão (1366×650) e Configurações | [menu-padrao-1366.png](fase-5-telas/menu-padrao-1366.png), [configuracoes-1366.png](fase-5-telas/configuracoes-1366.png) |
| Itens com a barra de pedido e a prévia da importação | [itens-1920.png](fase-5-telas/itens-1920.png), [itens-importar-previa.png](fase-5-telas/itens-importar-previa.png) |

## Mutantes sobreviventes: preciso que você aceite ou recuse

```
linha_do_tempo: 285 mutantes · KILLED: 228 · None: 55 · SURVIVED: 2
itens:          149 mutantes · KILLED: 126 · None: 22 · SURVIVED: 1
```

A primeira rodada deixou 16 e 14 vivos (bordas exatas da janela, precisão do
arredondamento, erro no meio da importação, item desligado). Reforcei os testes. Os 3 que
sobram não mudam o comportamento:

| Mutante | Por que não muda nada |
|---|---|
| `tipo == "rodando"` → `>=` | "rodando" é o maior dos três tipos em ordem alfabética |
| `atual < inicio_janela` → `!=` | a hora cheia é sempre arredondada para baixo: nunca passa do início |
| `caminho != "atributos"` → `is not` | o texto vem do mesmo literal, então é o mesmo objeto |

## Decisões que tomei e que você pode mudar

- O **Painel substitui o conteúdo do Dashboard**. O componente antigo continua no código,
  fora da tela.
- **Parâmetros do pedido** (como a competência) são campos livres de nome e valor, em
  "Mais opções": o manifesto não declara os parâmetros em linha, então não inventei
  formulário. Se quiser um campo "Competência" fixo para a Integração Contábil, o caminho é
  o manifesto declarar os parâmetros.
- A Central mostra primeiro as máquinas ocupadas; na grade de 6 e 9, cada quadro esconde o
  log para caber; clicar no quadro abre o Acompanhar, com o log completo.
- Ver a lista de itens exige `executar` ou `editar_itens`; e-mails e pastas, só
  `editar_itens`.

## O que falta

- **Ações a partir da atenção** (ex.: "Ignorar rubrica" grava a rubrica no cadastro do
  item): está na seção 6.5 da Fase 0 e ficou para depois desta entrega.
- Fase 6: notificações, retenção e exclusão automática das imagens, e o visual novo nas
  telas administrativas (hoje elas só ganharam a escala de texto e as cores).
- Ligar a Integração Contábil, quando você pedir (certificado, cadastro, `dfolha`).

## Riscos e limitações abertos

- No modo agente, ainda não conferi se o pacote recebe o retrato dos itens (`dados_dos_itens`)
  no `input.json`; no modo direto ele chega na entrega do job.
- O Painel lê, por execução rodando, até 800 eventos e a estimativa: bom para dezenas de
  execuções ao mesmo tempo; para centenas, precisaria de um resumo pronto.
- A aba "Tempos por item" usa a permissão antiga (`can_view`), não a concessão por
  automação.
- O portal **não** está pronto para produção.
