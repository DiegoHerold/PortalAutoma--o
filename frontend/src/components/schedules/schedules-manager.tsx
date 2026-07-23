"use client";

import { useMemo, useState } from "react";
import { CalendarClock, Pencil, Plus, Trash2 } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Select, Label, Field } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { describeCron } from "@/lib/cron";
import type { Schedule } from "@/types/schedule";
import type { Automation } from "@/types/automation";

const emptyForm = {
  automation_id: "",
  cron_expression: "0 8 * * *",
  timezone: "America/Sao_Paulo",
  is_active: true,
};

export function SchedulesManager() {
  const { token } = useAuth();
  const { toast } = useToast();
  const schedules = useApi<Schedule[]>("/schedules");
  const automations = useApi<Automation[]>("/automations");
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [editing, setEditing] = useState<Schedule | null>(null);
  const [form, setForm] = useState(emptyForm);

  const nameOf = useMemo(() => {
    const map = new Map<number, string>();
    automations.data?.forEach((a) => map.set(a.id, a.name));
    return map;
  }, [automations.data]);

  function openCreate() {
    setEditing(null);
    setForm({ ...emptyForm, automation_id: automations.data?.[0] ? String(automations.data[0].id) : "" });
    setOpen(true);
  }

  function openEdit(schedule: Schedule) {
    setEditing(schedule);
    setForm({
      automation_id: String(schedule.automation_id),
      cron_expression: schedule.cron_expression,
      timezone: schedule.timezone,
      is_active: schedule.is_active,
    });
    setOpen(true);
  }

  async function save() {
    if (!token || !form.automation_id) return;
    setSubmitting(true);
    try {
      await apiRequest<Schedule>(editing ? `/schedules/${editing.id}` : "/schedules", {
        method: editing ? "PUT" : "POST",
        token,
        body: JSON.stringify({ ...form, automation_id: Number(form.automation_id) }),
      });
      toast({ title: editing ? "Agendamento atualizado" : "Agendamento criado", kind: "success" });
      setEditing(null);
      setForm(emptyForm);
      setOpen(false);
      await schedules.refetch();
    } catch (err) {
      toast({ title: "Falha ao salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(schedule: Schedule) {
    if (!token) return;
    if (!window.confirm(`Apagar o agendamento "${schedule.cron_expression}"?`)) return;
    try {
      await apiRequest<void>(`/schedules/${schedule.id}`, { method: "DELETE", token });
      toast({ title: "Agendamento apagado", kind: "success" });
      await schedules.refetch();
    } catch (err) {
      toast({ title: "Falha ao apagar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  if (schedules.error) return <ErrorState message={schedules.error} onRetry={schedules.refetch} />;

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" /> Novo agendamento
        </Button>
      </div>

      {schedules.loading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))}
        </div>
      ) : (schedules.data ?? []).length === 0 ? (
        <EmptyState icon={CalendarClock} title="Sem agendamentos" description="Crie o primeiro agendamento." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {schedules.data!.map((s) => (
            <Card key={s.id} className="p-5">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="truncate font-display text-base font-semibold">{nameOf.get(s.automation_id) ?? `Automacao #${s.automation_id}`}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{describeCron(s.cron_expression)}</p>
                </div>
                <div className="flex items-center gap-1">
                  <Badge tone={s.is_active ? "success" : "neutral"}>{s.is_active ? "Ativo" : "Inativo"}</Badge>
                  <Button size="icon" variant="ghost" onClick={() => openEdit(s)} title="Editar agendamento">
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button size="icon" variant="ghost" onClick={() => remove(s)} title="Apagar agendamento">
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
                <code className="tabular rounded bg-muted px-2 py-1 text-xs">{s.cron_expression}</code>
                <span className="text-xs text-muted-foreground">{s.timezone}</span>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? "Editar agendamento" : "Novo agendamento"}
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={save} disabled={submitting || !form.automation_id || !form.cron_expression || !form.timezone}>
              {submitting && <Spinner />} {editing ? "Salvar" : "Criar"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field>
            <Label htmlFor="s-automation">Automacao</Label>
            <Select id="s-automation" value={form.automation_id} onChange={(e) => setForm({ ...form, automation_id: e.target.value })}>
              <option value="">Selecione...</option>
              {automations.data?.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field>
            <Label htmlFor="s-cron">Cron</Label>
            <Input id="s-cron" className="tabular" value={form.cron_expression} onChange={(e) => setForm({ ...form, cron_expression: e.target.value })} />
          </Field>
          <Field>
            <Label htmlFor="s-timezone">Timezone</Label>
            <Input id="s-timezone" className="tabular" value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} />
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              className="h-4 w-4 accent-primary"
            />
            Ativo
          </label>
        </div>
      </Modal>
    </div>
  );
}
