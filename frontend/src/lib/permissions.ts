import type { User } from "@/types/user";
import type { CurrentUser } from "@/types/auth";

export function isAdminRole(role: string) {
  return role === "admin";
}

/**
 * @deprecated Baseado no modelo legado de permissões por categoria (User.category_permissions).
 * Prefira `hasPermission`, que espelha o RBAC real do backend (modules/access/domain/permission.py).
 */
export function canUserAccessPage(user: User | null, action: keyof User["category_permissions"][number]) {
  if (!user) return false;
  if (isAdminRole(user.role.slug)) return true;
  return user.category_permissions.some((permission) => permission[action]);
}

/**
 * Espelha PermissionChecker.has_permission do backend (modules/access/application/use_cases.py):
 * admin sempre passa; caso contrário verifica a lista `rbac_permissions` do usuário autenticado.
 * Isto é só para esconder/mostrar itens de navegação e ações na UI — a autorização real
 * é sempre reforçada pelo backend em cada endpoint.
 */
export function hasPermission(user: CurrentUser | null, permission: string): boolean {
  if (!user) return false;
  if (user.role === "admin") return true;
  return (user.rbac_permissions ?? []).includes(permission);
}

/** Verdadeiro se o usuário tiver qualquer uma das permissões informadas (ou for admin). */
export function hasAnyPermission(user: CurrentUser | null, permissions: string[]): boolean {
  if (!user) return false;
  if (user.role === "admin") return true;
  if (permissions.length === 0) return true;
  const granted = new Set(user.rbac_permissions ?? []);
  return permissions.some((permission) => granted.has(permission));
}

/** O papel da pessoa inclui a funcionalidade (em "ver" ou "gerenciar")? Admin tem todas. */
export function podeVer(user: CurrentUser | null, funcionalidade: string): boolean {
  if (!user) return false;
  if (user.role === "admin") return true;
  const tem = new Set(user.rbac_permissions ?? []);
  return tem.has(`${funcionalidade}.ver`) || tem.has(`${funcionalidade}.gerenciar`);
}

/** O papel da pessoa inclui a funcionalidade em "gerenciar" (vê e altera)? */
export function podeGerenciar(user: CurrentUser | null, funcionalidade: string): boolean {
  if (!user) return false;
  return user.role === "admin" || (user.rbac_permissions ?? []).includes(`${funcionalidade}.gerenciar`);
}

/** A regra do menu: o item aparece se o papel inclui a funcionalidade dele. Sem funcionalidade
 * (Configurações), aparece para qualquer pessoa logada. */
export function itemVisivel(item: { funcionalidade?: string }, user: CurrentUser | null): boolean {
  if (!user) return false;
  return !item.funcionalidade || podeVer(user, item.funcionalidade);
}

/** @deprecated Use ``podeVer``/``podeGerenciar`` com a funcionalidade (Papéis globais). */
export function isAdminOrManager(user: CurrentUser | null): boolean {
  if (!user) return false;
  return user.role === "admin" || user.role === "manager";
}
