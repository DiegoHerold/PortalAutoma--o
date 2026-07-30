"use client";

import { useEffect, useMemo, useState } from "react";

import { ScheduleOccurrencesPreview } from "@/components/schedules/schedule-occurrences-preview";
import { Button } from "@/components/ui/button";
import { Field, Input, Label, Select } from "@/components/ui/input";
import { Sheet } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { pickHeadlineVersion } from "@/lib/flow-api";
import { createSchedule, updateSchedule } from "@/lib/schedule-api";
import { MISFIRE_POLICY_OPTIONS, OVERLAP_POLICY_OPTIONS } from "@/lib/schedule-policies";
import { flowVersionStatusMeta } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { Automation } from "@/types/automation";
import type { Flow, FlowVersion } from "@/types/flow";
import type { MisfirePolicy, OverlapPolicy, RecurrenceType, Schedule, SchedulePreviewPayload, ScheduleWritePayload, TargetType } from "@/types/schedule";

const RECURRENCE_TYPES: { value: RecurrenceType; label: string }[] = [
  { value: "daily", label: "Todo dia" },
  { value: "weekly", label: "Dias da semana" },
  { value: "monthly", label: "Mensal" },
  { value: "once", label: "Data específica" },
];

const WEEKDAY_BUTTON_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];

type FormState = {
  target_type: TargetType;
  automation_id: string;
  flow_id: string;
  flow_version_id: string;
  name: string;
  timezone: string;
  is_active: boolean;
  mode: "recurrence" | "interval";
  recurrence_type: RecurrenceType;
  time_of_day: string;
  weekdays: number[];
  day_of_month: number;
  specific_date: string;
  interval_seconds: number;
  misfire_policy: MisfirePolicy;
  misfire_grace_seconds: number;
  max_catch_up_runs: number;
  overlap_policy: OverlapPolicy;
};

function emptyForm(prefill?: { targetType?: TargetType; specificDate?: string; automationId?: string }): FormState {
  return {
    target_type: prefill?.targetType ?? "automation",
    automation_id: prefill?.automationId ?? "",
    flow_id: "",
    flow_version_id: "",
    name: "",
    timezone: "America/Sao_Paulo",
    is_active: true,
    mode: "recurrence",
    recurrence_type: prefill?.specificDate ? "once" : "daily",
    time_of_day: "08:00",
    weekdays: [0, 1, 2, 3, 4],
    day_of_month: 1,
    specific_date: prefill?.specificDate ?? "",
    interval_seconds: 300,
    misfire_policy: "run_once_now",
    misfire_grace_seconds: 3600,
    max_catch_up_runs: 1,
    overlap_policy: "forbid",
  };
}

function scheduleToForm(schedule: Schedule): FormState {
  return {
    target_type: schedule.target_type,
    automation_id: schedule.automation_id != null ? String(schedule.automation_id) : "",
    flow_id: schedule.flow_id ?? "",
    flow_version_id: schedule.flow_version_id ?? "",
    name: schedule.name ?? "",
    timezone: schedule.timezone,
    is_active: schedule.is_active,
    mode: schedule.schedule_type === "interval" ? "interval" : "recurrence",
    recurrence_type: schedule.recurrence_type,
    time_of_day: schedule.time_of_day,
    weekdays: schedule.weekdays ?? [0, 1, 2, 3, 4],
    day_of_month: schedule.day_of_month ?? 1,
    specific_date: schedule.specific_date ?? "",
    interval_seconds: schedule.interval_seconds ?? 300,
    misfire_policy: (schedule.misfire_policy as MisfirePolicy) ?? "run_once_now",
    misfire_grace_seconds: schedule.misfire_grace_seconds ?? 3600,
    max_catch_up_runs: schedule.max_catch_up_runs ?? 1,
    overlap_policy: (schedule.overlap_policy as OverlapPolicy) ?? "forbid",
  };
}

function buildPayload(form: FormState): ScheduleWritePayload {
  return {
    target_type: form.target_type,
    automation_id: form.target_type === "automation" && form.automation_id ? Number(form.automation_id) : null,
    flow_id: form.target_type === "flow" ? form.flow_id || null : null,
    flow_version_id: form.target_type === "flow" ? form.flow_version_id || null : null,
    name: form.name.trim() ? form.name.trim() : null,
    timezone: form.timezone,
    is_active: form.is_active,
    schedule_type: form.mode === "interval" ? "interval" : null,
    recurrence_type: form.recurrence_type,
    time_of_day: form.time_of_day,
    weekdays: form.mode === "recurrence" && form.recurrence_type === "weekly" ? form.weekdays : null,
    day_of_month: form.mode === "recurrence" && form.recurrence_type === "monthly" ? form.day_of_month : null,
    specific_date: form.mode === "recurrence" && form.recurrence_type === "once" ? form.specific_date || null : null,
    interval_seconds: form.mode === "interval" ? form.interval_seconds : null,
    misfire_policy: form.misfire_policy,
    max_catch_up_runs: form.max_catch_up_runs,
    misfire_grace_seconds: form.misfire_grace_seconds,
    overlap_policy: form.overlap_policy,
  };
}

