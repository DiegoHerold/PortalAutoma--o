export type Role = {
  id: number;
  name: string;
  slug: string;
  description?: string | null;
  permissions?: string[];
};

export type CategoryPermission = {
  id?: number | null;
  category_id: number;
  category_name?: string | null;
  can_view: boolean;
  can_execute: boolean;
  can_create: boolean;
  can_edit: boolean;
  can_delete: boolean;
  can_approve: boolean;
};

export type User = {
  id: number;
  name: string;
  email: string;
  status?: "pending" | "active" | "disabled" | "locked" | "archived" | string;
  is_active: boolean;
  /** Ainda não criou a senha pelo convite (13/11/2026). */
  aguardando_senha?: boolean;
  /** Só na criação: o convite saiu por e-mail? null quando a pessoa já tinha senha. */
  convite_enviado?: boolean | null;
  role: Role;
  organization_id?: number | null;
  permissions?: string[];
  rbac_permissions?: string[];
  category_permissions: CategoryPermission[];
  last_login_at?: string | null;
  disabled_at?: string | null;
};
