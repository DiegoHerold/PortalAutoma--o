"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import { LoadingState } from "@/components/shared/loading-state";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type { Category } from "@/types/category";

type CategoryFormState = {
  name: string;
  slug: string;
  description: string;
  is_active: boolean;
};

const initialForm: CategoryFormState = {
  name: "",
  slug: "",
  description: "",
  is_active: true,
};

export function CategoriesManager() {
  const { token } = useAuth();
  const [categories, setCategories] = useState<Category[]>([]);
  const [form, setForm] = useState<CategoryFormState>(initialForm);
  const [loading, setLoading] = useState(true);

  async function load() {
    if (!token) return;
    setLoading(true);
    const data = await apiRequest<Category[]>("/categories", { token });
    setCategories(data);
    setLoading(false);
  }

  useEffect(() => {
    void load();
  }, [token]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    await apiRequest<Category>("/categories", {
      method: "POST",
      token,
      body: JSON.stringify(form),
    });
    setForm(initialForm);
    await load();
  }

  if (loading) return <LoadingState label="Carregando categorias..." />;

  return (
    <div className="space-y-6">
      <form className="grid gap-3 rounded-3xl bg-white/80 p-6 shadow-sm md:grid-cols-2" onSubmit={handleSubmit}>
        <input className="rounded-2xl border border-slate-200 px-4 py-3" placeholder="Nome" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        <input className="rounded-2xl border border-slate-200 px-4 py-3" placeholder="Slug" value={form.slug} onChange={(event) => setForm({ ...form, slug: event.target.value })} />
        <input className="rounded-2xl border border-slate-200 px-4 py-3 md:col-span-2" placeholder="Descricao" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} />
          Categoria ativa
        </label>
        <button className="rounded-2xl bg-ink px-4 py-3 text-sm font-semibold text-white" type="submit">
          Criar categoria
        </button>
      </form>
      <div className="grid gap-4 md:grid-cols-2">
        {categories.map((category) => (
          <div key={category.id} className="rounded-3xl bg-white/80 p-5 shadow-sm">
            <h3 className="text-lg font-semibold">{category.name}</h3>
            <p className="mt-1 text-sm text-slate-500">{category.slug}</p>
            <p className="mt-3 text-sm text-slate-600">{category.description ?? "Sem descricao."}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
