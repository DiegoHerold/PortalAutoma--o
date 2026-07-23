"use client";

import type { FormEvent } from "react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, Select, Textarea, Label, Field } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import type { Category } from "@/types/category";

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
};

const EXECUTORS = ["playwright", "power_automate", "n8n", "python_script", "http_request", "shell_command"];
const PRIORITIES = ["critical", "high", "normal", "low"];

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
  onSubmit,
  submitting,
  initial,
  submitLabel = "Criar automacao",
}: {
  categories: Category[];
  onSubmit: (form: AutomationFormState) => void | Promise<void>;
  submitting?: boolean;
  initial?: AutomationFormState;
  submitLabel?: string;
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

      <div className="grid gap-4 sm:grid-cols-2">
        <Field>
          <Label htmlFor="package-url">URL do pacote</Label>
          <Input
            id="package-url"
            value={form.package_url}
            onChange={(e) => set("package_url", e.target.value)}
            placeholder="https://servidor/pacotes/minha-automacao.zip"
          />
        </Field>
        <Field>
          <Label htmlFor="package-sha">SHA-256</Label>
          <Input
            id="package-sha"
            className="tabular"
            value={form.package_sha256}
            onChange={(e) => set("package_sha256", e.target.value)}
            placeholder="sha256 opcional"
          />
        </Field>
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

      <div className="flex justify-end">
        <Button type="submit" disabled={submitting}>
          {submitting && <Spinner />} {submitLabel}
        </Button>
      </div>
    </form>
  );
}
