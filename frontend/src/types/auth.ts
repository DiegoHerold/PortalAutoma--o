export type LoginInput = {
  email: string;
  password: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export type CurrentUser = {
  id: number;
  email: string;
  name: string;
  role: string;
  role_id?: number;
  organization_id?: number | null;
  permissions: Array<{
    id?: number | null;
    category_id: number;
    category_name?: string | null;
    can_view: boolean;
    can_execute: boolean;
    can_create: boolean;
    can_edit: boolean;
    can_delete: boolean;
    can_approve: boolean;
  }>;
  rbac_permissions?: string[];
};
