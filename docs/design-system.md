# Design System — Portal de Automações

Guia da camada visual do frontend. Direção: **console de operações** — sóbrio, denso na medida certa, com identidade própria (grafite + marigold) que foge do visual genérico de SaaS/IA. Zero dependências de UI externas (sem Radix/shadcn instalados): a camada de componentes é própria, mas usa o mesmo modelo de _CSS variables_ do shadcn, o que torna trivial migrar depois.

## Tokens de cor

Definidos como HSL em `src/app/globals.css`, com variantes `:root` (claro) e `.dark` (escuro). Consumidos via `tailwind.config.ts` como `hsl(var(--token))`.

Semânticos base: `background`, `foreground`, `card`, `popover`, `muted`, `accent`, `secondary`, `border`, `input`, `ring`, `primary`.

Status (com par `-foreground`): `success`, `warning`, `info`, `destructive`.

Sidebar (grafite): `sidebar`, `sidebar-foreground`, `sidebar-border`, `sidebar-accent`.

Regra: **nunca** usar cores soltas (`bg-slate-800`, `#111`). Sempre tokens (`bg-card`, `text-muted-foreground`, `border-border`). Isso garante tema claro/escuro consistente.

### Cor de marca

`--primary` é um **marigold** (`26 90% 48%` claro / `28 92% 55%` escuro). É a única cor de destaque forte — usar com parcimônia (ações primárias, item de menu ativo, indicadores). Evitar múltiplos neons.

## Status de domínio (fonte única)

`src/lib/status.ts` centraliza rótulos, tom (`Badge`) e ícone de cada estado. **Todo** componente que exibe status deve importar daqui — nunca redefinir cores localmente.

- Job/execução: `pending`, `queued`, `running`, `success`, `failed`, `cancelled` → `jobStatusMeta()`
- Worker: `online`, `busy`, `offline` → `workerStatusMeta()`
- Prioridade: `critical` > `high` > `normal` > `low` → `priorityMeta()` (inclui `rank` para ordenar filas)
- Executor: `executorLabel()`

Componentes prontos em `src/components/ui/status-badge.tsx`: `<StatusBadge>`, `<WorkerStatusBadge>`, `<PriorityBadge>`, `<StatusDot>`.

## Tipografia

Via `next/font` (self-hosted, sem layout shift), três famílias em `src/app/layout.tsx`:

- `--font-sans` (Inter) — corpo e UI
- `--font-display` (Space Grotesk) — títulos (`font-display`), dá personalidade
- `--font-mono` (JetBrains Mono) — números, IDs, timestamps, JSON

Use a classe utilitária `.tabular` (definida em `globals.css`) em qualquer dado numérico/operacional (IDs, horários, contadores) — aplica fonte mono + `tabular-nums` para alinhamento em tabelas.

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
- Sidebar (`app-sidebar.tsx`): navegação agrupada (`lib/navigation.ts`) por **Operação / Infraestrutura / Administração**, item ativo destacado; versão mobile em drawer.
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

## Convenções

1. Cores só por token. 2. Status só via `lib/status.ts`. 3. Dados numéricos com `.tabular`. 4. Todo estado assíncrono tem loading + empty + error. 5. Nada de `localStorage` além de auth/tema.