/**
 * Espelha as regras de ScheduleCreateRequest._check_recurrence_fields (backend/.../api/schemas.py)
 * para dar erro amigável antes do submit. O 422 do backend continua sendo a fonte da verdade —
 * esta validação é só uma conveniência de UX, não substitui a checagem do servidor.
 */
function validate(form: FormState): string[] {
  const errors: string[] = [];
  if (form.target_type === "automation" && !form.automation_id) errors.push("Selecione uma automação.");
  if (form.target_type === "flow" && !form.flow_version_id) errors.push("Selecione uma versão do fluxo.");
  if (form.mode === "interval") {
    if (!form.interval_seconds || form.interval_seconds < 60) errors.push("O intervalo deve ser de pelo menos 60 segundos.");
  } else if (form.recurrence_type === "weekly" && form.weekdays.length === 0) {
    errors.push("Selecione ao menos um dia da semana.");
  } else if (form.recurrence_type === "monthly" && (form.day_of_month === null || Number.isNaN(form.day_of_month))) {
    errors.push("Informe o dia do mês.");
  } else if (form.recurrence_type === "once" && !form.specific_date) {
    errors.push("Informe a data específica.");
  }
  return errors;
}

export function ScheduleFormSheet({
  open,
  onClose,
  editingId,
  prefill,
  automations,
  flows,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  editingId: number | null;
  prefill?: { targetType?: TargetType; specificDate?: string; automationId?: string };
  automations: Automation[];
  flows: Flow[];
  onSaved: (schedule: Schedule) => void | Promise<void>;
}) {
  const { token } = useAuth();
  const { toast } = useToast();

  const editingQuery = useApi<Schedule>(editingId ? `/schedules/${editingId}` : null, { enabled: open && !!editingId });
  const editing = editingId ? (editingQuery.data ?? null) : null;

  const [form, setForm] = useState<FormState>(() => emptyForm(prefill));
  const [submitting, setSubmitting] = useState(false);
  const [showErrors, setShowErrors] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (editingId && !editing) return; // aguarda o fetch do Schedule sendo editado
    setForm(editing ? scheduleToForm(editing) : emptyForm(prefill));
    setShowErrors(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, editingId, editing?.id]);

  const flowVersions = useApi<FlowVersion[]>(form.flow_id ? `/flows/${form.flow_id}/versions` : null, {
    enabled: open && form.target_type === "flow" && !!form.flow_id,
  });

  useEffect(() => {
    if (form.target_type !== "flow" || !flowVersions.data || form.flow_version_id) return;
    const headline = pickHeadlineVersion(flowVersions.data);
    if (headline) setForm((f) => ({ ...f, flow_version_id: headline.id }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flowVersions.data]);

  function toggleWeekday(day: number) {
    setForm((f) => ({ ...f, weekdays: f.weekdays.includes(day) ? f.weekdays.filter((d) => d !== day) : [...f.weekdays, day].sort() }));
  }

  const errors = useMemo(() => validate(form), [form]);

  const previewPayload = useMemo<SchedulePreviewPayload | null>(() => {
    if (errors.length > 0) return null;
    return {
      timezone: form.timezone,
      schedule_type: form.mode === "interval" ? "interval" : form.recurrence_type === "once" ? "once" : "cron",
      recurrence_type: form.recurrence_type,
      time_of_day: form.time_of_day,
      weekdays: form.mode === "recurrence" && form.recurrence_type === "weekly" ? form.weekdays : null,
      day_of_month: form.mode === "recurrence" && form.recurrence_type === "monthly" ? form.day_of_month : null,
      specific_date: form.mode === "recurrence" && form.recurrence_type === "once" ? form.specific_date || null : null,
      interval_seconds: form.mode === "interval" ? form.interval_seconds : null,
      count: 5,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.timezone, form.mode, form.recurrence_type, form.time_of_day, form.weekdays, form.day_of_month, form.specific_date, form.interval_seconds, errors.length]);

  async function save() {
    if (!token) return;
    if (errors.length > 0) {
      setShowErrors(true);
      return;
    }
    setSubmitting(true);
    try {
      const payload = buildPayload(form);
      const saved = editing ? await updateSchedule(token, editing.id, payload) : await createSchedule(token, payload);
      toast({ title: editing ? "Agendamento atualizado" : "Agendamento criado", kind: "success" });
      await onSaved(saved);
      onClose();
    } catch (err) {
      toast({ title: "Falha ao salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={editingId ? "Editar agendamento" : "Novo agendamento"}
      widthClassName="w-full sm:max-w-2xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={save} disabled={submitting || (!!editingId && !editing)}>
            {submitting && <Spinner />} {editingId ? "Salvar" : "Criar"}
          </Button>
        </>
      }
    >
      {editingId && !editing ? (
        <div className="space-y-4">
          <Skeleton className="h-10 rounded-md" />
          <Skeleton className="h-24 rounded-md" />
          <Skeleton className="h-24 rounded-md" />
        </div>
      ) : (
      <div className="space-y-6">
        {showErrors && errors.length > 0 && (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
            <ul className="list-disc space-y-0.5 pl-4">
              {errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </div>
        )}

        <section className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">O que agendar</h3>
          <div className="grid grid-cols-2 gap-2">
            {(["automation", "flow"] as TargetType[]).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setForm((f) => ({ ...f, target_type: t }))}
                className={cn(
                  "rounded-md border p-2.5 text-center text-xs font-medium transition-colors",
                  form.target_type === t ? "border-primary bg-primary/5 text-primary" : "border-input text-muted-foreground hover:border-primary/50",
                )}
              >
                {t === "automation" ? "Automação" : "Fluxo"}
              </button>
            ))}
          </div>

          {form.target_type === "automation" ? (
            <Field>
              <Label htmlFor="s-automation">Automação</Label>
              <Select id="s-automation" value={form.automation_id} onChange={(e) => setForm({ ...form, automation_id: e.target.value })}>
                <option value="">Selecione...</option>
                {automations.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </Select>
            </Field>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field>
                <Label htmlFor="s-flow">Fluxo</Label>
                <Select id="s-flow" value={form.flow_id} onChange={(e) => setForm({ ...form, flow_id: e.target.value, flow_version_id: "" })}>
                  <option value="">Selecione...</option>
                  {flows.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field>
                <Label htmlFor="s-flow-version">Versão</Label>
                <Select
                  id="s-flow-version"
                  value={form.flow_version_id}
                  disabled={!form.flow_id}
                  onChange={(e) => setForm({ ...form, flow_version_id: e.target.value })}
                >
                  <option value="">{flowVersions.loading ? "Carregando..." : "Selecione..."}</option>
                  {flowVersions.data?.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.version} ({flowVersionStatusMeta(v.status).label})
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
          )}
        </section>

        <section className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Quando</h3>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setForm((f) => ({ ...f, mode: "recurrence" }))}
              className={cn(
                "rounded-md border p-2.5 text-center text-xs font-medium transition-colors",
                form.mode === "recurrence" ? "border-primary bg-primary/5 text-primary" : "border-input text-muted-foreground hover:border-primary/50",
              )}
            >
              Recorrência (horário fixo)
            </button>
            <button
              type="button"
              onClick={() => setForm((f) => ({ ...f, mode: "interval" }))}
              className={cn(
                "rounded-md border p-2.5 text-center text-xs font-medium transition-colors",
                form.mode === "interval" ? "border-primary bg-primary/5 text-primary" : "border-input text-muted-foreground hover:border-primary/50",
              )}
            >
              Intervalo (a cada N segundos)
            </button>
          </div>

          {form.mode === "interval" ? (
            <Field>
              <Label htmlFor="s-interval">Intervalo (segundos)</Label>
              <Input
                id="s-interval"
                type="number"
                min={60}
                className="tabular"
                value={form.interval_seconds}
                onChange={(e) => setForm({ ...form, interval_seconds: Number(e.target.value) })}
              />
              <p className="text-xs text-muted-foreground">
                Mínimo de 60 segundos. Agendamentos por intervalo não aparecem nas visões de calendário — gerencie-os pela Lista.
              </p>
            </Field>
          ) : (
            <>
              <div className="grid gap-2 sm:grid-cols-4">
                {RECURRENCE_TYPES.map((r) => (
                  <button
                    type="button"
                    key={r.value}
                    onClick={() => setForm({ ...form, recurrence_type: r.value })}
                    className={cn(
                      "rounded-md border p-2.5 text-center text-xs font-medium transition-colors",
                      form.recurrence_type === r.value ? "border-primary bg-primary/5 text-primary" : "border-input text-muted-foreground hover:border-primary/50",
                    )}
                  >
                    {r.label}
                  </button>
                ))}
              </div>

              {form.recurrence_type === "weekly" && (
                <Field>
                  <Label>Dias da semana</Label>
                  <div className="flex flex-wrap gap-1.5">
                    {WEEKDAY_BUTTON_LABELS.map((label, idx) => (
                      <button
                        type="button"
                        key={label}
                        onClick={() => toggleWeekday(idx)}
                        className={cn(
                          "h-9 w-11 rounded-md border text-xs font-medium transition-colors",
                          form.weekdays.includes(idx) ? "border-primary bg-primary/5 text-primary" : "border-input text-muted-foreground hover:border-primary/50",
                        )}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </Field>
              )}

              {form.recurrence_type === "monthly" && (
                <Field>
                  <Label htmlFor="s-day">Dia do mês</Label>
                  <Input
                    id="s-day"
                    type="number"
                    min={0}
                    max={31}
                    className="tabular"
                    value={form.day_of_month}
                    onChange={(e) => setForm({ ...form, day_of_month: Number(e.target.value) })}
                  />
                  <p className="text-xs text-muted-foreground">Use 0 para &quot;último dia do mês&quot; (aproximado como dia 28).</p>
                </Field>
              )}

              {form.recurrence_type === "once" && (
                <Field>
                  <Label htmlFor="s-date">Data</Label>
                  <Input id="s-date" type="date" className="tabular" value={form.specific_date} onChange={(e) => setForm({ ...form, specific_date: e.target.value })} />
                </Field>
              )}

              <Field>
                <Label htmlFor="s-time">Horário</Label>
                <Input id="s-time" type="time" className="tabular w-40" value={form.time_of_day} onChange={(e) => setForm({ ...form, time_of_day: e.target.value })} />
              </Field>
            </>
          )}
        </section>

        <ScheduleOccurrencesPreview payload={previewPayload} />

        <section className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Geral</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field>
              <Label htmlFor="s-name">Nome (opcional)</Label>
              <Input id="s-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Rótulo interno" />
            </Field>
            <Field>
              <Label htmlFor="s-timezone">Fuso horário</Label>
              <Input id="s-timezone" className="tabular" value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} />
            </Field>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} className="h-4 w-4 accent-primary" />
            Ativo
          </label>
        </section>

        <section className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Política de atraso (misfire)</h3>
          <div className="grid gap-2 sm:grid-cols-2">
            {MISFIRE_POLICY_OPTIONS.map((opt) => (
              <button
                type="button"
                key={opt.value}
                onClick={() => setForm({ ...form, misfire_policy: opt.value as MisfirePolicy })}
                className={cn(
                  "rounded-md border p-2.5 text-left text-xs transition-colors",
                  form.misfire_policy === opt.value ? "border-primary bg-primary/5" : "border-input hover:border-primary/50",
                )}
              >
                <span className="block font-medium text-foreground">{opt.label}</span>
                <span className="mt-0.5 block text-muted-foreground">{opt.description}</span>
              </button>
            ))}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field>
              <Label htmlFor="s-grace">Tolerância de atraso (segundos)</Label>
              <Input
                id="s-grace"
                type="number"
                min={0}
                className="tabular"
                value={form.misfire_grace_seconds}
                onChange={(e) => setForm({ ...form, misfire_grace_seconds: Number(e.target.value) })}
              />
            </Field>
            <Field>
              <Label htmlFor="s-catchup">Máx. execuções de recuperação</Label>
              <Input
                id="s-catchup"
                type="number"
                min={1}
                className="tabular"
                value={form.max_catch_up_runs}
                onChange={(e) => setForm({ ...form, max_catch_up_runs: Number(e.target.value) })}
              />
            </Field>
          </div>
        </section>

        <section className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Política de sobreposição</h3>
          <div className="grid gap-2 sm:grid-cols-2">
            {OVERLAP_POLICY_OPTIONS.map((opt) => (
              <button
                type="button"
                key={opt.value}
                onClick={() => setForm({ ...form, overlap_policy: opt.value as OverlapPolicy })}
                className={cn(
                  "rounded-md border p-2.5 text-left text-xs transition-colors",
                  form.overlap_policy === opt.value ? "border-primary bg-primary/5" : "border-input hover:border-primary/50",
                )}
              >
                <span className="block font-medium text-foreground">{opt.label}</span>
                <span className="mt-0.5 block text-muted-foreground">{opt.description}</span>
              </button>
            ))}
          </div>
        </section>
      </div>
      )}
    </Sheet>
  );
}
