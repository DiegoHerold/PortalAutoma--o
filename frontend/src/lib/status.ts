import {
  AlarmClockOff,
  CircleDashed,
  Clock,
  Hourglass,
  Loader,
  CheckCircle2,
  XCircle,
  Ban,
  Circle,
  PauseCircle,
  SkipForward,
  type LucideIcon,
} from "lucide-react";

type Tone = "neutral" | "primary" | "success" | "warning" | "info" | "destructive" | "outline";

export type StatusMeta = {
  label: string;
  tone: Tone;
  icon: LucideIcon;
  dot: string;
  /** Usado pela legenda (schedule-status-legend.tsx) — nao obrigatorio para os demais mapas. */
  description?: string;
  /** Ordem de exibicao na legenda/agrupamentos — nao obrigatorio. */
  order?: number;
};

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
  blocked: { label: "Bloqueado", tone: "warning", icon: Clock, dot: "bg-warning" },
  skipped: { label: "Ignorado", tone: "neutral", icon: CircleDashed, dot: "bg-muted-foreground" },
  partially_succeeded: { label: "Parcialmente concluído", tone: "warning", icon: CheckCircle2, dot: "bg-warning" },
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

/** Ciclo de vida do próprio Schedule (config) — ver backend .../application/use_cases.py (Enable/Pause/Disable/Archive). */
export const SCHEDULE_STATUS: Record<string, StatusMeta> = {
  active: { label: "Ativo", tone: "success", icon: CheckCircle2, dot: "bg-success" },
  paused: { label: "Pausado", tone: "warning", icon: Clock, dot: "bg-warning" },
  disabled: { label: "Desabilitado", tone: "neutral", icon: Ban, dot: "bg-muted-foreground" },
  archived: { label: "Arquivado", tone: "neutral", icon: Ban, dot: "bg-muted-foreground" },
  completed: { label: "Concluído", tone: "info", icon: CheckCircle2, dot: "bg-info" },
};

export function scheduleStatusMeta(status?: string | null): StatusMeta {
  return (status && SCHEDULE_STATUS[status]) || { label: status || "—", tone: "neutral", icon: Circle, dot: "bg-muted-foreground" };
}

/**
 * Agent (backend/modules/fleet/domain/agent.py) tem 4 dimensões de status independentes.
 * `connectivity_status` reaproveita WORKER_STATUS/workerStatusMeta (mesmos valores:
 * connecting/online/stale/disconnected/offline). As outras 3 são só do domínio Agent.
 */
export const AGENT_ADMINISTRATIVE_STATUS: Record<string, StatusMeta> = {
  pending_registration: { label: "Aguardando registro", tone: "neutral", icon: CircleDashed, dot: "bg-muted-foreground" },
  enabled: { label: "Habilitado", tone: "success", icon: CheckCircle2, dot: "bg-success" },
  draining: { label: "Drenando", tone: "warning", icon: Clock, dot: "bg-warning" },
  maintenance: { label: "Manutenção", tone: "warning", icon: Clock, dot: "bg-warning" },
  updating: { label: "Atualizando", tone: "info", icon: Loader, dot: "bg-info" },
  disabled: { label: "Desabilitado", tone: "destructive", icon: Ban, dot: "bg-destructive" },
};

export function agentAdministrativeStatusMeta(status?: string | null): StatusMeta {
  return (status && AGENT_ADMINISTRATIVE_STATUS[status]) || { label: status || "—", tone: "neutral", icon: Circle, dot: "bg-muted-foreground" };
}

export const AGENT_HEALTH_STATUS: Record<string, StatusMeta> = {
  healthy: { label: "Saudável", tone: "success", icon: CheckCircle2, dot: "bg-success" },
  degraded: { label: "Degradado", tone: "warning", icon: Clock, dot: "bg-warning" },
  error: { label: "Erro", tone: "destructive", icon: XCircle, dot: "bg-destructive" },
};

export function agentHealthStatusMeta(status?: string | null): StatusMeta {
  return (status && AGENT_HEALTH_STATUS[status]) || { label: status || "—", tone: "neutral", icon: Circle, dot: "bg-muted-foreground" };
}

export const AGENT_OCCUPANCY_STATUS: Record<string, StatusMeta> = {
  idle: { label: "Ocioso", tone: "neutral", icon: Circle, dot: "bg-muted-foreground" },
  busy: { label: "Ocupado", tone: "info", icon: Loader, dot: "bg-info" },
  saturated: { label: "Saturado", tone: "warning", icon: Clock, dot: "bg-warning" },
};

export function agentOccupancyStatusMeta(status?: string | null): StatusMeta {
  return (status && AGENT_OCCUPANCY_STATUS[status]) || { label: status || "—", tone: "neutral", icon: Circle, dot: "bg-muted-foreground" };
}

