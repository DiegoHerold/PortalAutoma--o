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
  created: { label: "Criada", tone: "neutral", icon: CircleDashed, dot: "bg-muted-foreground" },
  ready: { label: "Pronta", tone: "warning", icon: Clock, dot: "bg-warning" },
  queued: { label: "Na fila", tone: "warning", icon: Clock, dot: "bg-warning" },
  offered: { label: "Ofertada", tone: "warning", icon: Clock, dot: "bg-warning" },
  accepted: { label: "Aceita", tone: "info", icon: CheckCircle2, dot: "bg-info" },
  committed: { label: "Commit", tone: "info", icon: Loader, dot: "bg-info" },
  preparing: { label: "Preparando", tone: "info", icon: Loader, dot: "bg-info" },
  running: { label: "Executando", tone: "info", icon: Loader, dot: "bg-info" },
  cancelling: { label: "Cancelando", tone: "warning", icon: Clock, dot: "bg-warning" },
  cancel_requested: { label: "Cancelamento solicitado", tone: "warning", icon: Clock, dot: "bg-warning" },
  success: { label: "Sucesso", tone: "success", icon: CheckCircle2, dot: "bg-success" },
  succeeded: { label: "Sucesso", tone: "success", icon: CheckCircle2, dot: "bg-success" },
  failed: { label: "Falha", tone: "destructive", icon: XCircle, dot: "bg-destructive" },
  rejected: { label: "Rejeitada", tone: "warning", icon: Ban, dot: "bg-warning" },
  expired: { label: "Expirada", tone: "warning", icon: Clock, dot: "bg-warning" },
  lost: { label: "Perdida", tone: "destructive", icon: XCircle, dot: "bg-destructive" },
  cancelled: { label: "Cancelado", tone: "neutral", icon: Ban, dot: "bg-muted-foreground" },
  timed_out: { label: "Timeout", tone: "warning", icon: Clock, dot: "bg-warning" },
  active: { label: "Ativo", tone: "success", icon: CheckCircle2, dot: "bg-success" },
  suspect: { label: "Suspeito", tone: "warning", icon: Clock, dot: "bg-warning" },
  revoked: { label: "Revogado", tone: "neutral", icon: Ban, dot: "bg-muted-foreground" },
  completed: { label: "Concluido", tone: "success", icon: CheckCircle2, dot: "bg-success" },
};

export function jobStatusMeta(status?: string | null): StatusMeta {
  return (status && JOB_STATUS[status]) || { label: status || "—", tone: "neutral", icon: Circle, dot: "bg-muted-foreground" };
}

/** Worker statuses. */
export const WORKER_STATUS: Record<string, StatusMeta> = {
  online: { label: "Online", tone: "success", icon: CheckCircle2, dot: "bg-success" },
  busy: { label: "Ocupado", tone: "info", icon: Loader, dot: "bg-info" },
  connecting: { label: "Conectando", tone: "info", icon: Loader, dot: "bg-info" },
  stale: { label: "Atrasado", tone: "warning", icon: Clock, dot: "bg-warning" },
  disconnected: { label: "Desconectado", tone: "warning", icon: CircleDashed, dot: "bg-warning" },
  offline: { label: "Offline", tone: "neutral", icon: Circle, dot: "bg-muted-foreground" },
  disabled: { label: "Desabilitado", tone: "neutral", icon: Ban, dot: "bg-muted-foreground" },
  maintenance: { label: "Manutencao", tone: "warning", icon: Clock, dot: "bg-warning" },
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

/**
 * backend/modules/orchestration stores priority as a plain int score (not a
 * label) — mirrors the same scale the legacy Job dispatcher used
 * (app/services/job_dispatcher_service.py::_priority_to_int) so existing
 * dispatch behavior/sort order is preserved.
 */
export function priorityLabelFromScore(score?: number | null): string {
  if (score == null) return "normal";
  if (score >= 100) return "critical";
  if (score >= 50) return "high";
  if (score >= 0) return "normal";
  return "low";
}

export function priorityScoreFromLabel(label: string): number {
  switch (label) {
    case "critical":
      return 100;
    case "high":
      return 50;
    case "low":
      return -10;
    default:
      return 0;
  }
}

/** Schedule calendar occurrence statuses (upcoming/missed are calendar-only; the rest mirror JOB_STATUS). */
export const OCCURRENCE_STATUS: Record<string, StatusMeta> = {
  upcoming: { label: "Agendado", tone: "outline", icon: Clock, dot: "bg-muted-foreground" },
  missed: { label: "Não executado", tone: "warning", icon: CircleDashed, dot: "bg-warning" },
  queued: { label: "Na fila", tone: "warning", icon: Clock, dot: "bg-warning" },
  running: { label: "Executando", tone: "info", icon: Loader, dot: "bg-info" },
  success: { label: "Sucesso", tone: "success", icon: CheckCircle2, dot: "bg-success" },
  failed: { label: "Falha", tone: "destructive", icon: XCircle, dot: "bg-destructive" },
  cancelled: { label: "Cancelado", tone: "neutral", icon: Ban, dot: "bg-muted-foreground" },
};

export function occurrenceStatusMeta(status?: string | null): StatusMeta {
  return (
    (status && OCCURRENCE_STATUS[status]) || { label: status || "—", tone: "neutral", icon: Circle, dot: "bg-muted-foreground" }
  );
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
