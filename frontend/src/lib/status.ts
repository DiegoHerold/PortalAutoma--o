import {
  CircleDashed,
  Clock,
  Loader,
  CheckCircle2,
  XCircle,
  Ban,
  Circle,
  type LucideIcon,
} from "lucide-react";

type Tone = "neutral" | "primary" | "success" | "warning" | "info" | "destructive" | "outline";

export type StatusMeta = { label: string; tone: Tone; icon: LucideIcon; dot: string };

/** Job / execution lifecycle statuses. */
export const JOB_STATUS: Record<string, StatusMeta> = {
  pending: { label: "Pendente", tone: "neutral", icon: CircleDashed, dot: "bg-muted-foreground" },
  queued: { label: "Na fila", tone: "warning", icon: Clock, dot: "bg-warning" },
  running: { label: "Executando", tone: "info", icon: Loader, dot: "bg-info" },
  success: { label: "Sucesso", tone: "success", icon: CheckCircle2, dot: "bg-success" },
  failed: { label: "Falha", tone: "destructive", icon: XCircle, dot: "bg-destructive" },
  cancelled: { label: "Cancelado", tone: "neutral", icon: Ban, dot: "bg-muted-foreground" },
};

export function jobStatusMeta(status?: string | null): StatusMeta {
  return (status && JOB_STATUS[status]) || { label: status || "—", tone: "neutral", icon: Circle, dot: "bg-muted-foreground" };
}

/** Worker statuses. */
export const WORKER_STATUS: Record<string, StatusMeta> = {
  online: { label: "Online", tone: "success", icon: CheckCircle2, dot: "bg-success" },
  busy: { label: "Ocupado", tone: "info", icon: Loader, dot: "bg-info" },
  offline: { label: "Offline", tone: "neutral", icon: Circle, dot: "bg-muted-foreground" },
};

export function workerStatusMeta(status?: string | null): StatusMeta {
  return (status && WORKER_STATUS[status]) || { label: status || "—", tone: "neutral", icon: Circle, dot: "bg-muted-foreground" };
}

/** Queue priorities. */
export const PRIORITY: Record<string, { label: string; tone: Tone; rank: number }> = {
  critical: { label: "Crítica", tone: "destructive", rank: 0 },
  high: { label: "Alta", tone: "warning", rank: 1 },
  normal: { label: "Normal", tone: "info", rank: 2 },
  low: { label: "Baixa", tone: "neutral", rank: 3 },
};

export function priorityMeta(priority?: string | null) {
  return (priority && PRIORITY[priority]) || { label: priority || "—", tone: "neutral" as Tone, rank: 9 };
}

export const EXECUTOR_LABELS: Record<string, string> = {
  playwright: "Playwright",
  power_automate: "Power Automate",
  n8n: "n8n",
  python_script: "Python",
  http_request: "HTTP",
  shell_command: "Shell",
};

export function executorLabel(type?: string | null): string {
  return (type && EXECUTOR_LABELS[type]) || type || "—";
}
