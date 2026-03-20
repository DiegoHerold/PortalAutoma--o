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
  permissions: Array<{
    category_id: number;
    can_view: boolean;
    can_execute: boolean;
    can_create: boolean;
    can_edit: boolean;
    can_delete: boolean;
    can_approve: boolean;
  }>;
};
