import { apiRequest } from "@/lib/api";
import type { Automation } from "@/types/automation";
import type { AutomationVersionResponse as AutomationVersion } from "@/types/catalog";
import type { RecurrenceType, Schedule } from "@/types/schedule";
import type { Trigger } from "@/types/trigger";

export type ExecutionMode = "manual" | "webhook" | "scheduled";

export type AutomationConfigForm = {
  name: string;
  slug: string;
  description: string;
  category_id: string;
  executor_type: string;
  package_url: string;
  package_sha256: string;
  default_priority: string;
  timeout_seconds: number;
  max_retries: number;
  is_active: boolean;
  execution_mode: ExecutionMode;
  schedule_recurrence_type: RecurrenceType;
  schedule_time_of_day: string; // "HH:MM"
  schedule_weekdays: number[]; // 0=Seg .. 6=Dom, used when recurrence_type === "weekly"
  schedule_day_of_month: number; // 1-31, 0 = último dia -- used when recurrence_type === "monthly"
  schedule_specific_date: string; // "YYYY-MM-DD" -- used when recurrence_type === "once"
  schedule_timezone: string;
  worker_ids: number[];
};

export function slugify(value: string) {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export async function syncExecutionConfig(
  token: string,
  automationId: number,
  slug: string,
  form: AutomationConfigForm,
  existingTrigger: Trigger | undefined,
  existingSchedule: Schedule | undefined,
) {
  if (form.execution_mode === "webhook") {
    // Webhook creation is handled by /webhooks, where the one-time secret can
    // be shown safely to the operator.
  } else if (existingTrigger) {
    await apiRequest(`/triggers/${existingTrigger.id}`, { method: "DELETE", token });
  }

  if (form.execution_mode === "scheduled") {
    const body = JSON.stringify({
      automation_id: automationId,
      timezone: form.schedule_timezone,
      is_active: true,
      recurrence_type: form.schedule_recurrence_type,
      time_of_day: form.schedule_time_of_day,
      weekdays: form.schedule_recurrence_type === "weekly" ? form.schedule_weekdays : null,
      day_of_month: form.schedule_recurrence_type === "monthly" ? form.schedule_day_of_month : null,
      specific_date: form.schedule_recurrence_type === "once" ? form.schedule_specific_date : null,
    });
    if (existingSchedule) {
      await apiRequest(`/schedules/${existingSchedule.id}`, { method: "PUT", token, body });
    } else {
      await apiRequest("/schedules", { method: "POST", token, body });
    }
  } else if (existingSchedule) {
    await apiRequest(`/schedules/${existingSchedule.id}`, { method: "DELETE", token });
  }

  await apiRequest(`/automations/${automationId}/worker-preferences`, {
    method: "PUT",
    token,
    body: JSON.stringify({
      preferences: form.worker_ids.map((worker_id, priority_order) => ({ worker_id, priority_order })),
    }),
  });
}

export async function applyImportedAutomationConfig(
  token: string,
  stagingId: string,
  form: AutomationConfigForm,
): Promise<AutomationVersion> {
  const version = await apiRequest<AutomationVersion>(`/automations/import/${stagingId}/confirm`, {
    method: "POST",
    token,
    body: JSON.stringify({ category_id: form.category_id ? Number(form.category_id) : null }),
  });

  await apiRequest<Automation>(`/automations/${version.automation_id}`, {
    method: "PUT",
    token,
    body: JSON.stringify({
      name: form.name,
      slug: form.slug,
      description: form.description,
      category_id: Number(form.category_id),
      executor_type: form.executor_type,
      package_url: form.package_url || null,
      package_sha256: form.package_sha256 || null,
      default_priority: form.default_priority,
      timeout_seconds: form.timeout_seconds,
      max_retries: form.max_retries,
      is_active: form.is_active,
    }),
  });

  const [triggers, schedules] = await Promise.all([
    apiRequest<Trigger[]>("/triggers", { token }),
    apiRequest<Schedule[]>("/schedules", { token }),
  ]);
  await syncExecutionConfig(
    token,
    version.automation_id,
    form.slug,
    form,
    triggers.find((trigger) => trigger.automation_id === version.automation_id),
    schedules.find((schedule) => schedule.automation_id === version.automation_id),
  );

  return version;
}
