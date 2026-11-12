# Design System — Portal de Automações

Status: vigente para UI atual. Os nomes visuais `Job` e `Worker` continuam
temporariamente por compatibilidade, mas a UX deve migrar para `Execution`,
`TaskExecution`, `Agent` e `AgentInstance` conforme `docs/migration.md`.

Guia da camada visual do frontend. Direção: **identidade Biason** (ADR-020) —
navy da marca, névoa como acento, Arial no texto e nos títulos
e números. Referência de identidade: Biason Comunica. Referência de experiência:
portal da Integração Contábil — **estimativas, imagens ao vivo e logs à vista em
tudo**, nunca escondidos atrás de cliques. Zero dependências de UI externas: a
camada de componentes é própria, com o modelo de _CSS variables_ do shadcn.

## Tokens de cor

Definidos como HSL em `src/app/globals.css`, com `:root` (claro) e `.dark`
(escuro). Consumidos via `tailwind.config.ts` como `hsl(var(--token))`.

| Token | Claro | Escuro | Uso |
|---|---|---|---|
| `background` | fundo `#eef2f6` | noite profunda `#0b1223` | fundo da página |
| `card` | branco | `#111b32` | cartões, tabelas |
| `foreground` | texto `#2e3a52` | `#dbe5f0` | texto corrido |
| `titulo` | noite `#141e37` | branco | `h1`–`h3`, nomes |
| `muted-foreground` | apoio `#5e6b84` | `#93a4bd` | texto de apoio |
| `border` | linha `#dbe3ec` | `#1f2c4d` | bordas |
| `primary` | marinho `#1b3a63` | névoa `#b5ccde` (texto noite) | ação principal, eyebrow |
| `nevoa` | `#b5ccde` | `#b5ccde` | tracinho do eyebrow, faixa do topo |
| `areia` | `#d7bf91` | `#d7bf91` | acento pontual (alerta na faixa escura) |
| `sidebar` | noite `#141e37` | `#090f1b` | menu lateral |
| `sidebar-primary` | névoa | névoa | item ativo do menu |
| `success` | ok `#1d7a4c` | `#3fb77d` | concluído, online, tela livre |
| `warning` | âmbar `#a56609` | `#e0a84a` | **Sem previsão**, job perdido |
| `destructive` | erro `#b42318` | `#f07167` | falha, sem sinal, cancelar |
| `info` | `#2563a6` | `#6fa8dc` | informativo |

Regra: **nunca** usar cores soltas nas telas (`bg-slate-800`, `#111`). Sempre
tokens. A faixa de resumo do topo (`.faixa-noite`) também segue o tema: veja abaixo.

## Tamanho e densidade (atualizado em 11/11/2026)

- **O portal cresce com a tela**: `html { font-size: clamp(15px, 0.42vw + 9px, 18px) }`
  dá 15px até 1280px, ~15px em 1440px e ~17px em 1920px. Tudo no Tailwind é
  `rem`, então texto, ícones, espaços e o menu crescem juntos.
- A escala do Tailwind usa `xs` = 13,1px e `sm` = 14,1px na base de 15px.
  **Nada abaixo de `text-xs`**; tamanhos fixos em `px` são proibidos (use `rem`).
- **Menos é mais**: uma ação principal por tela; só a busca à mostra; o resto dos filtros
  atrás de um botão "Filtros" que abre um painel, com a contagem de filtros ativos.
- Monitorar vem primeiro: tela ao vivo, barra de progresso, falta e término em Arial
  grande, e as últimas linhas do log. Detalhe técnico fica um clique abaixo.
- **Menu lateral por categoria** (`lib/navigation.ts`): Monitorar (Painel, Fila, Máquinas,
  Histórico), Operação (Execuções, Fluxos, Webhooks, Agendamentos), Catálogo (Automações,
  Categorias, Runtimes) e Infraestrutura (Agents). Por padrão o menu vai **até Agents**, sem
  rolagem num notebook de 1366×768 (teste `menu lateral` em `e2e/fase5.spec.ts`).
