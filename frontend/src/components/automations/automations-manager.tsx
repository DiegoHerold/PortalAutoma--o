"use client";

import { useMemo, useState } from "react";
import { Plus, Search, Workflow } from "lucide-react";

import { AutomationCard, type UltimaExecucao } from "@/components/automations/automation-card";
import { useDisparo } from "@/components/painel/disparo-rapido";
import { podeGerenciar } from "@/lib/permissions";
import type { VisaoFila } from "@/lib/fila";
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
import { useAvisos } from "@/hooks/use-avisos";
import type { Painel } from "@/lib/painel";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { syncExecutionConfig } from "@/lib/automation-config";
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
    schedule_recurrence_type: schedule?.recurrence_type ?? emptyAutomationForm.schedule_recurrence_type,
    schedule_time_of_day: schedule?.time_of_day ?? emptyAutomationForm.schedule_time_of_day,
    schedule_weekdays: schedule?.weekdays ?? emptyAutomationForm.schedule_weekdays,
    schedule_day_of_month: schedule?.day_of_month ?? emptyAutomationForm.schedule_day_of_month,
    schedule_specific_date: schedule?.specific_date ?? emptyAutomationForm.schedule_specific_date,
    schedule_timezone: schedule?.timezone ?? emptyAutomationForm.schedule_timezone,
    worker_ids: workerIds,
  };
}

export function AutomationsManager() {
  const { token } = useAuth();
  const { toast } = useToast();
  const automations = useApi<Automation[]>("/automations");
  const painel = useApi<Painel>("/painel", { pollMs: 30000 });
  useAvisos("/painel/avisos", () => void painel.refetch(), 1500);
  const rodandoPor = new Map<number, number>();
  for (const e of painel.data?.execucoes ?? []) {
    if (e.automation_id != null) rodandoPor.set(e.automation_id, (rodandoPor.get(e.automation_id) ?? 0) + 1);
  }
  const { user } = useAuth();
  const gerencia = podeGerenciar(user, "automacoes");
  // Para os cartões: a última execução de cada uma, quantas na fila e quais a pessoa pode executar.
  const recentes = useApi<{ automacoes: Array<{ automation_id: number; ultima: UltimaExecucao }> }>("/painel/recentes?limite=200",
    { pollMs: 60000 });
  const fila = useApi<VisaoFila>("/fila", { pollMs: 30000 });
  const executaveis = useApi<{ automacoes: Array<{ id: number }> }>("/painel/executaveis");
  const ultimaPor = new Map<number, UltimaExecucao>();
  for (const r of Array.isArray(recentes.data?.automacoes) ? recentes.data.automacoes : []) ultimaPor.set(r.automation_id, r.ultima);
  const naFilaPor = new Map<number, number>();
  for (const j of Array.isArray(fila.data?.jobs) ? fila.data.jobs : []) {
    if (j.automation_id != null) naFilaPor.set(j.automation_id, (naFilaPor.get(j.automation_id) ?? 0) + 1);
  }
  const podeExecutar = new Set((Array.isArray(executaveis.data?.automacoes) ? executaveis.data.automacoes : []).map((a) => a.id));
  const { disparar, janela } = useDisparo(() => { void fila.refetch(); void painel.refetch(); });
  const categories = useApi<Category[]>("/categories");
  const workers = useApi<Worker[]>("/workers");
  const schedules = useApi<Schedule[]>("/schedules");

  const [query, setQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [verArquivadas, setVerArquivadas] = useState(false);
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

  // Webhooks saíram do cadastro da automação (13/11/2026): ficam em Operação > Webhooks e na aba Técnico.
  const editingTrigger = useMemo<Trigger | undefined>(
    () => undefined,
    [],
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
      const arquivada = a.status === "archived";
      return matchesQuery && matchesCategory && arquivada === verArquivadas;
    });
  }, [automations.data, query, categoryFilter, verArquivadas]);
  const arquivadas = (automations.data ?? []).filter((a) => a.status === "archived").length;

  function openCreate() {
    setNewDialogOpen(true);
  }

  function openEdit(automation: Automation) {
    setEditing(automation);
    setEditModalOpen(true);
  }

  const creationDependenciesLoading = categories.loading || workers.loading;

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
      await Promise.all([automations.refetch(), schedules.refetch()]);
    } catch (err) {
      toast({ title: "Falha ao salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  async function deleteAutomation(automation: Automation) {
    if (!token) return;
    if (!window.confirm(`Arquivar "${automation.name}"?\n\nEla sai do Catálogo e não pode mais ser executada. O histórico, os itens e a auditoria continuam guardados, e dá para restaurar em "Arquivadas".`)) return;
    try {
      await apiRequest<void>(`/automations/${automation.id}`, { method: "DELETE", token });
      toast({ title: "Automação arquivada", description: "Para voltar, use Arquivadas > Restaurar.", kind: "success" });
      await automations.refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : undefined;
      const blocked = message?.toLowerCase().includes("cancele");
      toast({
        title: blocked ? "Automação tem execuções ativas" : "Não foi possível arquivar",
        description: blocked
          ? "Cancele as execuções em andamento ou aguardando na página de Execuções antes de arquivar esta automação."
          : message,
        kind: "error",
      });
    }
  }

  async function restaurar(automation: Automation) {
    if (!token) return;
    try {
      await apiRequest(`/automations/${automation.id}/restaurar`, { method: "POST", token });
      toast({ title: `${automation.name} de volta ao Catálogo`, kind: "success" });
      await automations.refetch();
    } catch (err) {
      toast({ title: "Não foi possível restaurar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Buscar automação..."
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
        <Button variant={verArquivadas ? "primary" : "outline"} onClick={() => setVerArquivadas((v) => !v)} aria-pressed={verArquivadas}>
          {verArquivadas ? "Voltar ao Catálogo" : `Arquivadas${arquivadas ? ` (${arquivadas})` : ""}`}
        </Button>
        {gerencia && (
          <Button onClick={openCreate} disabled={creationDependenciesLoading}>
            <Plus className="h-4 w-4" /> Nova automação
          </Button>
        )}
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
              <Button onClick={openCreate} disabled={creationDependenciesLoading}>
                <Plus className="h-4 w-4" /> Nova automação
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
              rodando={rodandoPor.get(a.id) ?? 0}
              naFila={naFilaPor.get(a.id) ?? 0}
              ultima={ultimaPor.get(a.id) ?? null}
              onExecutar={a.status !== "archived" && a.is_active && podeExecutar.has(a.id)
                ? (x) => disparar({ id: x.id, nome: x.name }) : undefined}
              onEdit={a.status === "archived" || !gerencia ? undefined : openEdit}
              onDelete={a.status === "archived" || !gerencia ? undefined : deleteAutomation}
              onRestore={a.status === "archived" && gerencia ? restaurar : undefined}
            />
          ))}
        </div>
      )}

      {janela}

      <NewAutomationDialog
        open={newDialogOpen}
        onClose={() => setNewDialogOpen(false)}
        categories={categories.data ?? []}
        workers={workers.data ?? []}
        onImported={() => void Promise.all([automations.refetch(), schedules.refetch()])}
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
