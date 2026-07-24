"use client";

import type { FormEvent } from "react";
import { useState } from "react";
import { ArrowDown, ArrowUp, Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input, Select, Textarea, Label, Field } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { slugify, type AutomationConfigForm, type ExecutionMode } from "@/lib/automation-config";
import type { Category } from "@/types/category";
import type { RecurrenceType } from "@/types/schedule";
import type { Worker } from "@/types/worker";

export type AutomationFormState = AutomationConfigForm;

export const emptyAutomationForm: AutomationFormState = {
  name: "",
  slug: "",
  description: "",
  category_id: "",
  executor_type: "python_script",
  package_url: "",
  package_sha256: "",
  default_priority: "normal",
  timeout_seconds: 300,
  max_retries: 0,
  is_active: true,
  execution_mode: "manual",
  schedule_recurrence_type: "daily",
  schedule_time_of_day: "08:00",
  schedule_weekdays: [0, 1, 2, 3, 4],
  schedule_day_of_month: 1,
  schedule_specific_date: "",
  schedule_timezone: "America/Sao_Paulo",
  worker_ids: [],
};

const EXECUTORS = ["playwright", "power_automate", "n8n", "python_script", "http_request", "shell_command"];
const PRIORITIES = ["critical", "high", "normal", "low"];
const EXECUTION_MODES: { value: ExecutionMode; label: string; hint: string }[] = [
  { value: "manual", label: "Manual", hint: "Roda apenas quando alguém clicar em Disparar." },
  { value: "webhook", label: "Gatilho", hint: "Roda quando um sistema externo chamar a URL gerada." },
  { value: "scheduled", label: "Agendamento", hint: "Roda automaticamente numa recorrência (diária, semanal, mensal ou data única)." },
];

const RECURRENCE_TYPES: { value: RecurrenceType; label: string }[] = [
  { value: "daily", label: "Todo dia" },
  { value: "weekly", label: "Dias específicos da semana" },
  { value: "monthly", label: "Mensal" },
  { value: "once", label: "Data específica" },
];

const WEEKDAY_LABELS = [
  { value: 0, label: "Seg" },
  { value: 1, label: "Ter" },
  { value: 2, label: "Qua" },
  { value: 3, label: "Qui" },
  { value: 4, label: "Sex" },
  { value: 5, label: "Sáb" },
  { value: 6, label: "Dom" },
];

