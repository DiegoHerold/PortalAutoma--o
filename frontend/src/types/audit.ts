export type AuditEntry = {
  id: number | string;
  actor?: string | null;
  actor_type?: string | null;
  action: string;
  entity_type?: string | null;
  entity_id?: number | string | null;
  created_at: string;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
  message?: string | null;
};
