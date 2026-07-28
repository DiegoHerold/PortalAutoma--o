import {
  LayoutDashboard,
  Workflow,
  ListChecks,
  History,
  Server,
  Webhook,
  CalendarClock,
  Users,
  ShieldCheck,
  FolderTree,
  ScrollText,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type NavItem = { href: string; label: string; icon: LucideIcon };
export type NavGroup = { label: string; items: NavItem[] };

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Operação",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/automations", label: "Automações", icon: Workflow },
      { href: "/jobs", label: "Fila de jobs", icon: ListChecks },
      { href: "/executions", label: "Execuções", icon: History },
    ],
  },
  {
    label: "Infraestrutura",
    items: [
      { href: "/workers", label: "Workers", icon: Server },
      { href: "/triggers", label: "Gatilhos", icon: Webhook },
      { href: "/schedules", label: "Agendamentos", icon: CalendarClock },
    ],
  },
  {
    label: "Administração",
    items: [
      { href: "/users", label: "Usuários", icon: Users },
      { href: "/roles", label: "Papéis", icon: ShieldCheck },
      { href: "/categories", label: "Categorias", icon: FolderTree },
      { href: "/audit", label: "Auditoria", icon: ScrollText },
      { href: "/settings", label: "Configurações", icon: Settings },
    ],
  },
];

export const ALL_NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((g) => g.items);
