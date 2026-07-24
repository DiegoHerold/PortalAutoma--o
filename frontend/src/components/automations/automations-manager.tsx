"use client";

import { useMemo, useState } from "react";
import { Plus, Search, Workflow } from "lucide-react";

import { AutomationCard } from "@/components/automations/automation-card";
import { AutomationForm, emptyAutomationForm, type AutomationFormState } from "@/components/automations/automation-form";
import { NewAutomationDialog } from "@/components/automations/new-automation-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type { Automation } from "@/types/automation";
import type { Category } from "@/types/category";
import type { Trigger } from "@/types/trigger";
import type { Schedule } from "@/types/schedule";
import type { Worker, WorkerPreference } from "@/types/worker";

function toForm(
  automation: Automation,
  trigger: Trigger | undefined,
  schedule: Schedule | undefined,
  workerIds: number[],
): AutomationFormState {
  return {
    name: automation.name,
    slug: automation.slug,
    description: automation.description ?? "",
    category_id: String(automation.category_id),
    executor_type: automation.executor_type,
    package_url: automation.package_url ?? "",
    package_sha256: automation.package_sha256 ?? "",
    default_priority: automation.default_priority,
    timeout_seconds: automation.timeout_seconds,
    max_retries: automation.max_retries,
    is_active: automation.is_active,
    execution_mode: schedule ? "scheduled" : trigger ? "webhook" : "manual",
    schedule_cron: schedule?.cron_expression ?? emptyAutomationForm.schedule_cron,
    schedule_timezone: schedule?.timezone ?? emptyAutomationForm.schedule_timezone,
    worker_ids: workerIds,
  };
}

function generateSecret(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID().replace(/-/g, "");
  return Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
}

/**
 * Creates/updates/removes the Trigger and Schedule rows and replaces the
 * worker-preferences list for an automation, based on what the form says.
 * Called after the automation itself is created/updated so we have its id.
 */
