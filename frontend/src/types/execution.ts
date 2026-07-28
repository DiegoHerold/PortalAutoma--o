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
    status: string;
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

export type ExecutionDispatchDecision = {
  id: string;
  status: string;
  selected_agent_id?: string | null;
  selected_agent_instance_id?: string | null;
  execution_attempt_id?: string | null;
  execution_offer_id?: string | null;
  decision_reason?: string | null;
  candidates?: Array<{
    agent_id: string;
    agent_instance_id?: string | null;
    eligible: boolean;
    rejection_reasons?: Array<Record<string, unknown>>;
    score?: number;
    score_components?: Record<string, number>;
  }>;
  created_at?: string;
};

export type ExecutionDispatchInfo = {
  execution_id: string;
  decisions: ExecutionDispatchDecision[];
};

export type ExecutionLeaseInfo = {
  execution_attempt_id: string;
  lease: {
    id: string;
    status: string;
    expires_at: string;
    grace_until: string;
    renewal_sequence: number;
  } | null;
};

export type ExecutionEventsPage = {
  items: Array<{
    id: string;
    event_type: string;
    level?: string | null;
    message?: string | null;
    payload?: Record<string, unknown>;
    occurred_at: string;
    received_at: string;
  }>;
  next_cursor?: string | null;
};
