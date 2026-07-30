import { apiRequest } from "@/lib/api";
import type {
  RetentionPolicyResponse,
  RetentionPolicyUpsertRequest,
  SecretCreateRequest,
  SecretGrantCreateRequest,
  SecretGrantResponse,
  SecretWithVersionResponse,
  SystemLimitResponse,
  SystemLimitUpsertRequest,
} from "@/types/governance";

export function createSecret(token: string | null, payload: SecretCreateRequest) {
  return apiRequest<SecretWithVersionResponse>("/secrets", { method: "POST", token, body: JSON.stringify(payload) });
}

export function rotateSecret(token: string | null, secretId: string, payload: { value: string; expires_at?: string }) {
  return apiRequest<SecretWithVersionResponse>(`/secrets/${secretId}/rotate`, { method: "POST", token, body: JSON.stringify(payload) });
}

export function createSecretGrant(token: string | null, secretId: string, payload: SecretGrantCreateRequest) {
  return apiRequest<SecretGrantResponse>(`/secrets/${secretId}/grants`, { method: "POST", token, body: JSON.stringify(payload) });
}

export function revokeSecretGrant(token: string | null, grantId: string) {
  return apiRequest<SecretGrantResponse>(`/secret-grants/${grantId}/revoke`, { method: "POST", token });
}

export function upsertSystemLimit(token: string | null, key: string, payload: SystemLimitUpsertRequest) {
  return apiRequest<SystemLimitResponse>(`/governance/system-limits/${encodeURIComponent(key)}`, {
    method: "PUT",
    token,
    body: JSON.stringify(payload),
  });
}

export function upsertRetentionPolicy(token: string | null, resourceType: string, payload: RetentionPolicyUpsertRequest) {
  return apiRequest<RetentionPolicyResponse>(`/governance/retention-policies/${encodeURIComponent(resourceType)}`, {
    method: "PUT",
    token,
    body: JSON.stringify(payload),
  });
}