/** Incoming webhook lifecycle/status labels. */
export const WEBHOOK_STATUS: Record<string, StatusMeta> = {
  active: { label: "Ativo", tone: "success", icon: CheckCircle2, dot: "bg-success" },
  inactive: { label: "Inativo", tone: "neutral", icon: Ban, dot: "bg-muted-foreground" },
  invalid: { label: "Invalido", tone: "destructive", icon: XCircle, dot: "bg-destructive" },
  legacy: { label: "Legado", tone: "warning", icon: Clock, dot: "bg-warning" },
};

export function webhookStatusMeta(status?: string | null): StatusMeta {
  return (status && WEBHOOK_STATUS[status]) || { label: status || "-", tone: "neutral", icon: Circle, dot: "bg-muted-foreground" };
}

/** Execution source/type labels used by /executions filters and detail views. */
export const EXECUTION_ORIGIN_LABELS: Record<string, string> = {
  manual: "Manual",
  trigger: "Trigger",
  webhook: "Webhook",
  schedule: "Agenda",
  scheduled: "Agenda",
  flow: "Fluxo",
  flow_node: "No de Fluxo",
};

export function executionOriginLabel(origin?: string | null): string {
  return (origin && EXECUTION_ORIGIN_LABELS[origin]) || origin || "-";
}

export const EXECUTION_TYPE_LABELS: Record<string, string> = {
  automation: "Automacao",
  flow: "Fluxo",
};

export function executionTypeLabel(type?: string | null): string {
  return (type && EXECUTION_TYPE_LABELS[type]) || type || "Execucao";
}

/** Flow (o "container" do fluxo) status. */
export const FLOW_STATUS: Record<string, StatusMeta> = {
  draft: { label: "Rascunho", tone: "neutral", icon: CircleDashed, dot: "bg-muted-foreground" },
  active: { label: "Ativo", tone: "success", icon: CheckCircle2, dot: "bg-success" },
  disabled: { label: "Desativado", tone: "warning", icon: Ban, dot: "bg-warning" },
  archived: { label: "Arquivado", tone: "neutral", icon: Ban, dot: "bg-muted-foreground" },
};

export function flowStatusMeta(status?: string | null): StatusMeta {
  return (status && FLOW_STATUS[status]) || { label: status || "—", tone: "neutral", icon: Circle, dot: "bg-muted-foreground" };
}

/** FlowVersion lifecycle (draft -> published -> deprecated/blocked). */
export const FLOW_VERSION_STATUS: Record<string, StatusMeta> = {
  draft: { label: "Rascunho", tone: "neutral", icon: CircleDashed, dot: "bg-muted-foreground" },
  published: { label: "Publicada", tone: "success", icon: CheckCircle2, dot: "bg-success" },
  deprecated: { label: "Depreciada", tone: "warning", icon: Clock, dot: "bg-warning" },
  blocked: { label: "Bloqueada", tone: "destructive", icon: Ban, dot: "bg-destructive" },
};

export function flowVersionStatusMeta(status?: string | null): StatusMeta {
  return (
    (status && FLOW_VERSION_STATUS[status]) || { label: status || "—", tone: "neutral", icon: Circle, dot: "bg-muted-foreground" }
  );
}

// Ver backend/modules/telemetry/domain/states.py::ExecutionEventType — apenas os tipos
// realmente emitidos pelos Agents/telemetria (não inventar eventos que o backend não produz).
export const EVENT_TYPE_LABELS: Record<string, string> = {
  "execution.started": "Execução iniciada",
  "execution.completed": "Execução concluída",
  "execution.failed": "Execução falhou",
  "execution.cancelled": "Execução cancelada",
  "execution.timed_out": "Execução expirou (timeout)",
  "task.started": "Automação iniciada",
  "task.progress": "Progresso atualizado",
  "task.completed": "Automação concluída",
  "task.failed": "Automação falhou",
  log: "Log",
  warning: "Aviso",
  error: "Erro",
  metric: "Métrica",
  "process.started": "Processo iniciado",
  "process.exited": "Processo encerrado",
  "artifact.created": "Artefato criado",
  "artifact.available": "Artefato disponível",
  "artifact.failed": "Artefato com falha",
  diagnostic: "Diagnóstico",
};

