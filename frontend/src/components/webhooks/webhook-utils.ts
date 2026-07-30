import type { Automation } from "@/types/automation";
import type { Trigger } from "@/types/trigger";

export type WebhookPayload = {
  name: string | null;
  automation_id: number;
  trigger_type: "https";
  route_path: string;
  is_active: boolean;
  parameter_mapping_json: Record<string, string> | null;
};

export function automationName(automations: Automation[] | null | undefined, automationId: number): string {
  return automations?.find((item) => item.id === automationId)?.name ?? `Automacao #${automationId}`;
}

export function webhookStatus(trigger: Trigger): "active" | "inactive" | "invalid" | "legacy" {
  if (trigger.trigger_type === "chained") return "legacy";
  if (!trigger.route_path || !trigger.automation_id) return "invalid";
  return trigger.is_active ? "active" : "inactive";
}

export function triggerToPayload(trigger: Trigger, patch: Partial<WebhookPayload> = {}): WebhookPayload {
  return {
    name: trigger.name ?? trigger.route_path,
    automation_id: trigger.automation_id,
    trigger_type: "https",
    route_path: trigger.route_path,
    is_active: trigger.is_active,
    parameter_mapping_json: trigger.parameter_mapping_json,
    ...patch,
  };
}

export function formatLastSecret(trigger: Trigger): string {
  if (!trigger.secret_configured) return "Sem secret";
  return trigger.secret_last_four ? `****${trigger.secret_last_four}` : "Configurado";
}

export function webhookInvocationUrl(trigger: Trigger, invokeBaseUrl?: string | null): string {
  if (trigger.invocation_url) return trigger.invocation_url;
  const base = (invokeBaseUrl || "").replace(/\/$/, "");
  if (!base || !trigger.route_path) return "";
  return `${base}/${trigger.route_path.replace(/^\//, "")}`;
}

export function conditionLabel(condition?: string | null): string {
  if (condition === "success") return "Ao concluir com sucesso";
  if (condition === "failed") return "Ao falhar";
  if (condition === "always") return "Sempre";
  return "-";
}

export function mappingSummary(mapping: Record<string, string> | null | undefined): string {
  const count = Object.keys(mapping || {}).length;
  return count > 0 ? `${count} parametro(s) mapeado(s)` : "payload bruto";
}