- **Configurações** (`settings-panel.tsx`) em abas, com a aba no endereço (`#menu`,
  `#notificacoes`, `#conta`, `#sistema`): **Menu e atalhos** lista **todas** as áreas que a pessoa
  pode abrir, por categoria e na ordem do menu, cada uma com uma frase do que faz, o atalho e a
  chave "No menu / Fora do menu" (`areas-do-portal.tsx`, guardado em `portal.menu.itens`).
  Nada fica sem caminho: o que sai do menu continua lá. "Restaurar padrão" volta itens e ordem.
  Por padrão, ficam fora do menu (`padrao: false`): Armazenamento, Segurança, Pessoas e acesso e
  Governança. A página aberta sempre aparece no menu, mesmo desligada.
- **Ordem do menu**: arraste um item para cima ou para baixo dentro da categoria, ou arraste
  o nome da categoria para mudar a ordem das categorias. Pelo teclado: Alt+↑/↓ no item.
  Fica no navegador (`portal.menu.ordem`). No celular (gaveta) não há arrastar.
- Menu **recolhido**: só ícones vetoriais de 1,75rem, com traço e contraste reforçados,
  ainda sem rolagem.
- **Linha do tempo das Máquinas**: cada hora tem largura fixa (5rem). Janela curta ocupa a
  largura toda; a de 24 h passa da tela e **rola na horizontal**, com o nome da máquina
  fixo à esquerda e a tela já posicionada no "agora". O dia só aparece na virada
  ("AMANHÃ" sobre 00:00), nunca grudado em cada hora.

## Tipografia

Pilha de fontes do sistema definida em `src/app/globals.css`, sem download
durante o build ou requisição de fonte no navegador:

- `--font-sans` — **Arial / Helvetica**: corpo e UI, com espaçamento discreto entre letras.
- `--font-display` — **Arial / Helvetica**: títulos (`font-display`,
  `.titulo-condensado`, nome legado da classe) e números grandes (estimativas, contadores).
- `--font-mono` — Cascadia Code/Consolas: IDs e horários em tabela (`.tabular`).

**Escala de texto (12/11/2026, foco em telas grandes).** A raiz cresce com a tela (15px até
1280px, ~17px em 1920px, no máximo 18px) e a escala do Tailwind é compacta: os tamanhos pequenos
sobem e os grandes descem, para nada ficar miúdo nem gigante. Em 1920:

| Classe | px | Uso |
|---|---|---|
| `text-xs` | 15,4 | selos, rótulos em caixa alta, cabeçalho de tabela |
| `text-sm` | 16,5 | texto de apoio, linhas de lista, botão pequeno |
| `text-base` | 17 | corpo, descrição da página, botão grande |
| `text-xl` | 21 | título de janela e de painel lateral |
| `text-2xl` | 24,5 | título de seção |
| `text-3xl` | 27,7 | números do monitor (falta, termina) |
| `text-4xl` | 32 | título da página e números do resumo |

Nenhum tamanho fixo em px nas telas: só a escala. O teste `e2e/telas-grandes.spec.ts` confere,
em 1920, que nenhum texto fica abaixo de 13px nem acima de 40px.

**Espaçamento.** O conteúdo tem margem lateral de 3rem em telas grandes (`lg:px-12` no
`AppShell`), a mesma do topo, para busca, título e cartões começarem na mesma linha; entre
blocos, 2rem (`space-y-8`).

**Agendamentos (12/11/2026)** são uma agenda, no estilo da agenda do Google:
- só o calendário: título com o período, Hoje, ‹ ›, Dia/Semana/Mês e Criar;
- clicar num horário vazio cria o agendamento já com o dia e a hora;
- arrastar uma ocorrência futura muda o dia ou a hora;
- clicar numa ocorrência abre o cartão com Editar, Executar agora e Detalhes;
- a mudança de um agendamento que se repete vale para todas as vezes e pede confirmação
  mostrando o antes e o depois;
- agendamento por intervalo e ocorrência que já rodou não se arrastam.

Navegação e leitura (12/11/2026, segunda rodada):
- clicar e arrastar num espaço vazio seleciona o intervalo ("09:00 – 11:30") e cria a partir do
  início (o agendamento guarda só o horário de início);
- o dia do cabeçalho da Semana abre o Dia; no Dia, os dias vizinhos ficam nas laterais do
  cabeçalho; no Mês, dois cliques num dia abrem o Dia (um clique cria);
