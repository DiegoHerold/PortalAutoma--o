"use client";

import { useMemo, useState } from "react";
import { CalendarClock, ChevronLeft, ChevronRight, Plus, Trash2 } from "lucide-react";

import { ErrorState } from "@/components/shared/error-state";
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
import { addMonths, getMonthGridDays, isSameDay, monthLabel, toDateKey, WEEKDAY_HEADER_LABELS } from "@/lib/calendar";
import { describeRecurrence } from "@/lib/cron";
import { occurrenceStatusMeta } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { Automation } from "@/types/automation";
import type { RecurrenceType, Schedule, ScheduleOccurrence } from "@/types/schedule";

type ScheduleFormState = {
  automation_id: string;
  recurrence_type: RecurrenceType;
  time_of_day: string;
  weekdays: number[];
  day_of_month: number;
  specific_date: string;
  timezone: string;
  is_active: boolean;
};

const RECURRENCE_TYPES: { value: RecurrenceType; label: string }[] = [
  { value: "daily", label: "Todo dia" },
  { value: "weekly", label: "Dias da semana" },
  { value: "monthly", label: "Mensal" },
  { value: "once", label: "Data específica" },
];

function emptyForm(automationId?: string, specificDate?: string): ScheduleFormState {
  return {
    automation_id: automationId ?? "",
    recurrence_type: specificDate ? "once" : "daily",
    time_of_day: "08:00",
    weekdays: [0, 1, 2, 3, 4],
    day_of_month: 1,
    specific_date: specificDate ?? "",
    timezone: "America/Sao_Paulo",
    is_active: true,
  };
}

function scheduleToForm(schedule: Schedule): ScheduleFormState {
  return {
    automation_id: schedule.automation_id == null ? "" : String(schedule.automation_id),
    recurrence_type: schedule.recurrence_type,
    time_of_day: schedule.time_of_day,
    weekdays: schedule.weekdays ?? [0, 1, 2, 3, 4],
    day_of_month: schedule.day_of_month ?? 1,
    specific_date: schedule.specific_date ?? "",
    timezone: schedule.timezone,
    is_active: schedule.is_active,
  };
}

