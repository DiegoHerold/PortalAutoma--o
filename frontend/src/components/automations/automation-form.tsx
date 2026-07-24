"use client";

import type { FormEvent } from "react";
import { useState } from "react";
import { Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input, Select, Textarea, Label, Field } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import type { Category } from "@/types/category";
import type { Worker } from "@/types/worker";

export type ExecutionMode = "manual" | "webhook" | "scheduled";

export type AutomationFormState = {
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
  // Disparo: como a automação é iniciada. "manual" = só pelo botão Disparar;
  // "webhook" = via gatilho HTTP; "scheduled" = via agendamento (cron).
  execution_mode: ExecutionMode;
  schedule_cron: string;
  schedule_timezone: string;
  // Computadores (workers) autorizados a rodar esta automação, em ordem de
  // preferência. Vazio = qualquer worker compatível pode pegar o job.
  worker_ids: number[];
};

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
  schedule_cron: "0 8 * * 1-5",
  schedule_timezone: "America/Sao_Paulo",
  worker_ids: [],
};

const EXECUTORS = ["playwright", "power_automate", "n8n", "python_script", "http_request", "shell_command"];
const PRIORITIES = ["critical", "high", "normal", "low"];
const EXECUTION_MODES: { value: ExecutionMode; label: string; hint: string }[] = [
  { value: "manual", label: "Manual", hint: "Só roda quando alguém clicar em \"Disparar\"." },
  { value: "webhook", label: "Gatilho (webhook)", hint: "Roda quando um sistema externo chamar a URL do gatilho." },
  { value: "scheduled", label: "Agendado", hint: "Roda automaticamente seguindo uma expressão cron." },
];

function slugify(value: string) {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function AutomationForm({
  categories,
  workers = [],
  onSubmit,
  submitting,
  initial,
  submitLabel = "Criar automacao",
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
            placeholder="Ex.: Conciliacao bancaria"
            required
          />
        </Field>
        <Field>
          <Label htmlFor="slug">Slug</Label>
          <Input id="slug" className="tabular" value={form.slug} onChange={(e) => set("slug", e.target.value)} required />
        </Field>
      </div>

      <Field>
        <Label htmlFor="description">Descricao</Label>
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
          O pacote executável desta automação vem da importação (GitHub ou ZIP), na seção &quot;Versões&quot; da página
          da automação — não é definido aqui.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Field>
          <Label htmlFor="priority">Prioridade padrao</Label>
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
          <Label htmlFor="retries">Max. retries</Label>
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
        <Label>Como esta automação é disparada</Label>
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
          <div className="grid gap-4 sm:grid-cols-2">
            <Field>
              <Label htmlFor="cron">Expressão cron</Label>
              <Input
                id="cron"
                className="tabular"
                value={form.schedule_cron}
                onChange={(e) => set("schedule_cron", e.target.value)}
                placeholder="0 8 * * 1-5"
                required={form.execution_mode === "scheduled"}
              />
              <p className="text-xs text-muted-foreground">Ex.: &quot;0 8 * * 1-5&quot; = todo dia útil às 8h.</p>
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
        )}
      </div>

      <div className="space-y-3 border-t border-border pt-5">
        <Label>Computadores autorizados a rodar</Label>
        <p className="text-xs text-muted-foreground">
          Deixe tudo desmarcado para permitir qualquer worker compatível. Se marcar algum, o dispatcher só usa os
          selecionados (pela ordem em que aparecem aqui).
        </p>
        {workers.length === 0 ? (
          <p className="rounded-md border border-dashed border-border py-4 text-center text-xs text-muted-foreground">
            Nenhum worker cadastrado ainda.
          </p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            {workers.map((w) => (
              <label
                key={w.id}
                className="flex items-center gap-2 rounded-md border border-input p-2.5 text-sm hover:border-primary/50"
              >
                <input
                  type="checkbox"
                  checked={form.worker_ids.includes(w.id)}
                  onChange={() => toggleWorker(w.id)}
                  className="h-4 w-4 rounded border-input accent-primary"
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{w.name}</span>
                  <span className="tabular block truncate text-xs text-muted-foreground">{w.hostname}</span>
                </span>
              </label>
            ))}
          </div>
        )}
      </div>

      <div className="flex justify-end">
        <Button type="submit" disabled={submitting}>
          {submitting && <Spinner />} {submitLabel}
        </Button>
      </div>
    </form>
  );
}