- Ctrl + roda do mouse (ou − e + no rodapé) estica ou encolhe as horas, e fica guardado;
- a grade abre das 8 h às 18 h (sem escolha guardada, a altura da hora é a que faz caber esse
  trecho); no dia de hoje, abre 1 h 30 antes do agora.

As regras puras ficam em `lib/agenda.ts` (testadas em `e2e/agenda-regras.spec.ts`); a tela em
`components/schedules/agenda/agenda-calendario.tsx`.

**Voltar.** Toda tela que não é um item do menu (uma automação, uma execução, um job...) mostra
"← Voltar" no topo (`components/layout/botao-voltar.tsx`, no `AppShell`). Ele volta para onde a
pessoa estava. Se ela abriu o link direto, vai para a tela mãe: o item do menu acima dela, ou o
Histórico para uma execução.

## Elementos de marca (`globals.css`)

- `.eyebrow` — caixa alta espaçada, cor `primary`, com tracinho névoa antes.
  Fica acima do título de cada página (`PageTitle eyebrow="Operação"`).
- `.titulo-condensado` — Arial 600. Títulos de página e números; nome legado mantido
  para compatibilidade dos componentes.
- `.faixa-noite` — faixa de resumo do topo das telas operacionais (Painel, Fila,
  Acompanhar), com borda inferior névoa de 3 px. **No tema claro é branca com texto
  azul-marinho**; no escuro, o gradiente noite do Comunica. Dentro dela use as classes
  `.faixa-rotulo`, `.faixa-valor`, `.faixa-apoio` e `.faixa-alerta` e as variáveis
  `--faixa-divisao` e `--tela-fundo`, nunca cor fixa (`text-white`, `#0b1223`): cor fixa
  some no tema claro.
- Menu lateral (12/11/2026): **lista única, sem títulos de categoria**; a pessoa arrasta
  qualquer item para qualquer lugar (Alt+↑/↓ pelo teclado). Recolhido, **só o texto some**: os
  ícones têm o mesmo tamanho e ficam no mesmo lugar, e o logo é a mesma imagem cortada no "B"
  (o B não se mexe; somem "IASON" e "ASSESSORIA EMPRESARIAL").
- Menu lateral: **só o logo** Biason branco (`public/marca/logo-biason-branco.png`), sem
  texto embaixo; borda inferior névoa como o topo do Comunica. O logo leva ao Painel.
  Recolhido, mostra só "B" branco. O botão de recolher/expandir fica no topo, sobre a borda
  direita da área do logo; o rodapé contém Configurações.
- **Sino de avisos** no topo (`sino-de-avisos.tsx`): contagem por ler em vermelho, lista dos
  últimos 20, "Marcar todos como lidos" e atalho para Configurações > Notificações.
- **Filtros** em telas de lista: `FiltrosEscondidos` (`components/shared/filtros-escondidos.tsx`)
  deixa só a busca à mostra e o resto atrás de "Filtros".
- O rótulo acima do título (`PageTitle eyebrow`) é a **categoria do menu** da tela:
  Monitorar, Operação, Catálogo, Infraestrutura, Segurança, Pessoas e acesso, Governança.
- Cartões (`Card`, `SectionCard`, `EmptyState`) com canto `rounded-xl` e título em Arial
  (`titulo-condensado`). Texto de tela sempre com acento.

## Estimativas e motivos (regra de tela)

- Estimativa é sempre aproximada: `~ 23 min`, `~ 1 h 11 min`, `< 1 min`
  (`lib/fila.ts::duracao`). Número em Arial, visível na linha — não em
  tooltip.
- **"Sem previsão" nunca aparece sozinho.** Vem sempre com cada motivo que se
  aplica, em `warning`, logo abaixo da linha (decisão 2 da Fase 0). Os textos vêm
  do backend; a tela só capitaliza a primeira letra.
- Estimativa parcial: "pelo menos ~ 9 min" + as etapas sem histórico.
- Ações que mudam a fila (cancelar, continuar, recomeçar) abrem confirmação que
  diz **o que acontece**, em lista, antes de chamar a API.

## Status de domínio (fonte única)

`src/lib/status.ts` centraliza rótulos, tom (`Badge`) e ícone de cada estado. **Todo** componente que exibe status deve importar daqui — nunca redefinir cores localmente.

