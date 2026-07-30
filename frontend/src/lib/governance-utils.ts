import type { AuditEntryResponse, AuditEventResponse, JsonRecord } from "@/types/governance";

const SENSITIVE_KEY = /value|secret|password|token|authorization|api[_-]?key|private[_-]?key|credential|cookie/i;
const REDACTED = "[REDACTED]";

export function redactSensitiveData(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(redactSensitiveData);
  if (!isRecord(value)) return value;
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, SENSITIVE_KEY.test(key) ? REDACTED : redactSensitiveData(item)]));
}

export function normalizeLegacyAuditEntry(entry: AuditEntryResponse): AuditEventResponse {
  return {
    id: entry.id,
    organization_id: null,
    actor_type: entry.actor_type || "unknown",
    actor_id: entry.actor,
    action: entry.action,
    resource_type: entry.entity_type || "unknown",
    resource_id: entry.entity_id || entry.id,
    before: entry.before,
    after: entry.after,
    metadata: entry.message ? { message: entry.message } : {},
    correlation_id: null,
    ip: null,
    user_agent: null,
    occurred_at: entry.created_at,
  };
}

export function auditActionLabel(value: string): string {
  return friendlyLabel(value, { secret_created: "Secret criado", secret_rotated: "Secret rotacionado", secret_grant_created: "Concessão de secret criada", secret_grant_revoked: "Concessão de secret revogada", system_limit_upserted: "Limite do sistema atualizado", retention_policy_upserted: "Política de retenção atualizada" });
}

export function auditResourceLabel(value: string): string {
  return friendlyLabel(value, { secret: "Secret", secret_grant: "Concessão de secret", system_limit: "Limite do sistema", retention_policy: "Política de retenção" });
}

export function auditActorLabel(value: string): string {
  return friendlyLabel(value, { user: "Usuário", system: "Sistema", service_account: "Conta de serviço" });
}

export function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function friendlyLabel(value: string, known: Record<string, string>): string {
  if (known[value]) return known[value];
  return value.replace(/[_-]+/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}
