export type JsonRecord = Record<string, unknown>;

export type SecretResponse = {
  id: string;
  organization_id: number | null;
  key: string;
  name: string;
  description: string | null;
  status: string;
  current_version_id: string | null;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type SecretVersionResponse = {
  id: string;
  secret_id: string;
  version: number;
  encryption_key_id: string;
  created_by: string | null;
  created_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
};

export type SecretWithVersionResponse = { secret: SecretResponse; version: SecretVersionResponse };

export type SecretCreateRequest = {
  key: string;
  name: string;
  value: string;
  description?: string;
  organization_id?: number;
  expires_at?: string;
};

export type SecretRotateRequest = { value: string; expires_at?: string };

export type SecretGrantResponse = {
  id: string;
  secret_id: string;
  grantee_type: string;
  grantee_id: string;
  permission: string;
  created_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
};

export type SecretGrantCreateRequest = {
  grantee_type: string;
  grantee_id: string;
  permission: string;
  expires_at?: string;
};

export type SystemLimitResponse = {
  key: string;
  value: number;
  unit: string;
  description: string | null;
  organization_id: number | null;
  metadata: JsonRecord;
  updated_at: string | null;
};

export type SystemLimitUpsertRequest = {
  value: number;
  unit: string;
  description?: string;
  organization_id?: number;
  metadata: JsonRecord;
};

export type RetentionPolicyResponse = {
  resource_type: string;
  retention_days: number;
  archive_after_days: number | null;
  delete_after_days: number | null;
  legal_hold: boolean;
  enabled: boolean;
  organization_id: number | null;
  updated_at: string | null;
};

export type RetentionPolicyUpsertRequest = {
  retention_days: number;
  archive_after_days?: number;
  delete_after_days?: number;
  legal_hold: boolean;
  enabled: boolean;
  organization_id?: number;
};

export type AuditEntryResponse = {
  id: string;
  actor: string | null;
  actor_type: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  created_at: string | null;
  before: JsonRecord | null;
  after: JsonRecord | null;
  message: string | null;
};

export type AuditEventResponse = {
  id: string;
  organization_id: number | null;
  actor_type: string;
  actor_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string;
  before: JsonRecord | null;
  after: JsonRecord | null;
  metadata: JsonRecord;
  correlation_id: string | null;
  ip: string | null;
  user_agent: string | null;
  occurred_at: string | null;
};

export type AuditEventFilters = {
  query: string;
  actor_type: string;
  resource_type: string;
  action: string;
  date_from: string;
  date_to: string;
  limit: number;
  offset: number;
};

export type AuditEventFacets = {
  actions: string[];
  resource_types: string[];
  actor_types: string[];
};