export function SchedulesManager() {
  const { token } = useAuth();
  const { toast } = useToast();
  const automations = useApi<Automation[]>("/automations");
  const schedules = useApi<Schedule[]>("/schedules");

  const [viewMonth, setViewMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [filterAutomationId, setFilterAutomationId] = useState("");
  const [filterStatus, setFilterStatus] = useState("");

  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [editing, setEditing] = useState<Schedule | null>(null);
  const [occurrenceContext, setOccurrenceContext] = useState<ScheduleOccurrence | null>(null);
  const [form, setForm] = useState<ScheduleFormState>(emptyForm());

  const gridDays = useMemo(() => getMonthGridDays(viewMonth), [viewMonth]);
  const rangeFrom = toDateKey(gridDays[0].date);
  const rangeTo = toDateKey(gridDays[gridDays.length - 1].date);

  const occurrences = useApi<ScheduleOccurrence[]>(`/schedules/calendar?from_date=${rangeFrom}&to_date=${rangeTo}`);

  const nameOf = useMemo(() => {
    const map = new Map<number, string>();
    automations.data?.forEach((a) => map.set(a.id, a.name));
    return map;
  }, [automations.data]);

  const filteredOccurrences = useMemo(() => {
    let list = occurrences.data ?? [];
    if (filterAutomationId) list = list.filter((o) => String(o.automation_id) === filterAutomationId);
    if (filterStatus) list = list.filter((o) => o.status === filterStatus);
    return list;
  }, [occurrences.data, filterAutomationId, filterStatus]);

  const occurrencesByDay = useMemo(() => {
    const map = new Map<string, ScheduleOccurrence[]>();
    for (const o of filteredOccurrences) {
      const key = toDateKey(new Date(o.occurs_at));
      const bucket = map.get(key) ?? [];
      bucket.push(o);
      map.set(key, bucket);
    }
    for (const bucket of map.values()) bucket.sort((a, b) => a.occurs_at.localeCompare(b.occurs_at));
    return map;
  }, [filteredOccurrences]);

  const runningCount = useMemo(() => (occurrences.data ?? []).filter((o) => o.status === "running").length, [occurrences.data]);

  function openCreate(specificDate?: string) {
    setEditing(null);
    setOccurrenceContext(null);
    setForm(emptyForm(automations.data?.[0] ? String(automations.data[0].id) : "", specificDate));
    setOpen(true);
  }

  function openEdit(schedule: Schedule, occurrence?: ScheduleOccurrence) {
    setEditing(schedule);
    setOccurrenceContext(occurrence ?? null);
    setForm(scheduleToForm(schedule));
    setOpen(true);
  }

  function openOccurrence(occurrence: ScheduleOccurrence) {
    const schedule = schedules.data?.find((s) => s.id === occurrence.schedule_id);
    if (!schedule) {
      toast({ title: "Agendamento não encontrado", kind: "error" });
      return;
    }
    openEdit(schedule, occurrence);
  }

  function toggleWeekday(day: number) {
    setForm((f) => ({
      ...f,
      weekdays: f.weekdays.includes(day) ? f.weekdays.filter((d) => d !== day) : [...f.weekdays, day].sort(),
    }));
  }

  async function save() {
    if (!token || !form.automation_id) return;
    setSubmitting(true);
    try {
      const body = JSON.stringify({
        automation_id: Number(form.automation_id),
        timezone: form.timezone,
        is_active: form.is_active,
        recurrence_type: form.recurrence_type,
        time_of_day: form.time_of_day,
        weekdays: form.recurrence_type === "weekly" ? form.weekdays : null,
        day_of_month: form.recurrence_type === "monthly" ? form.day_of_month : null,
        specific_date: form.recurrence_type === "once" ? form.specific_date : null,
      });
      await apiRequest<Schedule>(editing ? `/schedules/${editing.id}` : "/schedules", {
        method: editing ? "PUT" : "POST",
        token,
        body,
      });
      toast({ title: editing ? "Agendamento atualizado" : "Agendamento criado", kind: "success" });
      setOpen(false);
      setEditing(null);
      setOccurrenceContext(null);
      await Promise.all([schedules.refetch(), occurrences.refetch()]);
    } catch (err) {
      toast({ title: "Falha ao salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(schedule: Schedule) {
    if (!token) return;
    const label = schedule.automation_id == null ? schedule.name ?? `#${schedule.id}` : nameOf.get(schedule.automation_id) ?? schedule.automation_id;
    if (!window.confirm(`Apagar o agendamento de "${label}"?`)) return;
    try {
      await apiRequest<void>(`/schedules/${schedule.id}`, { method: "DELETE", token });
      toast({ title: "Agendamento apagado", kind: "success" });
      setOpen(false);
      setEditing(null);
      setOccurrenceContext(null);
      await Promise.all([schedules.refetch(), occurrences.refetch()]);
    } catch (err) {
      toast({ title: "Falha ao apagar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  if (schedules.error) return <ErrorState message={schedules.error} onRetry={schedules.refetch} />;
  if (automations.error) return <ErrorState message={automations.error} onRetry={automations.refetch} />;

  const today = new Date();
  const loadingGrid = schedules.loading || occurrences.loading;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <Button size="icon" variant="outline" onClick={() => setViewMonth((m) => addMonths(m, -1))} aria-label="Mês anterior">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <h2 className="w-44 text-center font-display text-base font-semibold capitalize">{monthLabel(viewMonth)}</h2>
          <Button size="icon" variant="outline" onClick={() => setViewMonth((m) => addMonths(m, 1))} aria-label="Próximo mês">
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setViewMonth(new Date(today.getFullYear(), today.getMonth(), 1))}
          >
            Hoje
          </Button>
          {runningCount > 0 && (
            <Badge tone="info" className="animate-pulse">
              {runningCount} rodando agora
            </Badge>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select value={filterAutomationId} onChange={(e) => setFilterAutomationId(e.target.value)} className="w-48">
            <option value="">Todas as automações</option>
            {automations.data?.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </Select>
          <Select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="w-40">
            <option value="">Todos os status</option>
            <option value="upcoming">Agendado</option>
            <option value="running">Executando</option>
            <option value="success">Sucesso</option>
            <option value="failed">Falha</option>
            <option value="missed">Não executado</option>
          </Select>
          <Button onClick={() => openCreate()}>
            <Plus className="h-4 w-4" /> Novo agendamento
          </Button>
        </div>
      </div>

      {loadingGrid ? (
        <Skeleton className="h-[560px] rounded-lg" />
      ) : (occurrences.error && !occurrences.data) ? (
        <ErrorState message={occurrences.error} onRetry={occurrences.refetch} />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <div className="grid grid-cols-7 border-b border-border bg-muted/40 text-xs font-medium text-muted-foreground">
            {WEEKDAY_HEADER_LABELS.map((label) => (
              <div key={label} className="px-2 py-2 text-center">
                {label}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7">
            {gridDays.map(({ date, inMonth }) => {
              const key = toDateKey(date);
              const dayOccurrences = occurrencesByDay.get(key) ?? [];
              const isToday = isSameDay(date, today);
              const visible = dayOccurrences.slice(0, 3);
              const overflow = dayOccurrences.length - visible.length;

              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => openCreate(key)}
                  className={cn(
                    "flex min-h-[104px] flex-col items-stretch gap-1 border-b border-r border-border p-1.5 text-left transition-colors hover:bg-accent/40",
                    !inMonth && "bg-muted/20 text-muted-foreground",
                  )}
                >
                  <span
                    className={cn(
                      "self-start rounded-full px-1.5 text-xs font-medium",
                      isToday ? "bg-primary text-primary-foreground" : "text-muted-foreground",
                    )}
                  >
                    {date.getDate()}
                  </span>
                  <div className="flex flex-1 flex-col gap-1 overflow-hidden">
                    {visible.map((o) => {
                      const meta = occurrenceStatusMeta(o.status);
                      const time = new Date(o.occurs_at).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
                      return (
                        <span
                          key={`${o.schedule_id}-${o.occurs_at}`}
                          role="button"
                          tabIndex={0}
                          onClick={(e) => {
                            e.stopPropagation();
                            openOccurrence(o);
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.stopPropagation();
                              openOccurrence(o);
                            }
                          }}
                          className={cn(
                            "flex items-center gap-1 truncate rounded px-1 py-0.5 text-[11px] font-medium",
                            meta.tone === "success" && "bg-success/12 text-success",
                            meta.tone === "destructive" && "bg-destructive/12 text-destructive",
                            meta.tone === "info" && "bg-info/12 text-info",
                            meta.tone === "warning" && "bg-warning/15 text-warning",
                            (meta.tone === "neutral" || meta.tone === "outline") && "bg-muted text-muted-foreground",
                          )}
                          title={`${nameOf.get(o.automation_id) ?? o.automation_id} — ${meta.label}`}
                        >
                          <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", meta.dot)} />
                          <span className="truncate">
                            {time} {nameOf.get(o.automation_id) ?? `#${o.automation_id}`}
                          </span>
                        </span>
                      );
                    })}
                    {overflow > 0 && <span className="px-1 text-[11px] text-muted-foreground">+{overflow} mais</span>}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {(schedules.data ?? []).length === 0 && !schedules.loading && (
        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          <CalendarClock className="h-3.5 w-3.5" /> Nenhum agendamento cadastrado ainda -- clique em um dia do calendário ou em
          &quot;Novo agendamento&quot;.
        </p>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? "Editar agendamento" : "Novo agendamento"}
        description={editing ? describeRecurrence(editing) : undefined}
        footer={
          <>
            {editing && (
              <Button variant="destructive" className="mr-auto" onClick={() => remove(editing)}>
                <Trash2 className="h-4 w-4" /> Apagar
              </Button>
            )}
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={save} disabled={submitting || !form.automation_id || (form.recurrence_type === "weekly" && form.weekdays.length === 0)}>
              {submitting && <Spinner />} {editing ? "Salvar" : "Criar"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {occurrenceContext && (
            <div className="rounded-md border border-info/30 bg-info/5 p-3 text-xs text-muted-foreground">
              Ocorrência de{" "}
              {new Date(occurrenceContext.occurs_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}:{" "}
              <Badge tone={occurrenceStatusMeta(occurrenceContext.status).tone}>{occurrenceStatusMeta(occurrenceContext.status).label}</Badge>
              {occurrenceContext.job_id && <span className="ml-1">(job #{occurrenceContext.job_id})</span>}
            </div>
          )}

          <Field>
            <Label htmlFor="s-automation">Automação</Label>
            <Select id="s-automation" value={form.automation_id} onChange={(e) => setForm({ ...form, automation_id: e.target.value })}>
              <option value="">Selecione...</option>
              {automations.data?.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </Select>
          </Field>

          <div className="grid gap-2 sm:grid-cols-4">
            {RECURRENCE_TYPES.map((r) => (
              <button
                type="button"
                key={r.value}
                onClick={() => setForm({ ...form, recurrence_type: r.value })}
                className={cn(
                  "rounded-md border p-2.5 text-center text-xs font-medium transition-colors",
                  form.recurrence_type === r.value
                    ? "border-primary bg-primary/5 text-primary"
                    : "border-input text-muted-foreground hover:border-primary/50",
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
                {["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"].map((label, idx) => (
                  <button
                    type="button"
                    key={label}
                    onClick={() => toggleWeekday(idx)}
                    className={cn(
                      "h-9 w-11 rounded-md border text-xs font-medium transition-colors",
                      form.weekdays.includes(idx)
                        ? "border-primary bg-primary/5 text-primary"
                        : "border-input text-muted-foreground hover:border-primary/50",
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {form.weekdays.length === 0 && <p className="text-xs text-error">Selecione ao menos um dia.</p>}
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
              <Input
                id="s-date"
                type="date"
                className="tabular"
                value={form.specific_date}
                onChange={(e) => setForm({ ...form, specific_date: e.target.value })}
              />
            </Field>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <Field>
              <Label htmlFor="s-time">Horário</Label>
              <Input
                id="s-time"
                type="time"
                className="tabular"
                value={form.time_of_day}
                onChange={(e) => setForm({ ...form, time_of_day: e.target.value })}
              />
            </Field>
            <Field>
              <Label htmlFor="s-timezone">Fuso horário</Label>
              <Input
                id="s-timezone"
                className="tabular"
                value={form.timezone}
                onChange={(e) => setForm({ ...form, timezone: e.target.value })}
              />
            </Field>
          </div>

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