- Job/execução: `pending`, `queued`, `running`, `success`, `failed`, `cancelled` → `jobStatusMeta()`
- Worker: `online`, `busy`, `offline` → `workerStatusMeta()`
- Prioridade: `critical` > `high` > `normal` > `low` → `priorityMeta()` (inclui `rank` para ordenar filas)
- Executor: `executorLabel()`

Componentes prontos em `src/components/ui/status-badge.tsx`: `<StatusBadge>`, `<WorkerStatusBadge>`, `<PriorityBadge>`, `<StatusDot>`.

Use `.tabular` em dado numérico/operacional (IDs, horários, contadores): fonte mono + `tabular-nums`.

## Componentes de UI (`src/components/ui/`)

`button`, `card`, `badge`, `input`/`select`/`textarea`/`label`/`field`, `table`, `tabs`, `skeleton`, `separator`, `spinner`, `modal`, `toast`, `status-badge`.

- `Button`: variantes `primary | secondary | outline | ghost | destructive | subtle`, tamanhos `sm | md | lg | icon`, e `asChild` para envolver um `<Link>`.
- `Modal`: dialog acessível (fecha com ESC/backdrop), sem dependência externa.
- `useToast()`: notificações (`success | error | info | warning`).

Utilitário `cn()` (`src/lib/utils.ts`) — junção de classes estilo clsx, sem dependências. Também há helpers de formatação: `formatDateTime`, `formatTime`, `formatDuration`, `formatCountdown`, `relativeFromNow`.

## Estados de tela

Sempre desenhar vazio/erro/carregando com a mesma atenção do estado com dados:

- `LoadingState` / `Skeleton` / `SkeletonText`
- `EmptyState` (ícone + título + descrição + ação)
- `ErrorState` (mensagem + retry)

## Layout e navegação

- `AppShell` (`components/layout/app-shell.tsx`): sidebar fixa + header sticky + área de conteúdo (`max-w-[1400px]`). Provê o `RealtimeStatusProvider`.
- Sidebar (`app-sidebar.tsx`): navegação por categoria (`lib/navigation.ts`), filtrada pela escolha do menu (`lib/menu.ts`); item ativo com barra e ícone névoa; versão mobile em drawer.
- Header (`app-header.tsx`): busca/command palette (⌘K), indicador de tempo real, toggle de tema, menu do usuário.
- Command palette (`command-palette.tsx`): navegação rápida por teclado.
- Tema: `ThemeProvider` (`components/theme/theme-provider.tsx`) com classe `dark`, persistência em `localStorage` e anti-flash inline no `layout.tsx`.

## Dados e tempo real

Auth é client-side (token JWT no `localStorage`), então os dados são buscados no cliente:

- `useApi<T>(path, { pollMs })` — fetch com loading/error/refetch e polling opcional.
- `useRealtime<T>({ wsPath, onMessage, onPoll })` — assina o WebSocket do backend e **cai para polling** automaticamente se o socket falhar/cair, com reconexão exponencial. O estado alimenta o indicador do header via `RealtimeStatusProvider`.

Canal esperado do backend: `/ws/executions` (deriva de `NEXT_PUBLIC_API_URL`). Enquanto não existir, o app usa polling transparentemente.

## Performance

- Componentes de página são finos; listas/tabelas hidratam só a parte interativa.
- `loading.tsx` por grupo de rota para streaming (casca instantânea + skeletons).
- Fontes self-hosted; ícones tree-shaken (`lucide-react`).
- Sem libs pesadas no bundle inicial (gráficos/JSON viewer devem entrar via `dynamic()` quando adicionados).

## Acompanhar e imagens (regra de tela)

- A tela atual é o centro: imagem média com "N s nesta tela" sobreposto em Arial,
  a trilha de passos em miniaturas logo abaixo e o log ao vivo ao lado.
- Passo sem imagem ou com imagem recusada mostra o motivo no lugar da imagem.
- Imagens são buscadas com o token (`components/acompanhar/imagem-do-passo.tsx`) e
  mostradas por `blob:`; nunca há `<img src>` apontando para a API.
- Quem não tem "Ver telas e logs" vê o andamento e as estimativas, e um aviso de que
  telas e logs são restritos; a tela não chega a pedir log nem imagem.
- Indicador de conexão: "Ao vivo" (verde) ou "Reconectando" (âmbar, relendo a cada 30 s).

