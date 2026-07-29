import {
  LayoutDashboard,
  Workflow,
  GitBranch,
  ListChecks,
  History,
  CalendarClock,
  Webhook,
  Package,
  Layers,
  Server,
  ListOrdered,
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
};

export type NavGroup = { label: string; items: NavItem[] };

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Visão geral",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/executions", label: "Execuções", icon: History, anyPermission: ["execution.read", "flow.read"] },
    ],
  },
  {
    label: "Operação",
    items: [
      { href: "/flows", label: "Fluxos", icon: GitBranch, permission: "flow.read" },
      { href: "/jobs", label: "Fila de jobs", icon: ListChecks, permission: "execution.read" },
      { href: "/triggers", label: "Gatilhos e webhooks", icon: Webhook, permission: "flow.read" },
      { href: "/schedules", label: "Agendamentos", icon: CalendarClock, permission: "schedule.read" },
    ],
  },
  {
    label: "Catálogo",
    items: [
      { href: "/automations", label: "Automações", icon: Workflow, permission: "automation.read" },
      { href: "/categories", label: "Categorias", icon: Layers },
      { href: "/runtimes", label: "Runtimes", icon: Package, permission: "runtime.read", comingSoon: true },
    ],
  },
  {
    label: "Infraestrutura",
    items: [
      { href: "/workers", label: "Agents", icon: Server, permission: "agent.read" },
      { href: "/dispatch", label: "Fila de execução", icon: ListOrdered, permission: "execution.read", comingSoon: true },
      { href: "/storage", label: "Armazenamento", icon: Database, permission: "artifact.read", comingSoon: true },
    ],
  },
  {
    label: "Governança",
    items: [
      { href: "/audit", label: "Auditoria", icon: ScrollText, permission: "audit.read" },
      { href: "/secrets", label: "Segredos", icon: KeyRound, permission: "secret.read_metadata", comingSoon: true },
      { href: "/governance/limits", label: "Limites", icon: Gauge, adminOnly: true, comingSoon: true },
      { href: "/governance/retention", label: "Retenção", icon: Archive, adminOnly: true, comingSoon: true },
    ],
  },
  {
    label: "Administração",
    items: [
      { href: "/users", label: "Usuários", icon: Users, permission: "admin.users" },
      { href: "/organizations", label: "Organizações", icon: Building2, adminOnly: true, comingSoon: true },
      { href: "/teams", label: "Times", icon: UsersRound, adminOnly: true, comingSoon: true },
      { href: "/roles", label: "Papéis", icon: ShieldCheck, permission: "admin.roles" },
      { href: "/service-accounts", label: "Contas de serviço", icon: IdCard, adminOnly: true, comingSoon: true },
    ],
  },
  {
    label: "Configurações",
    items: [{ href: "/settings", label: "Configurações", icon: Settings }],
  },
];

export const ALL_NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((g) => g.items);
