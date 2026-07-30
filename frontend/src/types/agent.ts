// Tipos alinhados a backend/modules/fleet/{domain/agent.py,application/dto.py}.
// GET/POST/PATCH /agents* devolvem dataclasses serializadas via `_json` (asdict recursivo,
// datetime -> isoformat) — não têm response_model Pydantic, então estes tipos espelham as
// dataclasses Python diretamente, campo a campo.

export type AgentConnectivityStatus = "connecting" | "online" | "stale" | "disconnected" | "offline";
export type AgentAdministrativeStatus = "pending_registration" | "enabled" | "draining" | "maintenance" | "updating" | "disabled";
export type AgentHealthStatus = "healthy" | "degraded" | "error";
export type AgentOccupancyStatus = "idle" | "busy" | "saturated";

/** Resumo de um pool embutido em AgentDTO.pools (backend .../infrastructure/repositories/sqlalchemy_fleet.py::_pool_dict) — sem observed_at/revision, ao contrário de AgentPool (GET /agents/{id}/capacity). */
export type AgentPoolSummary = {
  recommended_total: number | null;
  administrator_total: number | null;
  effective_total: number;
  used: number;
  reserved: number;
  available: number;
};

export type AgentInteractiveSession = {
  available: boolean | null;
  locked: boolean | null;
  user: string | null;
  session_id: string | null;
  session_type: string | null;
  state: string;
  observed_at: string;
};

/** GET /agents, GET /agents/{id} — corpo de AgentDTO. */
export type Agent = {
  id: string;
  name: string;
  hostname: string;
  enabled: boolean;
  connectivity_status: AgentConnectivityStatus;
  administrative_status: AgentAdministrativeStatus;
  health_status: AgentHealthStatus;
  occupancy_status: AgentOccupancyStatus;
  current_version: string | null;
  desired_version: string | null;
  protocol_version: string | null;
  created_at: string | null;
  updated_at: string | null;
  last_seen_at: string | null;
  disabled_at: string | null;
  local_identity: string | null;
  machine_fingerprint: string | null;
  worker_id: number | null;
  cpu_percentage: number | null;
  memory_percentage: number | null;
  disk_free_mb: number | null;
  interactive_session: AgentInteractiveSession | null;
  pools: Record<string, AgentPoolSummary>;
  alerts: string[];
};

/** GET /agents/{id}/instances, entradas de GET /agents/{id}/history.instances. */
export type AgentInstance = {
  id: string;
  agent_id: string;
  process_started_at: string;
  connected_at: string | null;
  last_seen_at: string | null;
  disconnected_at: string | null;
  shutdown_reason: string | null;
  agent_version: string | null;
  negotiated_protocol_version: string | null;
  connection_id: string | null;
  created_at: string | null;
};

/** GET /agents/{id}/capabilities. */
export type AgentCapability = {
  id: string | null;
  agent_id: string | null;
  agent_instance_id: string | null;
  key: string;
  status: "available" | "unavailable" | "degraded" | "unknown";
  version: string | null;
  attributes: Record<string, unknown>;
  expires_at: string | null;
  source: string | null;
  observed_at: string;
  revision: number;
};

/** Item de GET /agents/{id}/capacity.pools — versão completa de AgentPoolSummary, com observed_at/revision. */
export type AgentPool = {
  agent_id: string;
  pool_type: string;
  observed_at: string;
  recommended_total: number | null;
  administrator_total: number | null;
  effective_total: number;
  used: number;
  reserved: number;
  available: number;
  revision: number;
};

export type AgentResourceSnapshot = {
  id: string;
  agent_id: string;
  agent_instance_id: string;
  observed_at: string;
  cpu_usage_percentage: number | null;
  memory_total_mb: number | null;
  memory_available_mb: number | null;
  memory_usage_percentage: number | null;
  disk_free_mb: number | null;
  disk_usage_percentage: number | null;
  process_count: number | null;
  uptime_seconds: number | null;
  revision: number;
  expires_at: string | null;
};

