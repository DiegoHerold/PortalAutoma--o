export type RecurrenceType = "daily" | "weekly" | "monthly" | "once";

/** "automation" agenda uma Automation direta; "flow" agenda uma FlowVersion publicada. */
export type TargetType = "automation" | "flow";

/** null/"cron" = recorrência estruturada (recurrence_type); "interval" = a cada N segundos; "once" = data única. */
export type ScheduleType = "cron" | "interval" | "once" | null;

/** Ciclo de vida do próprio agendamento (config), distinto do status de uma ocorrência pontual. */
export type ScheduleStatus = "active" | "paused" | "disabled" | "archived" | "completed";

/**
 * O que o backend faz quando uma execução deveria ter disparado mas o processo de scheduling
 * ficou fora do ar além de `misfire_grace_seconds` (backend/.../application/use_cases.py::_is_misfire).
 * - run_once_now: dispara uma única vez assim que o sistema volta, tratando o atraso como recuperável.
 * - skip: ignora a(s) execução(ões) perdida(s) e aguarda a próxima ocorrência normal.
 */
export type MisfirePolicy = "run_once_now" | "skip";

/**
 * O que fazer se a ocorrência seguinte vence enquanto a execução anterior do mesmo agendamento
 * ainda está rodando (backend/.../application/use_cases.py::_trigger_one).
 * - forbid: pula a nova execução (registra como "skipped") até a anterior terminar.
 * - allow: dispara mesmo assim, permitindo execuções concorrentes do mesmo agendamento.
 */
export type OverlapPolicy = "forbid" | "allow";

export type Schedule = {
  id: number;
  automation_id: number | null;
  automation_version_id: number | null;
  flow_id: string | null;
  flow_version_id: string | null;
  target_type: TargetType;
  key: string | null;
  name: string | null;
  cron_expression: string | null;
  timezone: string;
  is_active: boolean;
  recurrence_type: RecurrenceType;
  time_of_day: string; // "HH:MM"
  weekdays: number[] | null; // 0=Mon .. 6=Sun, set when recurrence_type === "weekly"
  day_of_month: number | null; // 1-31, or 0 = "último dia", set when recurrence_type === "monthly"
  specific_date: string | null; // "YYYY-MM-DD", set when recurrence_type === "once"
  is_one_time: boolean;
  last_dispatched_at: string | null;
  status: ScheduleStatus | string | null;
  schedule_type: ScheduleType | string | null;
  interval_seconds: number | null;
  payload: Record<string, unknown> | null;
  misfire_policy: MisfirePolicy | string | null;
  max_catch_up_runs: number | null;
  misfire_grace_seconds: number | null;
  overlap_policy: OverlapPolicy | string | null;
  next_run_at: string | null;
  last_run_at: string | null;
};

/**
 * `temporal_status` calculado pelo backend (nunca pelo relógio do navegador) — ver
 * backend/modules/orchestration/scheduling/application/calendar.py::classify_temporal_status.
 * Mapeado em `frontend/src/lib/status.ts::TEMPORAL_STATUS`.
 */
export type TemporalStatus =
  | "future_scheduled"
  | "future_paused"
  | "future_overlap_risk"
  | "awaiting_trigger"
  | "delayed"
  | "preparing"
  | "running"
  | "cancelling"
  | "past_succeeded"
  | "past_partial"
  | "past_failed"
  | "past_cancelled"
  | "past_timed_out"
  | "past_dispatch_failed"
  | "past_skipped_overlap"
  | "past_skipped_misfire"
  | "past_unknown";

export type ScheduleCalendarProgress = {
  total: number;
  succeeded: number;
  running: number;
  failed: number;
  pending: number;
};

/**
 * Um item da Central de Agendamentos — combina Schedule (regra) + ScheduleExecution
 * (ocorrência concreta) + Execution/FlowExecution (execução real), quando existirem.
 * Fonte: GET /schedules/calendar (backend/.../scheduling/api/schemas.py::ScheduleCalendarItemResponse).
 */
export type ScheduleCalendarItem = {
  id: string;
  schedule_id: number;
  schedule_execution_id: string | null;
  execution_id: string | null;
  flow_execution_id: string | null;
  target_type: TargetType;
  target_id: string | null;
  target_version: string | null;
  target_name: string;
  schedule_name: string | null;
  planned_start: string;
  actual_start: string | null;
  actual_end: string | null;
  /** actual_end quando concluído; senão planned/actual_start + estimated_duration_seconds (ver is_estimated). */
  effective_end: string | null;
  status: string;
  temporal_status: TemporalStatus | string;
  /** Rótulo curto pronto (ex.: "Ignorada por overlap", "Falha ao disparar"). */
  reason: string | null;
  progress: ScheduleCalendarProgress | null;
  responsible: string | null;
  agent: string | null;
  duration_seconds: number | null;
  estimated_duration_seconds: number | null;
  estimation_confidence: "low" | "medium" | "high" | null;
  is_estimated: boolean;
  recurrence_type: RecurrenceType;
  schedule_type: ScheduleType | string;
  timezone: string;
  is_one_time: boolean;
  overlap_group: number | null;
  overlap_index: number | null;
  overlap_count: number | null;
};

export type ScheduleCalendarSummary = {
  total: number;
  completed: number;
  running: number;
  failed: number;
  future: number;
  cancelled: number;
  skipped: number;
  peak_from: string | null;
  peak_to: string | null;
  peak_count: number;
};

export type ScheduleCalendarDensityBucket = {
  bucket_from: string;
  bucket_to: string;
  count: number;
  level: "none" | "low" | "medium" | "high";
};

export type ScheduleCalendarResponse = {
  range: { date_from: string; date_to: string; timezone: string };
  items: ScheduleCalendarItem[];
  summary: ScheduleCalendarSummary;
  density: ScheduleCalendarDensityBucket[];
};

/** GET /schedules/{id}/history — uma tentativa de disparo (agendada ou manual) de um Schedule. */
export type ScheduleExecution = {
  id: string;
  schedule_id: number;
  scheduled_for: string;
  status: string;
  trigger_type: "scheduled" | "manual" | string;
  execution_id: string | null;
  flow_execution_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  result: Record<string, unknown> | null;
  failure_summary: string | null;
  created_at: string;
};

/** Corpo espelhando ScheduleCreateRequest/ScheduleUpdateRequest (backend/.../api/schemas.py). */
export type ScheduleWritePayload = {
  target_type: TargetType;
  automation_id?: number | null;
  automation_version_id?: number | null;
  flow_id?: string | null;
  flow_version_id?: string | null;
  name?: string | null;
  timezone: string;
  is_active: boolean;
  schedule_type: "interval" | null;
  recurrence_type: RecurrenceType;
  time_of_day: string;
  weekdays: number[] | null;
  day_of_month: number | null;
  specific_date: string | null;
  interval_seconds: number | null;
  misfire_policy: MisfirePolicy;
  max_catch_up_runs: number;
  misfire_grace_seconds: number;
  overlap_policy: OverlapPolicy;
};

/** Corpo de POST /schedules/preview — calcula próximas ocorrências sem persistir nada. */
export type SchedulePreviewPayload = {
  timezone: string;
  schedule_type?: "interval" | "cron" | "once" | null;
  cron_expression?: string | null;
  recurrence_type: RecurrenceType;
  time_of_day: string;
  weekdays?: number[] | null;
  day_of_month?: number | null;
  specific_date?: string | null;
  interval_seconds?: number | null;
  count?: number;
};

export type SchedulePreviewResponse = {
  occurrences: string[];
};
