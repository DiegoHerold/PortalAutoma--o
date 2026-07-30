import { apiRequest } from "@/lib/api";
import type {
  Agent,
  AgentCommandAck,
  AgentConfigurationPatch,
  AgentConfigurationUpdateResult,
  AgentCredential,
  RegistrationToken,
  RotateCredentialResult,
} from "@/types/agent";

// ---- Ações administrativas (POST /agents/{id}/*) ----

function mutateStatus(token: string, agentId: string, action: "enable" | "disable" | "drain" | "resume") {
  return apiRequest<Agent>(`/agents/${agentId}/${action}`, { method: "POST", token });
}

export const enableAgent = (token: string, agentId: string) => mutateStatus(token, agentId, "enable");
export const drainAgent = (token: string, agentId: string) => mutateStatus(token, agentId, "drain");
export const resumeAgent = (token: string, agentId: string) => mutateStatus(token, agentId, "resume");

export function disableAgent(token: string, agentId: string, reason?: string) {
  return apiRequest<Agent>(`/agents/${agentId}/disable`, { method: "POST", token, body: JSON.stringify({ reason: reason || null }) });
}

export function setAgentMaintenance(token: string, agentId: string, enabled: boolean) {
  return apiRequest<Agent>(`/agents/${agentId}/maintenance`, { method: "POST", token, body: JSON.stringify({ enabled }) });
}

export function requestAgentDiagnostics(token: string, agentId: string, payload: Record<string, unknown> = {}) {
  return apiRequest<AgentCommandAck>(`/agents/${agentId}/diagnostics`, { method: "POST", token, body: JSON.stringify({ payload }) });
}

export function requestAgentCapabilitiesRefresh(token: string, agentId: string) {
  return apiRequest<AgentCommandAck>(`/agents/${agentId}/capabilities/refresh`, { method: "POST", token });
}

export function requestAgentUpdate(token: string, agentId: string, desiredVersion: string) {
  return apiRequest<AgentCommandAck>(`/agents/${agentId}/update`, { method: "POST", token, body: JSON.stringify({ desired_version: desiredVersion }) });
}

// ---- Configuração (PATCH /agents/{id}) ----
// A rota tem duas formas de resposta dependendo do que é enviado (backend/.../api/routes.py::patch_agent):
// enviar `configuration`/`desired_version` devolve {configuration, command}; enviar só `name` devolve o Agent.
// Por isso duas funções tipadas separadas em vez de uma só genérica.

export function updateAgentConfiguration(token: string, agentId: string, patch: AgentConfigurationPatch) {
  return apiRequest<AgentConfigurationUpdateResult>(`/agents/${agentId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify({ configuration: patch }),
  });
}

export function renameAgent(token: string, agentId: string, name: string) {
  return apiRequest<Agent>(`/agents/${agentId}`, { method: "PATCH", token, body: JSON.stringify({ name }) });
}

// ---- Tokens de registro (globais, não por Agent) ----

export function createRegistrationToken(token: string, body: { expires_in_seconds: number; metadata?: Record<string, unknown> }) {
  return apiRequest<RegistrationToken>("/agents/registration-tokens", { method: "POST", token, body: JSON.stringify(body) });
}

export function revokeRegistrationToken(token: string, tokenId: string) {
  return apiRequest<RegistrationToken>(`/agents/registration-tokens/${tokenId}/revoke`, { method: "POST", token });
}

// ---- Credenciais do Agent ----

export function rotateAgentCredential(token: string, agentId: string) {
  return apiRequest<RotateCredentialResult>(`/agents/${agentId}/credentials/rotate`, { method: "POST", token });
}

export function revokeAgentCredential(token: string, agentId: string, credentialId: string) {
  return apiRequest<AgentCredential>(`/agents/${agentId}/credentials/revoke`, {
    method: "POST",
    token,
    body: JSON.stringify({ credential_id: credentialId }),
  });
}