/** GET /agents/{id}/capacity. */
export type AgentCapacity = {
  pools: AgentPool[];
  latest_resource_snapshot: AgentResourceSnapshot | null;
};

export type AgentDiagnosticStatus = "requested" | "collecting" | "completed" | "failed";

/** GET /agents/{id}/history.diagnostics; também retornado (aninhado) por POST /agents/{id}/diagnostics. */
export type AgentDiagnostic = {
  id: string;
  agent_id: string;
  agent_instance_id: string | null;
  request_command_id: string | null;
  status: string;
  requested_at: string;
  summary: string | null;
  details: Record<string, unknown>;
  artifact_id: string | null;
  completed_at: string | null;
  error: string | null;
};

/** GET /agents/{id}/history. */
export type AgentHistory = {
  instances: AgentInstance[];
  diagnostics: AgentDiagnostic[];
};

export type AgentCommand = {
  id: string;
  agent_id: string;
  agent_instance_id: string | null;
  command_sequence: number;
  message_type: string;
  payload: Record<string, unknown>;
  status: string;
  created_at: string;
  available_at: string;
  sent_at: string | null;
  acknowledged_at: string | null;
  expires_at: string | null;
  attempts: number;
  last_error: string | null;
};

/** Resposta de POST /agents/{id}/diagnostics|capabilities/refresh|update — comando assíncrono, ainda não concluído. */
export type AgentCommandAck = {
  status: "pending_delivery";
  command: AgentCommand;
  diagnostic?: AgentDiagnostic;
};

/** backend/.../api/schemas.py::AgentConfigurationPatchRequest — o que dá pra editar via PATCH /agents/{id}. */
export type AgentConfigurationPatch = {
  heartbeat_interval_seconds?: number | null;
  stale_after_seconds?: number | null;
  offline_after_seconds?: number | null;
  administrator_pool_limits?: Record<string, number | null> | null;
  enabled_pools?: string[] | null;
  allowlist_capabilities?: string[] | null;
  maintenance?: boolean | null;
  desired_version?: string | null;
  restrictions?: Record<string, unknown> | null;
};

/** Configuração persistida (AgentConfigurationDTO) — corpo de `configuration` na resposta de PATCH quando enviado desired_version/configuration. */
export type AgentConfiguration = {
  agent_id: string;
  heartbeat_interval_seconds: number;
  stale_after_seconds: number;
  offline_after_seconds: number;
  administrator_pool_limits: Record<string, number | null>;
  enabled_pools: string[];
  allowlist_capabilities: string[];
  maintenance: boolean;
  desired_version: string | null;
  restrictions: Record<string, unknown>;
  updated_at: string | null;
};

export type AgentConfigurationUpdateResult = {
  configuration: AgentConfiguration;
  command: AgentCommand;
};

export type RegistrationTokenStatus = "active" | "used" | "expired" | "revoked";

/**
 * POST /agents/registration-tokens devolve `registration_token` (segredo em texto pleno) —
 * SÓ nesta resposta. GET de listagem não existe no backend; nunca é reexibido depois.
 */
export type RegistrationToken = {
  id: string;
  status: RegistrationTokenStatus;
  expires_at: string;
  created_by: string | null;
  created_at: string;
  used_at: string | null;
  used_by_agent_id: string | null;
  revoked_at: string | null;
  metadata: Record<string, unknown>;
  registration_token?: string;
};

export type CredentialStatus = "active" | "expired" | "rotated" | "revoked";

/** POST /agents/{id}/credentials/rotate — `secret`/`bearer_token` em texto pleno só nesta resposta. */
export type RotateCredentialResult = {
  id: string;
  agent_id: string;
  public_identifier: string;
  secret: string;
  bearer_token: string;
};

/** Resposta de POST /agents/{id}/credentials/revoke (AgentCredentialDTO sem secret). */
export type AgentCredential = {
  id: string;
  agent_id: string;
  credential_type: string;
  public_identifier: string;
  status: CredentialStatus;
  issued_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  rotated_at: string | null;
  revoked_at: string | null;
};
