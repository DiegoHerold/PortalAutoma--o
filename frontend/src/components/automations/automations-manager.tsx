"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import { AutomationCard } from "@/components/automations/automation-card";
import { LoadingState } from "@/components/shared/loading-state";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type { Automation } from "@/types/automation";
import type { Category } from "@/types/category";

type AutomationFormState = {
  name: string;
  slug: string;
  description: string;
  category_id: string;
  executor_type: string;
  default_priority: string;
  timeout_seconds: number;
  max_retries: number;
  is_active: boolean;
};

const initialForm: AutomationFormState = {
  name: "",
  slug: "",
  description: "",
  category_id: "",
  executor_type: "python_script",
  default_priority: "normal",
  timeout_seconds: 300,
  max_retries: 0,
  is_active: true,
};

export function AutomationsManager() {
  const { token } = useAuth();
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [form, setForm] = useState<AutomationFormState>(initialForm);
  const [loading, setLoading] = useState(true);

  async function load() {
    if (!token) return;
    setLoading(true);
    const [automationData, categoryData] = await Promise.all([
      apiRequest<Automation[]>("/automations", { token }),
      apiRequest<Category[]>("/categories", { token }),
    ]);
    setAutomations(automationData);
    setCategories(categoryData);
    if (!form.category_id && categoryData[0]) {
      setForm((current) => ({ ...current, category_id: String(categoryData[0].id) }));
    }
    setLoading(false);
  }

  useEffect(() => {
    void load();
  }, [token]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    await apiRequest<Automation>("/automations", {
      method: "POST",
      token,
      body: JSON.stringify({
        ...form,
        category_id: Number(form.category_id),
      }),
    });
    setForm(initialForm);
    await load();
  }

  if (loading) return <LoadingState label="Carregando automacoes..." />;

  return (
    <div className="space-y-6">
      <form className="grid gap-3 rounded-3xl bg-white/80 p-6 shadow-sm md:grid-cols-2" onSubmit={handleSubmit}>
        <input className="rounded-2xl border border-slate-200 px-4 py-3" placeholder="Nome" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        <input className="rounded-2xl border border-slate-200 px-4 py-3" placeholder="Slug" value={form.slug} onChange={(event) => setForm({ ...form, slug: event.target.value })} />
        <input className="rounded-2xl border border-slate-200 px-4 py-3 md:col-span-2" placeholder="Descricao" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
        <select className="rounded-2xl border border-slate-200 px-4 py-3" value={form.category_id} onChange={(event) => setForm({ ...form, category_id: event.target.value })}>
          <option value="">Selecione uma categoria</option>
          {categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </select>
        <select className="rounded-2xl border border-slate-200 px-4 py-3" value={form.executor_type} onChange={(event) => setForm({ ...form, executor_type: event.target.value })}>
          {["playwright", "power_automate", "n8n", "python_script", "http_request", "shell_command"].map((executorType) => (
            <option key={executorType} value={executorType}>
              {executorType}
            </option>
          ))}
        </select>
        <button className="rounded-2xl bg-ink px-4 py-3 text-sm font-semibold text-white md:col-span-2" type="submit">
          Criar automacao
        </button>
      </form>
      <div className="grid gap-4 md:grid-cols-2">
        {automations.map((automation) => (
          <AutomationCard key={automation.id} automation={automation} />
        ))}
      </div>
    </div>
  );
}
