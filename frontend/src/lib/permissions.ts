import type { User } from "@/types/user";

export function isAdminRole(role: string) {
  return role === "admin";
}

export function canUserAccessPage(user: User | null, action: keyof User["category_permissions"][number]) {
  if (!user) return false;
  if (isAdminRole(user.role.slug)) return true;
  return user.category_permissions.some((permission) => permission[action]);
}
