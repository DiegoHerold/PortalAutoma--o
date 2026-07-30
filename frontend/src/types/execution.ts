export type ExecutionLogEntry = {
  id: string | number;
  level: string;
  message: string;
  created_at: string;
};

export type Execution = {
  id: string | number;
  type?: string;
  origin?: string;
  status?: string;
  requested_by?: string | null;
  organization_id?: string | null;
  input?: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  correlation_id?: string | null;
  idempotency_key?: string | null;
  created_at?: string;
  started_at: string | null;
  completed_at?: string | null;
  failure_summary?: string | null;
  legacy_job_id?: number | null;
  telemetry?: {
    event_count?: number;
    log_count?: number;
    metric_count?: number;
    artifact_count?: number;
    latest_event_at?: string | null;
    progress_percentage?: number | null;
  } | null;

  job_id?: number | null;
  worker_id?: number | null;
  execution_status?: string;
  finished_at?: string | null;
  result_summary?: string | null;
  result_payload_json?: Record<string, unknown> | null;
  logs?: ExecutionLogEntry[];

  // Enrichment fields added to GET /executions (Jobs page parity — see
  // backend/modules/orchestration/api/schemas.py ExecutionSummaryResponse).
  automation_id?: number | null;
  automation_name?: string | null;
  priority?: number | null;
  agent_id?: string | null;
  agent_name?: string | null;
  trigger_id?: number | null;

  // Flow linkage is present either on FlowExecution records or inside task input
  // when an automation task was spawned by a Flow node.
  flow_execution_id?: string | null;
  flow_id?: string | null;
  flow_name?: string | null;
  flow_version_id?: string | null;
  flow_node_id?: string | null;
};

export type ExecutionAttempt = {
  id: string;
  task_execution_id: string;
  attempt_number: number;
  agent_id: string;
  agent_instance_id: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  exit_code?: number | null;
  output?: Record<string, unknown> | null;
  result?: Record<string, unknown> | null;
  resource_usage?: Record<string, unknown> | null;
};

export type ExecutionDetails = {
  execution: Execution;
  tasks: Array<{
    id: string;
    execution_id: string;
    automation_version_id?: number;
    status: string;
    priority?: number;
    parameters?: Record<string, unknown>;
    input?: Record<string, unknown>;
    requirements_snapshot?: Record<string, unknown>;
    retry_policy?: Record<string, unknown>;
    timeout_policy?: Record<string, unknown>;
    available_at?: string | null;
    current_attempt_number?: number;
    scheduling_attempts?: number;
    last_scheduling_attempt_at?: string | null;
    next_scheduling_attempt_at?: string | null;
    last_scheduling_failure?: Record<string, unknown> | null;
    started_at?: string | null;
    completed_at?: string | null;
    result?: Record<string, unknown> | null;
    failure_summary?: string | null;
  }>;
  attempts: ExecutionAttempt[];
  current_attempt?: ExecutionAttempt | null;
  current_offer?: Record<string, unknown> | null;
  agent?: Record<string, unknown> | null;
  automation_version?: Record<string, unknown> | null;
  telemetry?: Execution["telemetry"];
};

export type ExecutionProgress = {
  execution_id: string;
  task_execution_id: string | null;
  execution_attempt_id: string | null;
  percentage: number | null;
  current: number | null;
  total: number | null;
  message: string | null;
  updated_at: string | null;
};

// Ver backend/modules/dispatch/application/dto/__init__.py — painéis de suporte/diagnóstico
// avançado de scheduling (Fase 6). Servidos como dict cru via `to_payload` (dataclass -> dict,
// datetime -> isoformat), sem response_model Pydantic.

export type DispatchCandidate = {
  agent_id: string;
  agent_instance_id?: string | null;
  worker_id?: number | null;
  eligible: boolean;
  rejection_reasons?: Array<Record<string, unknown>>;
  score?: number;
  score_components?: Record<string, number>;
  evaluated_at?: string;
  snapshot_revision?: number | null;
};

