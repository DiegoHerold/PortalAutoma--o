// Tipos alinhados aos DTOs de backend/modules/orchestration/flows/application/dto.py

export type FlowStatus = "draft" | "active" | "disabled" | "archived";

export type Flow = {
  id: string;
  key: string;
  name: string;
  description: string | null;
  category_id: number | null;
  tags: string[];
  status: FlowStatus;
  created_by: string | null;
  created_at: string;
  updated_at: string | null;
};

export type FlowVersionStatus = "draft" | "published" | "deprecated" | "blocked";

export type FlowVersion = {
  id: string;
  flow_id: string;
  version: string;
  status: FlowVersionStatus;
  definition: Record<string, unknown>;
  input_schema: Record<string, unknown> | null;
  output_schema: Record<string, unknown> | null;
  release_notes: string | null;
  created_by: string | null;
  created_at: string;
  published_by: string | null;
  published_at: string | null;
  deprecated_at: string | null;
  blocked_at: string | null;
};

export type FlowNodeType = "automation" | "condition" | "join";

export type FlowFailurePolicy = "fail_flow" | "continue" | "skip_dependents" | "continue_alternative_path";

export type MappingEntry =
  | { source: "flow.input"; path: string }
  | { source: `node.${string}.output`; path: string }
  | { value: unknown };

export type FlowNode = {
  id: string;
  flow_version_id: string;
  key: string;
  name: string;
  node_type: FlowNodeType;
  automation_version_id: number | null;
  configuration: Record<string, unknown>;
  input_mapping: Record<string, MappingEntry>;
  output_mapping: Record<string, MappingEntry>;
  condition: Record<string, unknown> | null;
  retry_policy: Record<string, unknown>;
  timeout_policy: Record<string, unknown>;
  failure_policy: FlowFailurePolicy;
  execution_policy: Record<string, unknown>;
  position_metadata: { x?: number; y?: number; [key: string]: unknown };
  created_at: string;
};

export type FlowEdgeType = "success" | "failure" | "always" | "conditional";

export type FlowEdge = {
  id: string;
  flow_version_id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: FlowEdgeType;
  condition: Record<string, unknown> | null;
  mapping: Record<string, unknown>;
  created_at: string;
};

export type FlowValidationIssue = {
  code: string;
  message: string;
  details: Record<string, unknown>;
};

export type FlowValidationResult = {
  valid: boolean;
  issues: FlowValidationIssue[];
  topological_order: string[];
};

export type FlowExecutionStatus =
  | "created"
  | "pending"
  | "running"
  | "cancelling"
  | "succeeded"
  | "partially_succeeded"
  | "failed"
  | "cancelled"
  | "timed_out";

export type FlowExecution = {
  id: string;
  execution_id: string;
  flow_version_id: string;
  status: FlowExecutionStatus;
  origin: string;
  input: Record<string, unknown>;
  output: Record<string, unknown> | null;
  requested_by: string | null;
  schedule_execution_id: string | null;
  correlation_id: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  cancellation_requested_at: string | null;
  failure_summary: string | null;
};

export type FlowNodeExecutionStatus =
  | "pending"
  | "blocked"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "timed_out"
  | "skipped";

export type FlowNodeExecution = {
  id: string;
  flow_execution_id: string;
  flow_node_id: string;
  status: FlowNodeExecutionStatus;
  input: Record<string, unknown>;
  output: Record<string, unknown> | null;
  condition_result: Record<string, unknown> | null;
  dependency_state: Record<string, unknown>;
  revision: number;
  task_execution_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  skipped_at: string | null;
  failure_summary: string | null;
};

export type FlowExecutionDetails = {
  flow_execution: FlowExecution;
  execution: Record<string, unknown> | null;
  flow_version: FlowVersion | null;
  nodes: FlowNode[];
  edges: FlowEdge[];
  node_executions: FlowNodeExecution[];
};

// Tarefa/tentativa subjacente (backend/modules/orchestration) usada para detalhar
// um FlowNode do tipo automation em execução (Agent, tentativa atual, retries).
export type TaskExecution = {
  id: string;
  execution_id: string;
  automation_version_id: number;
  status: string;
  priority: number;
  parameters: Record<string, unknown>;
  input: Record<string, unknown>;
  result: Record<string, unknown> | null;
  retry_policy: Record<string, unknown>;
  timeout_policy: Record<string, unknown>;
  created_at: string;
  ready_at: string | null;
  queued_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  current_attempt_number: number;
  failure_summary: string | null;
  requirements_snapshot: Record<string, unknown>;
  available_at: string | null;
  scheduling_attempts: number;
  last_scheduling_attempt_at: string | null;
  next_scheduling_attempt_at: string | null;
  last_scheduling_failure: string | null;
};

export type ExecutionAttempt = {
  id: string;
  task_execution_id: string;
  agent_id: string | null;
  status: string;
  offered_at: string | null;
  accepted_at: string | null;
  committed_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  failure_summary: string | null;
  [key: string]: unknown;
};