export function eventTypeLabel(type: string): string {
  return EVENT_TYPE_LABELS[type] ?? type;
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

/**
 * `temporal_status` computado pelo backend em GET /schedules/calendar
 * (backend/modules/orchestration/scheduling/application/calendar.py::classify_temporal_status).
 * Cada item da Central de Agendamentos usa exatamente um destes valores — nao inventar novos
 * aqui sem que o backend os produza. `order` define a ordem em Agora/legenda; menor = mais cedo
 * na timeline passado -> presente -> futuro.
 */
export const TEMPORAL_STATUS: Record<string, StatusMeta> = {
  past_dispatch_failed: {
    label: "Falha ao disparar",
    tone: "destructive",
    icon: XCircle,
    dot: "bg-destructive",
    description: "O agendamento nunca chegou a criar uma execução — o disparo em si falhou.",
    order: 10,
  },
  past_skipped_misfire: {
    label: "Misfire ignorado",
    tone: "neutral",
    icon: SkipForward,
    dot: "bg-muted-foreground",
    description: "Passou da tolerância de atraso (misfire) antes de disparar e foi ignorado, conforme a política do agendamento.",
    order: 11,
  },
  past_skipped_overlap: {
    label: "Ignorada por overlap",
    tone: "neutral",
    icon: SkipForward,
    dot: "bg-muted-foreground",
    description: "A execução anterior deste agendamento ainda estava rodando e a política de sobreposição bloqueou esta ocorrência.",
    order: 12,
  },
  past_cancelled: {
    label: "Cancelado",
    tone: "neutral",
    icon: Ban,
    dot: "bg-muted-foreground",
    description: "A execução foi cancelada antes de concluir.",
    order: 13,
  },
  past_timed_out: {
    label: "Expirou (timeout)",
    tone: "destructive",
    icon: AlarmClockOff,
    dot: "bg-destructive",
    description: "A execução excedeu o tempo máximo permitido.",
    order: 14,
  },
  past_failed: {
    label: "Falhou",
    tone: "destructive",
    icon: XCircle,
    dot: "bg-destructive",
    description: "A execução iniciou mas terminou com falha.",
    order: 15,
  },
  past_partial: {
    label: "Parcialmente concluído",
    tone: "warning",
    icon: CheckCircle2,
    dot: "bg-warning",
    description: "Parte do fluxo concluiu com sucesso, mas ao menos uma etapa falhou.",
    order: 16,
  },
  past_succeeded: {
    label: "Concluído",
    tone: "success",
    icon: CheckCircle2,
    dot: "bg-success",
    description: "Terminou com sucesso.",
    order: 17,
  },
  past_unknown: {
    label: "Resultado desconhecido",
    tone: "neutral",
    icon: Circle,
    dot: "bg-muted-foreground",
    description: "A execução terminou em um estado que o frontend ainda não mapeia — verifique os detalhes.",
    order: 18,
  },
  delayed: {
    label: "Atrasado",
    tone: "warning",
    icon: Clock,
    dot: "bg-warning",
    description: "Passou do horário planejado e ainda não foi disparado nem resolvido.",
    order: 20,
  },
  awaiting_trigger: {
    label: "Aguardando disparo",
    tone: "warning",
    icon: Hourglass,
    dot: "bg-warning",
    description: "O horário planejado chegou; o disparo deve acontecer nos próximos instantes.",
    order: 21,
  },
  preparing: {
    label: "Em preparação",
    tone: "info",
    icon: Loader,
    dot: "bg-info",
    description: "A execução foi criada e está sendo preparada/enfileirada para um Agent.",
    order: 22,
  },
  running: {
    label: "Em andamento",
    tone: "info",
    icon: Loader,
    dot: "bg-info",
    description: "Em execução neste momento.",
    order: 23,
  },
  cancelling: {
    label: "Cancelando",
    tone: "warning",
    icon: Clock,
    dot: "bg-warning",
    description: "O cancelamento foi solicitado e está sendo processado.",
    order: 24,
  },
  future_overlap_risk: {
    label: "Aguardando liberação",
    tone: "outline",
    icon: PauseCircle,
    dot: "bg-muted-foreground",
    description: "Outra execução ativa deste agendamento pode bloquear esta ocorrência quando o horário chegar (política de sobreposição).",
    order: 30,
  },
  future_paused: {
    label: "Agendamento pausado",
    tone: "outline",
    icon: PauseCircle,
    dot: "bg-muted-foreground",
    description: "O agendamento está pausado ou desabilitado; esta ocorrência não vai disparar sozinha.",
    order: 31,
  },
  future_scheduled: {
    label: "Programado",
    tone: "outline",
    icon: CircleDashed,
    dot: "bg-muted-foreground",
    description: "Ocorrência futura calculada a partir da recorrência do agendamento.",
    order: 32,
  },
};

export function temporalStatusMeta(status?: string | null): StatusMeta {
  return (
    (status && TEMPORAL_STATUS[status]) || {
      label: status || "—",
      tone: "neutral",
      icon: Circle,
      dot: "bg-muted-foreground",
      order: 99,
    }
  );
}

/** Agrupamento grosso passado/presente/futuro de um temporal_status, para o resumo operacional. */
export function temporalBucket(status: string): "past" | "present" | "future" {
  if (status.startsWith("future_")) return "future";
  if (status.startsWith("past_")) return "past";
  return "present";
}
