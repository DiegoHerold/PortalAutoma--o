"use client";

import { useState } from "react";
import { FolderTree, Pencil, Plus, Trash2 } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Textarea, Label, Field } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type { Category } from "@/types/category";

const emptyForm = { name: "", slug: "", description: "", is_active: true };

export function CategoriesManager() {
  const { token } = useAuth();
  const { toast } = useToast();
  const categories = useApi<Category[]>("/categories");
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [editing, setEditing] = useState<Category | null>(null);
  const [form, setForm] = useState(emptyForm);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setOpen(true);
  }

  function openEdit(category: Category) {
    setEditing(category);
    setForm({
      name: category.name,
      slug: category.slug,
      description: category.description ?? "",
      is_active: category.is_active,
    });
    setOpen(true);
  }

  async function save() {
    if (!token) return;
    setSubmitting(true);
    try {
      await apiRequest<Category>(editing ? `/categories/${editing.id}` : "/categories", {
        method: editing ? "PUT" : "POST",
        token,
        body: JSON.stringify(form),
      });
      toast({ title: editing ? "Categoria atualizada" : "Categoria criada", kind: "success" });
      setForm(emptyForm);
      setEditing(null);
      setOpen(false);
      await categories.refetch();
    } catch (err) {
      toast({ title: "Falha ao salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(category: Category) {
    if (!token) return;
    if (!window.confirm(`Apagar a categoria "${category.name}"?`)) return;
    try {
      await apiRequest<void>(`/categories/${category.id}`, { method: "DELETE", token });
      toast({ title: "Categoria apagada", kind: "success" });
      await categories.refetch();
    } catch (err) {
      toast({ title: "Falha ao apagar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" /> Nova categoria
        </Button>
      </div>

      {categories.error ? (
        <ErrorState message={categories.error} onRetry={categories.refetch} />
      ) : categories.loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-32 rounded-lg" />
          ))}
        </div>
      ) : (categories.data ?? []).length === 0 ? (
        <EmptyState icon={FolderTree} title="Sem categorias" description="Crie a primeira categoria." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {categories.data!.map((c) => (
            <Card key={c.id} className="p-5">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="truncate font-display text-base font-semibold">{c.name}</h3>
                  <p className="tabular mt-0.5 truncate text-xs text-muted-foreground">{c.slug}</p>
                </div>
                <div className="flex items-center gap-1">
                  <Badge tone={c.is_active ? "success" : "neutral"}>{c.is_active ? "Ativa" : "Inativa"}</Badge>
                  <Button size="icon" variant="ghost" onClick={() => openEdit(c)} title="Editar categoria">
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button size="icon" variant="ghost" onClick={() => remove(c)} title="Apagar categoria">
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <p className="mt-3 line-clamp-2 text-sm text-muted-foreground">{c.description || "Sem descrição."}</p>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? "Editar categoria" : "Nova categoria"}
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={save} disabled={submitting || !form.name || !form.slug}>
              {submitting && <Spinner />} {editing ? "Salvar" : "Criar"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field>
            <Label htmlFor="c-name">Nome</Label>
            <Input id="c-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <Field>
            <Label htmlFor="c-slug">Slug</Label>
            <Input id="c-slug" className="tabular" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} />
          </Field>
          <Field>
            <Label htmlFor="c-desc">Descrição</Label>
            <Textarea id="c-desc" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              className="h-4 w-4 accent-primary"
            />
            Ativa
          </label>
        </div>
      </Modal>
    </div>
  );
}
