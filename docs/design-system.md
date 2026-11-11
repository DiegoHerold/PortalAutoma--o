# Design System — Portal de Automações

Status: vigente para UI atual. Os nomes visuais `Job` e `Worker` continuam
temporariamente por compatibilidade, mas a UX deve migrar para `Execution`,
`TaskExecution`, `Agent` e `AgentInstance` conforme `docs/migration.md`.

Guia da camada visual do frontend. Direção: **identidade Biason** (ADR-020) —
navy da marca, névoa como acento, Barlow no texto e Barlow Condensed em títulos
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

## Tamanho e densidade (pedido de 10/11/2026)

- **O portal cresce com a tela**: `html { font-size: clamp(13.6px, 0.36vw + 9px, 17.6px) }`
  dá ~13,6px até 1280px, ~14,2px em 1440px, ~15,9px em 1920px e no máximo 17,6px. É 80%
  da escala anterior (pedido de 10/11/2026: "em 80% fica ótimo"). Tudo no Tailwind é
  `rem`, então texto, ícones, espaços e o menu crescem juntos.
- A escala do Tailwind é maior que a padrão (`xs` = 13px, `sm` = 15px na base de 16px).
  **Nada abaixo de `text-xs`**; tamanhos fixos em `px` são proibidos (use `rem`).
- **Menos é mais**: uma ação principal por tela; só a busca à mostra; o resto dos filtros
  atrás de um botão "Filtros" que abre um painel, com a contagem de filtros ativos.
- Monitorar vem primeiro: tela ao vivo, barra de progresso, falta e término em Barlow
  Condensed grande, e as últimas linhas do log. Detalhe técnico fica um clique abaixo.
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
- Menu **recolhido**: só ícones, maiores (~1,65rem, 23px em 1366px), ainda sem rolagem.
- **Linha do tempo das Máquinas**: cada hora tem largura fixa (5rem). Janela curta ocupa a
  largura toda; a de 24 h passa da tela e **rola na horizontal**, com o nome da máquina
  fixo à esquerda e a tela já posicionada no "agora". O dia só aparece na virada
  ("AMANHÃ" sobre 00:00), nunca grudado em cada hora.

## Tipografia

Via `next/font/google` (baixada no build e servida pelo próprio portal, sem
requisição a terceiros no navegador), em `src/app/layout.tsx`:

- `--font-sans` — **Barlow** (400–700): corpo e UI.
- `--font-display` — **Barlow Condensed** (500–600): títulos (`font-display`,
  `.titulo-condensado`) e números grandes (estimativas, contadores).
- `--font-mono` — Cascadia Code/Consolas: IDs e horários em tabela (`.tabular`).

## Elementos de marca (`globals.css`)

- `.eyebrow` — caixa alta espaçada, cor `primary`, com tracinho névoa antes.
  Fica acima do título de cada página (`PageTitle eyebrow="Operação"`).
- `.titulo-condensado` — Barlow Condensed 600. Títulos de página e números.
- `.faixa-noite` — faixa de resumo do topo das telas operacionais (Painel, Fila,
  Acompanhar), com borda inferior névoa de 3 px. **No tema claro é branca com texto
  azul-marinho**; no escuro, o gradiente noite do Comunica. Dentro dela use as classes
  `.faixa-rotulo`, `.faixa-valor`, `.faixa-apoio` e `.faixa-alerta` e as variáveis
  `--faixa-divisao` e `--tela-fundo`, nunca cor fixa (`text-white`, `#0b1223`): cor fixa
  some no tema claro.
- Menu lateral: **só o logo** Biason branco (`public/marca/logo-biason-branco.png`), sem
  texto embaixo; borda inferior névoa como o topo do Comunica. O logo leva ao Painel.
  Recolhido, mostra só "B". Rodapé: Configurações e o botão de recolher, lado a lado.
- **Sino de avisos** no topo (`sino-de-avisos.tsx`): contagem por ler em vermelho, lista dos
  últimos 20, "Marcar todos como lidos" e atalho para Configurações > Notificações.
- **Filtros** em telas de lista: `FiltrosEscondidos` (`components/shared/filtros-escondidos.tsx`)
  deixa só a busca à mostra e o resto atrás de "Filtros".
- O rótulo acima do título (`PageTitle eyebrow`) é a **categoria do menu** da tela:
  Monitorar, Operação, Catálogo, Infraestrutura, Segurança, Pessoas e acesso, Governança.
- Cartões (`Card`, `SectionCard`, `EmptyState`) com canto `rounded-xl` e título em Barlow
  Condensed (`titulo-condensado`). Texto de tela sempre com acento.

## Estimativas e motivos (regra de tela)

- Estimativa é sempre aproximada: `~ 23 min`, `~ 1 h 11 min`, `< 1 min`
  (`lib/fila.ts::duracao`). Número em Barlow Condensed, visível na linha — não em
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

- A tela atual é o centro: imagem média com "N s nesta tela" sobreposto em Barlow
  Condensed, a trilha de passos em miniaturas logo abaixo e o log ao vivo ao lado.
- Passo sem imagem ou com imagem recusada mostra o motivo no lugar da imagem.
- Imagens são buscadas com o token (`components/acompanhar/imagem-do-passo.tsx`) e
  mostradas por `blob:`; nunca há `<img src>` apontando para a API.
- Quem não tem "Ver telas e logs" vê o andamento e as estimativas, e um aviso de que
  telas e logs são restritos; a tela não chega a pedir log nem imagem.
- Indicador de conexão: "Ao vivo" (verde) ou "Reconectando" (âmbar, relendo a cada 30 s).

## Testes de tela

`frontend/e2e/` com Playwright (`npx playwright test`). A API é simulada **só
dentro do teste** (`page.route`), apontando o frontend para um host `.invalid`;
cada teste falha se houver erro no console. O servidor de teste usa
`NEXT_DIST_DIR=.next-e2e` para nunca tocar no `.next` do build de produção. Os
prints ficam em `docs/fase-N-telas/`.

## Convenções

1. Cores só por token. 2. Status só via `lib/status.ts`. 3. Dados numéricos com `.tabular`. 4. Todo estado assíncrono tem loading + empty + error. 5. Nada de `localStorage` além de auth/tema.