export type ExecutionDispatchDecision = {
  id: string;
  scheduler_run_id?: string;
  status: string;
  selected_agent_id?: string | null;
  selected_agent_instance_id?: string | null;
  execution_attempt_id?: string | null;
  execution_offer_id?: string | null;
  decision_reason?: string | null;
  weights?: Record<string, number>;
  metadata?: Record<string, unknown>;
  candidates?: DispatchCandidate[];
  created_at?: string;
};

export type ExecutionDispatchInfo = {
  execution_id: string;
  decisions: ExecutionDispatchDecision[];
};

/** GET /execution-attempts/{id}/lease — ver ExecutionLeaseDTO. */
export type ExecutionLeaseInfo = {
  execution_attempt_id: string;
  lease: {
    id: string;
    execution_attempt_id: string;
    agent_id: string;
    agent_instance_id: string;
    status: string;
    issued_at: string;
    expires_at: string;
    last_renewed_at: string | null;
    renewal_sequence: number;
    grace_until: string;
    revoked_at: string | null;
    revocation_reason: string | null;
  } | null;
};

/** GET /execution-attempts/{id}/reservations — reservas de slot de pool (ResourceReservationDTO), plural (0..N). */
export type ExecutionReservation = {
  id: string;
  task_execution_id: string;
  execution_attempt_id: string;
  agent_id: string;
  agent_instance_id: string;
  pool_type: string;
  units: number;
  status: string;
  reserved_at: string;
  expires_at: string;
  execution_offer_id: string | null;
  activated_at: string | null;
  released_at: string | null;
  release_reason: string | null;
};

export type ExecutionReservationsInfo = {
  execution_attempt_id: string;
  reservations: ExecutionReservation[];
};

/** GET /execution-attempts/{id}/locks — locks de recurso exclusivo (ResourceLockDTO), ex. evitar 2 tentativas na mesma automação/máquina. */
export type ExecutionLock = {
  id: string;
  resource_key: string;
  normalized_key: string;
  scope: string;
  agent_id: string;
  execution_attempt_id: string;
  status: string;
  acquired_at: string;
  expires_at: string;
  released_at: string | null;
  release_reason: string | null;
};

export type ExecutionLocksInfo = {
  execution_attempt_id: string;
  locks: ExecutionLock[];
};

export type ExecutionEventsPage = {
  items: Array<{
    id: string;
    execution_id?: string;
    task_execution_id?: string;
    execution_attempt_id?: string;
    agent_id?: string;
    agent_instance_id?: string;
    event_sequence?: number;
    event_type: string;
    level?: string | null;
    message?: string | null;
    payload?: Record<string, unknown>;
    occurred_at: string;
    received_at: string;
  }>;
  next_cursor?: string | null;
};

// Ver backend/modules/telemetry/application/dto/__init__.py ExecutionMetricDTO / ExecutionProcessDTO
export type ExecutionMetric = {
  id: string;
  event_id: string;
  execution_id: string;
  task_execution_id: string;
  execution_attempt_id: string;
  event_sequence: number;
  metric_name: string;
  metric_type: string;
  value: number;
  unit: string | null;
  labels: Record<string, string>;
  occurred_at: string;
  received_at: string;
};

export type ExecutionProcess = {
  process_id: string;
  execution_id: string;
  execution_attempt_id: string;
  name: string | null;
  command: string | null;
  status: string;
  pid: number | null;
  exit_code: number | null;
  started_at: string | null;
  exited_at: string | null;
};

// Ver backend/modules/storage/application/dto/__init__.py ArtifactDTO
export type ExecutionArtifact = {
  id: string;
  execution_id: string;
  task_execution_id: string;
  execution_attempt_id: string;
  name: string;
  content_type: string;
  status: string;
  size_bytes: number | null;
  sha256: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string | null;
  uploaded_at: string | null;
  failed_at: string | null;
  failure_reason: string | null;
};
