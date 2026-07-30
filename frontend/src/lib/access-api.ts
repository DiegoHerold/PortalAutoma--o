import { apiRequest } from "@/lib/api";
import type { CreatedServiceAccountResponse, OrganizationCreateRequest, OrganizationResponse, OrganizationUpdateRequest, ServiceAccountCreateRequest, ServiceAccountResponse, ServiceAccountUpdateRequest, TeamCreateRequest, TeamResponse, TeamUpdateRequest } from "@/types/access";

export function createOrganization(token: string | null, payload: OrganizationCreateRequest) {
  return apiRequest<OrganizationResponse>("/organizations", { method: "POST", token, body: JSON.stringify(payload) });
}

export function updateOrganization(token: string | null, organizationId: number, payload: OrganizationUpdateRequest) {
  return apiRequest<OrganizationResponse>(`/organizations/${organizationId}`, { method: "PUT", token, body: JSON.stringify(payload) });
}

export function deleteOrganization(token: string | null, organizationId: number) {
  return apiRequest<void>(`/organizations/${organizationId}`, { method: "DELETE", token });
}

export function createTeam(token: string | null, payload: TeamCreateRequest) {
  return apiRequest<TeamResponse>("/teams", { method: "POST", token, body: JSON.stringify(payload) });
}

export function updateTeam(token: string | null, teamId: number, payload: TeamUpdateRequest) {
  return apiRequest<TeamResponse>(`/teams/${teamId}`, { method: "PUT", token, body: JSON.stringify(payload) });
}

export function deleteTeam(token: string | null, teamId: number) {
  return apiRequest<void>(`/teams/${teamId}`, { method: "DELETE", token });
}

export function createServiceAccount(token: string | null, payload: ServiceAccountCreateRequest) {
  return apiRequest<CreatedServiceAccountResponse>("/service-accounts", { method: "POST", token, body: JSON.stringify(payload) });
}

export function updateServiceAccount(token: string | null, serviceAccountId: string, payload: ServiceAccountUpdateRequest) {
  return apiRequest<ServiceAccountResponse>(`/service-accounts/${encodeURIComponent(serviceAccountId)}`, { method: "PUT", token, body: JSON.stringify(payload) });
}

export function deleteServiceAccount(token: string | null, serviceAccountId: string) {
  return apiRequest<void>(`/service-accounts/${encodeURIComponent(serviceAccountId)}`, { method: "DELETE", token });
}

export function revokeServiceAccount(token: string | null, serviceAccountId: string) {
  return apiRequest<ServiceAccountResponse>(`/service-accounts/${encodeURIComponent(serviceAccountId)}/revoke`, { method: "POST", token });
}