async function syncExecutionConfig(
  token: string,
  automationId: number,
  slug: string,
  form: AutomationFormState,
  existingTrigger: Trigger | undefined,
  existingSchedule: Schedule | undefined,
) {
  if (form.execution_mode === "webhook") {
    if (!existingTrigger) {
      const routePath = `${slug}-${Math.random().toString(36).slice(2, 8)}`;
      await apiRequest("/triggers", {
        method: "POST",
        token,
        body: JSON.stringify({
          automation_id: automationId,
          trigger_type: "https",
          route_path: routePath,
          secret_token: generateSecret(),
          is_active: true,
        }),
      });
    }
  } else if (existingTrigger) {
    await apiRequest(`/triggers/${existingTrigger.id}`, { method: "DELETE", token });
  }

  if (form.execution_mode === "scheduled") {
    const body = JSON.stringify({
      automation_id: automationId,
      cron_expression: form.schedule_cron,
      timezone: form.schedule_timezone,
      is_active: true,
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

export function AutomationsManager() {
  const { token } = useAuth();
  const { toast } = useToast();
  const automations = useApi<Automation[]>("/automations");
  const categories = useApi<Category[]>("/categories");
  const workers = useApi<Worker[]>("/workers");
  const triggers = useApi<Trigger[]>("/triggers");
  const schedules = useApi<Schedule[]>("/schedules");

  const [query, setQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [newDialogOpen, setNewDialogOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [editing, setEditing] = useState<Automation | null>(null);

  const editingPreferences = useApi<WorkerPreference[]>(
    editing ? `/automations/${editing.id}/worker-preferences` : null,
  );

  const categoryName = useMemo(() => {
    const map = new Map<number, string>();
    categories.data?.forEach((c) => map.set(c.id, c.name));
    return map;
  }, [categories.data]);

  const editingTrigger = useMemo(
    () => (editing ? triggers.data?.find((t) => t.automation_id === editing.id) : undefined),
    [triggers.data, editing],
  );
  const editingSchedule = useMemo(
    () => (editing ? schedules.data?.find((s) => s.automation_id === editing.id) : undefined),
    [schedules.data, editing],
  );

  const filtered = useMemo(() => {
    const list = automations.data ?? [];
    const q = query.trim().toLowerCase();
    return list.filter((a) => {
      const matchesQuery = !q || a.name.toLowerCase().includes(q) || a.slug.toLowerCase().includes(q);
      const matchesCategory = !categoryFilter || String(a.category_id) === categoryFilter;
      return matchesQuery && matchesCategory;
    });
  }, [automations.data, query, categoryFilter]);

  function openCreate() {
    setNewDialogOpen(true);
  }

  function openEdit(automation: Automation) {
    setEditing(automation);
    setEditModalOpen(true);
  }

  async function saveEdit(form: AutomationFormState) {
    if (!token || !editing) return;
    setSubmitting(true);
    try {
      await apiRequest<Automation>(`/automations/${editing.id}`, {
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
      try {
        await syncExecutionConfig(token, editing.id, form.slug, form, editingTrigger, editingSchedule);
      } catch (syncErr) {
        toast({
          title: "Automação salva, mas houve falha ao salvar gatilho/agendamento/workers",
          description: syncErr instanceof Error ? syncErr.message : undefined,
          kind: "warning",
        });
      }
      toast({ title: "Automacao atualizada", kind: "success" });
      setEditing(null);
      setEditModalOpen(false);
      await Promise.all([automations.refetch(), triggers.refetch(), schedules.refetch()]);
    } catch (err) {
      toast({ title: "Falha ao salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  async function deleteAutomation(automation: Automation) {
    if (!token) return;
    if (!window.confirm(`Apagar a automacao "${automation.name}"? Esta ação não pode ser desfeita.`)) return;
    try {
      await apiRequest<void>(`/automations/${automation.id}`, { method: "DELETE", token });
      toast({ title: "Automacao apagada", kind: "success" });
      await automations.refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : undefined;
      const blocked = message?.toLowerCase().includes("cancele");
      toast({
        title: blocked ? "Automação tem execuções ativas" : "Falha ao apagar",
        description: blocked
          ? "Cancele os jobs em andamento ou na fila (na tela de Jobs) antes de apagar esta automação."
          : message,
        kind: "error",
      });
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Buscar por nome ou slug..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <Select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="sm:w-56">
          <option value="">Todas as categorias</option>
          {categories.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" /> Nova automacao
        </Button>
      </div>

      {automations.error ? (
        <ErrorState message={automations.error} onRetry={automations.refetch} />
      ) : automations.loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40 rounded-lg" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Workflow}
          title="Nenhuma automacao"
          description={query || categoryFilter ? "Nenhum resultado para o filtro atual." : "Crie sua primeira automacao."}
          action={
            !query && !categoryFilter ? (
              <Button onClick={openCreate}>
                <Plus className="h-4 w-4" /> Nova automacao
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((a) => (
            <AutomationCard
              key={a.id}
              automation={a}
              categoryName={categoryName.get(a.category_id)}
              onEdit={openEdit}
              onDelete={deleteAutomation}
            />
          ))}
        </div>
      )}

      <NewAutomationDialog
        open={newDialogOpen}
        onClose={() => setNewDialogOpen(false)}
        categories={categories.data ?? []}
        onImported={() => void automations.refetch()}
      />

      <Modal
        open={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        title="Editar automacao"
        description="Atualize metadados, prioridade, executor, disparo e workers."
        className="max-w-2xl"
      >
        {editing && editingPreferences.loading ? (
          <Skeleton className="h-64 rounded-lg" />
        ) : (
        <AutomationForm
          key={editing?.id ?? "edit"}
          categories={categories.data ?? []}
          workers={workers.data ?? []}
          webhookPreview={editingTrigger?.route_path ?? null}
          onSubmit={saveEdit}
          submitting={submitting}
          initial={
            editing
              ? toForm(
                  editing,
                  editingTrigger,
                  editingSchedule,
                  (editingPreferences.data ?? []).sort((a, b) => a.priority_order - b.priority_order).map((p) => p.worker_id),
                )
              : undefined
          }
          submitLabel="Salvar automacao"
        />
        )}
      </Modal>
    </div>
  );
}
