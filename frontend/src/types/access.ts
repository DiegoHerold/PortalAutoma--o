export type OrganizationResponse = {
  id: number;
  key: string;
  name: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
};

export type OrganizationCreateRequest = { key: string; name: string; status?: string };
export type OrganizationUpdateRequest = OrganizationCreateRequest;

export type TeamResponse = {
  id: number;
  organization_id: number;
  key: string;
  name: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
};

export type TeamCreateRequest = { organization_id: number; key: string; name: string; status: string };
export type TeamUpdateRequest = TeamCreateRequest;

export type ServiceAccountResponse = {
  id: string;
  organization_id: number | null;
  name: string;
  status: string;
  permissions: string[];
  created_at: string | null;
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
};

export type ServiceAccountCreateRequest = {
  name: string;
  organization_id?: number;
  permissions: string[];
  expires_at?: string;
};
export type ServiceAccountUpdateRequest = ServiceAccountCreateRequest;

export type CreatedServiceAccountResponse = { service_account: ServiceAccountResponse; credential: string };