## Parar, continuar e "por que não anda" (regra de tela, 12/11/2026)

- **Linha da situação no cartão:** cada execução tem no máximo **uma** linha
  (`LinhaDaSituacao`, em `components/painel/controle-da-execucao.tsx`), que só aparece quando
  algo explica por que ela não anda. Rodando normal, não aparece nada. A frase quebra em até
  duas linhas, nunca é cortada. A ordem é:
  1. Não recebeu, ou recebeu e não parou, o cancelamento em 2 min (vermelho cheio; o botão
     Parar vira **Encerrar**, que abre uma janela dizendo o que acontece)
  2. Comunicação não está ativa: tentando até HH:MM, depois cancela (vermelho)
  3. Cancelando (vermelho)
  4. Para ao terminar o item (âmbar)
  5. Pausa (azul)
  6. Esperando: rótulo · há N min (azul)
  7. Sem sinal há N min (âmbar, depois de 10 minutos)
- **Parar:** é um botão pequeno no canto do cartão, e só aparece com "Parar e retomar execuções".
  - Abre uma janela com duas escolhas explicadas. "Parar depois do item atual" é o padrão.
  - No modo agente, a janela só oferece "Cancelar agora".
  - A janela abre no fim da página (portal), por cima de tudo.
- **O cartão continua clicável inteiro:** um link esticado fica por baixo do conteúdo, e o botão fica por cima.
- **Continuar:**
  - aparece nas "Últimas automações" quando a última execução foi cancelada, e no Acompanhar;
  - a janela mostra os itens que rodam de novo e quantos são pulados;
  - depois de confirmar, abre a execução nova;
  - uma execução já continuada mostra "Ver a continuação".

## Histórico e Auditoria (regra de tela, 12/11/2026)

**Histórico** tem duas abas, e a escolhida fica na URL (`?aba=tempos`):

- Execuções:
  - no topo, a faixa com o resumo do período (execuções, concluídas, com falha, tempo médio);
  - à vista ficam só os períodos (Hoje, 7 dias, 30 dias, Tudo);
  - situação, automação e busca ficam atrás de "Filtros (n)";
  - a lista é agrupada por dia ("Hoje", "Ontem", dia da semana);
  - cada linha mostra:
    - início → fim;
    - a duração com a comparação em palavras ("10 min acima do previsto", "dentro do previsto");
    - o motivo da falha em vermelho.
- Quanto tempo leva:
  - à esquerda: 1. a automação, 2. o item, escolhido de uma lista com filtro;
  - à direita: o total típico e uma barra por etapa (grossa: o típico; fina: a última vez, amarela quando passa mais de 10%);
  - "sem histórico" aparece em âmbar.

**Auditoria** é uma linha do tempo:

- Cada evento é uma frase ("Equipe de TI cadastrou a máquina mch_7"), montada em `lib/auditoria.ts`.
- Agrupar por Dia, Pessoa ou Ação. A escolha e os filtros (período, tipo, pessoa, busca) ficam na URL.
- O nome da pessoa é um link para a linha do tempo dela. "ver só esta ação" filtra pelo tipo de ação.
- Clicar num evento abre o painel ao lado, com quatro abas:
  - **O que foi**: quem, ação, recurso e IP. Quando algo foi alterado, mostra o diff. Quando algo foi criado, os campos ("Criado com").
  - **Na mesma ação**: o que veio do mesmo clique.
  - **Da pessoa**: um dia antes e um dia depois.
  - **Do item**: tudo o que já aconteceu com aquele recurso.
- Clicar num evento relacionado abre esse evento no painel.

## Testes de tela

`frontend/e2e/` com Playwright (`npx playwright test`). A API é simulada **só
dentro do teste** (`page.route`), apontando o frontend para um host `.invalid`;
cada teste falha se houver erro no console. O servidor de teste usa
`NEXT_DIST_DIR=.next-e2e` para nunca tocar no `.next` do build de produção. Os
prints ficam em `docs/fase-N-telas/`.

## Convenções

1. Cores só por token. 2. Status só via `lib/status.ts`. 3. Dados numéricos com `.tabular`. 4. Todo estado assíncrono tem loading + empty + error. 5. Nada de `localStorage` além de auth/tema.
