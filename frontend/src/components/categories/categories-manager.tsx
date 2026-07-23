"use client";

import { useState } from "react";
import { FolderTree, Plus } from "lucide-react";

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

export function CategoriesManager() {
  const { token } = useAuth();
  const { toast } = useToast();
  const categories = useApi<Category[]>("/categories");
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "", description: "", is_active: true });

  async function create() {
    if (!token) return;
    setSubmitting(true);
    try {
      await apiRequest<Category>("/categories", { method: "POST", token, body: JSON.stringify(form) });
      toast({ title: "Categoria criada", kind: "success" });
      setForm({ name: "", slug: "", description: "", is_active: true });
      setOpen(false);
      await categories.refetch();
    } catch (err) {
      toast({ title: "Falha ao criar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <Button onClick={() => setOpen(true)}>
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
                <Badge tone={c.is_active ? "success" : "neutral"}>{c.is_active ? "Ativa" : "Inativa"}</Badge>
              </div>
              <p className="mt-3 line-clamp-2 text-sm text-muted-foreground">{c.description || "Sem descrição."}</p>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Nova categoria"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={create} disabled={submitting || !form.name}>
              {submitting && <Spinner />} Criar
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