export function AutomationForm({
  categories,
  workers = [],
  onSubmit,
  submitting,
  initial,
  submitLabel = "Criar automação",
  webhookPreview,
}: {
  categories: Category[];
  workers?: Worker[];
  onSubmit: (form: AutomationFormState) => void | Promise<void>;
  submitting?: boolean;
  initial?: AutomationFormState;
  submitLabel?: string;
  /** URL do gatilho já existente (modo edição), exibida como referência. */
  webhookPreview?: string | null;
}) {
  const [form, setForm] = useState<AutomationFormState>(
    initial ?? {
      ...emptyAutomationForm,
      category_id: categories[0] ? String(categories[0].id) : "",
    },
  );

  function set<K extends keyof AutomationFormState>(key: K, value: AutomationFormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function toggleWorker(workerId: number) {
    setForm((f) => ({
      ...f,
      worker_ids: f.worker_ids.includes(workerId)
        ? f.worker_ids.filter((id) => id !== workerId)
        : [...f.worker_ids, workerId],
    }));
  }

  function toggleWeekday(day: number) {
    setForm((f) => ({
      ...f,
      schedule_weekdays: f.schedule_weekdays.includes(day)
        ? f.schedule_weekdays.filter((d) => d !== day)
        : [...f.schedule_weekdays, day].sort(),
    }));
  }

  function moveWorker(workerId: number, direction: -1 | 1) {
    setForm((f) => {
      const index = f.worker_ids.indexOf(workerId);
      const nextIndex = index + direction;
      if (index < 0 || nextIndex < 0 || nextIndex >= f.worker_ids.length) return f;
      const worker_ids = [...f.worker_ids];
      [worker_ids[index], worker_ids[nextIndex]] = [worker_ids[nextIndex], worker_ids[index]];
      return { ...f, worker_ids };
    });
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    void onSubmit(form);
  }

  return (
    <form id="automation-form" onSubmit={handleSubmit} className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field>
          <Label htmlFor="name">Nome</Label>
          <Input
            id="name"
            value={form.name}
            onChange={(e) => {
              set("name", e.target.value);
              if (!form.slug || form.slug === slugify(form.name)) set("slug", slugify(e.target.value));
            }}
            placeholder="Ex.: Conciliação bancária"
            required
          />
        </Field>
        <Field>
          <Label htmlFor="slug">Slug</Label>
          <Input id="slug" className="tabular" value={form.slug} onChange={(e) => set("slug", e.target.value)} required />
        </Field>
      </div>

      <Field>
        <Label htmlFor="description">Descrição</Label>
        <Textarea id="description" value={form.description} onChange={(e) => set("description", e.target.value)} />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field>
          <Label htmlFor="category">Categoria</Label>
          <Select id="category" value={form.category_id} onChange={(e) => set("category_id", e.target.value)} required>
            <option value="">Selecione...</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field>
          <Label htmlFor="executor">Executor</Label>
          <Select id="executor" value={form.executor_type} onChange={(e) => set("executor_type", e.target.value)}>
            {EXECUTORS.map((x) => (
              <option key={x} value={x}>
                {x}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <div className="flex items-start gap-2 rounded-md border border-info/30 bg-info/5 p-3 text-xs text-muted-foreground">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <p>
          O pacote executável vem da importação. Esta etapa define como a automação entra na fila, sua prioridade padrão
          e quais workers podem executá-la.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Field>
          <Label htmlFor="priority">Prioridade padrão</Label>
          <Select id="priority" value={form.default_priority} onChange={(e) => set("default_priority", e.target.value)}>
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </Select>
        </Field>
        <Field>
          <Label htmlFor="timeout">Timeout (s)</Label>
          <Input
            id="timeout"
            type="number"
            min={1}
            value={form.timeout_seconds}
            onChange={(e) => set("timeout_seconds", Number(e.target.value))}
          />
        </Field>
        <Field>
          <Label htmlFor="retries">Tentativas</Label>
          <Input
            id="retries"
            type="number"
            min={0}
            value={form.max_retries}
            onChange={(e) => set("max_retries", Number(e.target.value))}
          />
        </Field>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={form.is_active}
          onChange={(e) => set("is_active", e.target.checked)}
          className="h-4 w-4 rounded border-input accent-primary"
        />
        Ativa
      </label>

      <div className="space-y-3 border-t border-border pt-5">
        <Label>Gatilho</Label>
        <div className="grid gap-2 sm:grid-cols-3">
          {EXECUTION_MODES.map((mode) => (
            <button
              type="button"
              key={mode.value}
              onClick={() => set("execution_mode", mode.value)}
              className={`rounded-md border p-3 text-left text-sm transition-colors ${
                form.execution_mode === mode.value
                  ? "border-primary bg-primary/5"
                  : "border-input hover:border-primary/50"
              }`}
            >
              <p className="font-medium">{mode.label}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">{mode.hint}</p>
            </button>
          ))}
        </div>

        {form.execution_mode === "webhook" && webhookPreview && (
          <div className="flex items-start gap-2 rounded-md border border-info/30 bg-info/5 p-3 text-xs text-muted-foreground">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />
            <p>
              URL do gatilho atual: <span className="tabular font-medium text-foreground">{webhookPreview}</span>. Salvar
              aqui não altera a URL nem o token já gerados.
            </p>
          </div>
        )}
        {form.execution_mode === "webhook" && !webhookPreview && (
          <p className="text-xs text-muted-foreground">
            Uma URL de gatilho e um token de segurança serão gerados automaticamente ao salvar.
          </p>
        )}

        {form.execution_mode === "scheduled" && (
          <div className="space-y-4">
            <div className="grid gap-2 sm:grid-cols-4">
              {RECURRENCE_TYPES.map((r) => (
                <button
                  type="button"
                  key={r.value}
                  onClick={() => set("schedule_recurrence_type", r.value)}
                  className={`rounded-md border p-2.5 text-center text-xs font-medium transition-colors ${
                    form.schedule_recurrence_type === r.value
                      ? "border-primary bg-primary/5 text-primary"
                      : "border-input text-muted-foreground hover:border-primary/50"
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {form.schedule_recurrence_type === "weekly" && (
                <Field className="sm:col-span-2">
                  <Label>Dias da semana</Label>
                  <div className="flex flex-wrap gap-1.5">
                    {WEEKDAY_LABELS.map((d) => (
                      <button
                        type="button"
                        key={d.value}
                        onClick={() => toggleWeekday(d.value)}
                        className={`h-9 w-12 rounded-md border text-xs font-medium transition-colors ${
                          form.schedule_weekdays.includes(d.value)
                            ? "border-primary bg-primary/5 text-primary"
                            : "border-input text-muted-foreground hover:border-primary/50"
                        }`}
                      >
                        {d.label}
                      </button>
                    ))}
                  </div>
                  {form.schedule_weekdays.length === 0 && (
                    <p className="text-xs text-error">Selecione ao menos um dia.</p>
                  )}
                </Field>
              )}

              {form.schedule_recurrence_type === "monthly" && (
                <Field>
                  <Label htmlFor="day-of-month">Dia do mês</Label>
                  <Input
                    id="day-of-month"
                    type="number"
                    min={0}
                    max={31}
                    className="tabular"
                    value={form.schedule_day_of_month}
                    onChange={(e) => set("schedule_day_of_month", Number(e.target.value))}
                    required={form.schedule_recurrence_type === "monthly"}
                  />
                  <p className="text-xs text-muted-foreground">Use 0 para "último dia do mês" (aproximado como dia 28).</p>
                </Field>
              )}

              {form.schedule_recurrence_type === "once" && (
                <Field>
                  <Label htmlFor="specific-date">Data</Label>
                  <Input
                    id="specific-date"
                    type="date"
                    className="tabular"
                    value={form.schedule_specific_date}
                    onChange={(e) => set("schedule_specific_date", e.target.value)}
                    required={form.schedule_recurrence_type === "once"}
                  />
                </Field>
              )}

              <Field>
                <Label htmlFor="time-of-day">Horário</Label>
                <Input
                  id="time-of-day"
                  type="time"
                  className="tabular"
                  value={form.schedule_time_of_day}
                  onChange={(e) => set("schedule_time_of_day", e.target.value)}
                  required={form.execution_mode === "scheduled"}
                />
              </Field>
              <Field>
                <Label htmlFor="tz">Fuso horário</Label>
                <Input
                  id="tz"
                  className="tabular"
                  value={form.schedule_timezone}
                  onChange={(e) => set("schedule_timezone", e.target.value)}
                  placeholder="America/Sao_Paulo"
                  required={form.execution_mode === "scheduled"}
                />
              </Field>
            </div>
          </div>
        )}
      </div>

      <div className="space-y-3 border-t border-border pt-5">
        <Label>Workers por prioridade</Label>
        <p className="text-xs text-muted-foreground">
          Deixe tudo desmarcado para permitir qualquer worker compatível. Se marcar algum, o dispatcher usa apenas os
          selecionados, respeitando a prioridade configurada aqui.
        </p>
        {workers.length === 0 ? (
          <p className="rounded-md border border-dashed border-border py-4 text-center text-xs text-muted-foreground">
            Nenhum worker cadastrado ainda.
          </p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            {workers.map((w) => {
              const priorityIndex = form.worker_ids.indexOf(w.id);
              const selected = priorityIndex >= 0;
              return (
                <div
                  key={w.id}
                  className={`flex min-h-14 items-center gap-2 rounded-md border p-2.5 text-sm ${
                    selected ? "border-primary bg-primary/5" : "border-input hover:border-primary/50"
                  }`}
                >
                  <input
                    id={`worker-${w.id}`}
                    type="checkbox"
                    checked={selected}
                    onChange={() => toggleWorker(w.id)}
                    className="h-4 w-4 rounded border-input accent-primary"
                  />
                  <label htmlFor={`worker-${w.id}`} className="min-w-0 flex-1 cursor-pointer">
                    <span className="block truncate font-medium">{w.name}</span>
                    <span className="tabular block truncate text-xs text-muted-foreground">{w.hostname}</span>
                  </label>
                  {selected && (
                    <div className="flex items-center gap-1">
                      <span className="tabular rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                        #{priorityIndex + 1}
                      </span>
                      <button
                        type="button"
                        aria-label={`Aumentar prioridade de ${w.name}`}
                        onClick={() => moveWorker(w.id, -1)}
                        disabled={priorityIndex === 0}
                        className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
                      >
                        <ArrowUp className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        aria-label={`Diminuir prioridade de ${w.name}`}
                        onClick={() => moveWorker(w.id, 1)}
                        disabled={priorityIndex === form.worker_ids.length - 1}
                        className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
                      >
                        <ArrowDown className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="flex justify-end">
        <Button type="submit" disabled={submitting || !form.category_id}>
          {submitting && <Spinner />} {submitLabel}
        </Button>
      </div>
    </form>
  );
}
