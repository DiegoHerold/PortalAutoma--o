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
  Mail,
  Users,
  Building2,
  UsersRound,
  ShieldCheck,
  IdCard,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  /** Funcionalidade do papel que libera este item (Papéis globais; backend/modules/access/domain/funcionalidades.py).
   * Sem funcionalidade (Configurações): aparece para qualquer pessoa logada. */
  funcionalidade?: string;
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
      { href: "/dashboard", funcionalidade: "painel", label: "Painel", icon: LayoutDashboard },
      { href: "/fila", funcionalidade: "fila", label: "Fila", icon: ListOrdered },
      { href: "/maquinas", funcionalidade: "maquinas", label: "Máquinas", icon: Monitor },
      { href: "/historico", funcionalidade: "historico", label: "Histórico", icon: History },
    ],
  },
  {
    label: "Operação",
    items: [
      { href: "/executions", funcionalidade: "execucoes", label: "Execuções", icon: ScrollText },
      { href: "/flows", funcionalidade: "fluxos", label: "Fluxos", icon: GitBranch },
      { href: "/webhooks", funcionalidade: "webhooks", label: "Webhooks", icon: Webhook },
      { href: "/schedules", funcionalidade: "agendamentos", label: "Agendamentos", icon: CalendarClock },
    ],
  },
  {
    label: "Catálogo",
    items: [
      { href: "/automations", funcionalidade: "automacoes", label: "Automações", icon: Workflow },
      { href: "/categories", funcionalidade: "categorias", label: "Categorias", icon: Layers },
      { href: "/runtimes", funcionalidade: "runtimes", label: "Runtimes", icon: Package },
    ],
  },
  {
    label: "Infraestrutura",
    items: [
      { href: "/workers", funcionalidade: "agents", label: "Agents", icon: Server },
      { href: "/storage", funcionalidade: "armazenamento", label: "Armazenamento", icon: Database, padrao: false },
    ],
  },
  {
    label: "Segurança",
    items: [
      { href: "/audit", funcionalidade: "auditoria", label: "Auditoria", icon: ScrollText, padrao: false },
      { href: "/secrets", funcionalidade: "segredos", label: "Segredos", icon: KeyRound, padrao: false },
      { href: "/service-accounts", funcionalidade: "contas_de_servico", label: "Contas de serviço", icon: IdCard, padrao: false },
    ],
  },
  {
    label: "Pessoas e acesso",
    items: [
      { href: "/users", funcionalidade: "usuarios", label: "Usuários", icon: Users, padrao: false },
      { href: "/teams", funcionalidade: "times", label: "Times", icon: UsersRound, padrao: false },
      { href: "/roles", funcionalidade: "papeis", label: "Papéis", icon: ShieldCheck, padrao: false },
      { href: "/organizations", funcionalidade: "organizacoes", label: "Organizações", icon: Building2, padrao: false },
    ],
  },
  {
    label: "Governança",
    items: [
      { href: "/governance/limits", funcionalidade: "limites", label: "Limites", icon: Gauge, padrao: false },
      { href: "/governance/retention", funcionalidade: "retencao", label: "Retenção", icon: Archive, padrao: false },
      { href: "/emails", funcionalidade: "emails", label: "E-mails", icon: Mail, padrao: false },
    ],
  },
];

/** Sempre no rodapé do menu, fora das categorias. */
export const CONFIGURACOES: NavItem = { href: "/settings", label: "Configurações", icon: Settings };

export const ALL_NAV_ITEMS: NavItem[] = [...NAV_GROUPS.flatMap((g) => g.items), CONFIGURACOES];
