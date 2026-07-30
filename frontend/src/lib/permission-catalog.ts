import type { Role } from "@/types/role";

export const HIGH_IMPACT_PERMISSIONS = new Set(["admin.system", "admin.users", "admin.roles", "secret.manage", "audit.read"]);

export function permissionCatalog(roles: Role[] | null | undefined): string[] {
  return [...new Set((roles ?? []).flatMap((role) => role.permissions ?? []))].sort();
}

export function permissionLabel(permission: string): string {
  const terms: Record<string, string> = { admin: "Administrar", automation: "Automacoes", runtime: "Runtimes", agent: "Agents", execution: "Execucoes", flow: "Fluxos", schedule: "Agendamentos", artifact: "Artefatos", audit: "Auditoria", secret: "Secrets", read: "Ler", create: "Criar", update: "Atualizar", publish: "Publicar", block: "Bloquear", manage: "Gerenciar", disable: "Desabilitar", diagnose: "Diagnosticar", cancel: "Cancelar", retry: "Tentar novamente", trigger: "Disparar", download: "Baixar", metadata: "Metadados", users: "Usuarios", roles: "Papeis", system: "Sistema" };
  return permission.split(".").map((part) => terms[part] ?? part.replaceAll("_", " ")).join(" - ");
}
