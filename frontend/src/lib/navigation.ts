import {
  LayoutDashboard,
  Workflow,
  GitBranch,
  History,
  ListOrdered,
  Monitor,
  CalendarClock,
  Webhook,
  Package,
  Layers,
  Server,
  Database,
  ScrollText,
  KeyRound,
  Gauge,
  Archive,
  Users,
  Building2,
  UsersRound,
  ShieldCheck,
  IdCard,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Permissão RBAC necessária (lib/permissions.ts::hasPermission). Omitido = visível para qualquer usuário autenticado. */
  permission?: string;
  /** Item aparece se o usuário tiver qualquer uma destas permissões. */
  anyPermission?: string[];
  /** Item exige papel admin/manager (áreas administrativas sensíveis sem permissão RBAC dedicada ainda). */
  adminOnly?: boolean;
  /** Área ainda não implementada no frontend nesta etapa — leva a uma página "em construção". */
  comingSoon?: boolean;
  /** ``false``: fora do menu até a pessoa ligar nas Configurações. Padrão: no menu. */
  padrao?: boolean;
};

/** Categoria do menu. Itens com ``padrao: false`` ficam fora do menu até a pessoa ligar
 * nas Configurações (e sempre aparecem lá, na área de administração). */
export type NavGroup = { label: string; items: NavItem[] };

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Monitorar",
    items: [
      { href: "/dashboard", label: "Painel", icon: LayoutDashboard },
      { href: "/fila", label: "Fila", icon: ListOrdered, anyPermission: ["execution.read", "automation.read"] },
      { href: "/maquinas", label: "Máquinas", icon: Monitor, anyPermission: ["execution.read", "agent.read"] },
      { href: "/historico", label: "Histórico", icon: History, anyPermission: ["execution.read", "flow.read"] },
    ],
  },
  {
    label: "Operação",
    items: [
      { href: "/executions", label: "Execuções", icon: ScrollText, anyPermission: ["execution.read", "flow.read"] },
      { href: "/flows", label: "Fluxos", icon: GitBranch, permission: "flow.read" },
      { href: "/webhooks", label: "Webhooks", icon: Webhook, permission: "flow.read" },
      { href: "/schedules", label: "Agendamentos", icon: CalendarClock, permission: "schedule.read" },
    ],
  },
  {
    label: "Catálogo",
    items: [
      { href: "/automations", label: "Automações", icon: Workflow, permission: "automation.read" },
      { href: "/categories", label: "Categorias", icon: Layers },
      { href: "/runtimes", label: "Runtimes", icon: Package, permission: "runtime.read" },
    ],
  },
  {
    label: "Infraestrutura",
    items: [
      { href: "/workers", label: "Agents", icon: Server, permission: "agent.read" },
      { href: "/storage", label: "Armazenamento", icon: Database, permission: "artifact.read", padrao: false },
    ],
  },
  {
    label: "Segurança",
    items: [
      { href: "/audit", label: "Auditoria", icon: ScrollText, permission: "audit.read", padrao: false },
      { href: "/secrets", label: "Segredos", icon: KeyRound, permission: "secret.read_metadata", padrao: false },
      { href: "/service-accounts", label: "Contas de serviço", icon: IdCard, adminOnly: true, padrao: false },
    ],
  },
  {
    label: "Pessoas e acesso",
    items: [
      { href: "/users", label: "Usuários", icon: Users, permission: "admin.users", padrao: false },
      { href: "/teams", label: "Times", icon: UsersRound, adminOnly: true, padrao: false },
      { href: "/roles", label: "Papéis", icon: ShieldCheck, permission: "admin.roles", padrao: false },
      { href: "/organizations", label: "Organizações", icon: Building2, adminOnly: true, padrao: false },
    ],
  },
  {
    label: "Governança",
    items: [
      { href: "/governance/limits", label: "Limites", icon: Gauge, adminOnly: true, padrao: false },
      { href: "/governance/retention", label: "Retenção", icon: Archive, adminOnly: true, padrao: false },
    ],
  },
];

/** Sempre no rodapé do menu, fora das categorias. */
export const CONFIGURACOES: NavItem = { href: "/settings", label: "Configurações", icon: Settings };

export const ALL_NAV_ITEMS: NavItem[] = [...NAV_GROUPS.flatMap((g) => g.items), CONFIGURACOES];
