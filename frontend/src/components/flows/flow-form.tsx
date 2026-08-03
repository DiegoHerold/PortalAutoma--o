"use client";

import { useState } from "react";
import type { FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input, Label, Select, Textarea } from "@/components/ui/input";
import type { Category } from "@/types/category";
import type { Flow } from "@/types/flow";

export type FlowFormState = {
  key: string;
  name: string;
  description: string;
  category_id: string;
  tags: string;
};

export function emptyFlowForm(): FlowFormState {
  return { key: "", name: "", description: "", category_id: "", tags: "" };
}

export function flowToForm(flow: Flow): FlowFormState {
  return {
    key: flow.key,
    name: flow.name,
    description: flow.description ?? "",
    category_id: flow.category_id ? String(flow.category_id) : "",
    tags: flow.tags.join(", "),
  };
}

export function FlowForm({
  categories,
  initial,
  submitting,
  submitLabel,
  lockKey,
  onSubmit,
}: {
  categories: Category[];
  initial?: FlowFormState;
  submitting: boolean;
  submitLabel: string;
  /** true ao editar um Flow existente — a key não pode mudar depois de criada. */
  lockKey?: boolean;
  onSubmit: (form: FlowFormState) => void;
}) {
  const [form, setForm] = useState<FlowFormState>(initial ?? emptyFlowForm());
  const [keyTouched, setKeyTouched] = useState(Boolean(initial?.key));

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onSubmit(form);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="rounded-lg border border-border bg-muted/20 p-4">
        <div className="mb-4">
          <p className="text-sm font-semibold">Identidade do fluxo</p>
          <p className="mt-1 text-xs text-muted-foreground">Defina um nome claro. A key é criada automaticamente e pode ser ajustada antes de salvar.</p>
        </div>
        <div className="space-y-4">
          <Field>
            <Label htmlFor="flow-name">Nome</Label>
            <Input
              id="flow-name"
              required
              autoFocus={!lockKey}
              placeholder="Ex.: Fechamento financeiro mensal"
              value={form.name}
              onChange={(e) => {
                const name = e.target.value;
                setForm((prev) => ({
                  ...prev,
                  name,
                  key: lockKey || keyTouched ? prev.key : slugify(name),
                }));
              }}
            />
          </Field>

          <Field>
            <Label htmlFor="flow-key">Key</Label>
            <Input
              id="flow-key"
              required
              disabled={lockKey}
              placeholder="fechamento_financeiro_mensal"
              value={form.key}
              onChange={(e) => {
                setKeyTouched(true);
                setForm((prev) => ({ ...prev, key: slugify(e.target.value) }));
              }}
            />
            <p className="text-xs text-muted-foreground">Identificador único para integrações. Depois de criado, ele fica fixo.</p>
          </Field>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field className="sm:col-span-2">
          <Label htmlFor="flow-description">Descrição</Label>
          <Textarea
            id="flow-description"
            rows={3}
            placeholder="Qual processo este fluxo coordena?"
            value={form.description}
            onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
          />
        </Field>

        <Field>
          <Label htmlFor="flow-category">Categoria</Label>
          <Select id="flow-category" value={form.category_id} onChange={(e) => setForm((prev) => ({ ...prev, category_id: e.target.value }))}>
            <option value="">Sem categoria</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </Field>

        <Field>
          <Label htmlFor="flow-tags">Tags</Label>
          <Input
            id="flow-tags"
            placeholder="financeiro, mensal, crítico"
            value={form.tags}
            onChange={(e) => setForm((prev) => ({ ...prev, tags: e.target.value }))}
          />
          <p className="text-xs text-muted-foreground">Separe por vírgula.</p>
        </Field>
      </div>

      <div className="flex justify-end border-t border-border pt-4">
        <Button type="submit" disabled={submitting || !form.name || !form.key}>
          {submitting ? "Salvando..." : submitLabel}
        </Button>
      </div>
    </form>
  );
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 60);
}

export function parseTags(raw: string): string[] {
  return raw
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
}
