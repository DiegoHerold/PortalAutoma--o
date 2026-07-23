"use client";

import { useMemo, useState } from "react";
import { Plus, Search, Workflow } from "lucide-react";

import { AutomationCard } from "@/components/automations/automation-card";
import { AutomationForm, type AutomationFormState } from "@/components/automations/automation-form";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type { Automation } from "@/types/automation";
import type { Category } from "@/types/category";

export function AutomationsManager() {
  const { token } = useAuth();
  const { toast } = useToast();
  const automations = useApi<Automation[]>("/automations");
  const categories = useApi<Category[]>("/categories");

  const [query, setQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const categoryName = useMemo(() => {
    const map = new Map<number, string>();
    categories.data?.forEach((c) => map.set(c.id, c.name));
    return map;
  }, [categories.data]);

  const filtered = useMemo(() => {
    const list = automations.data ?? [];
    const q = query.trim().toLowerCase();
    return list.filter((a) => {
      const matchesQuery = !q || a.name.toLowerCase().includes(q) || a.slug.toLowerCase().includes(q);
      const matchesCategory = !categoryFilter || String(a.category_id) === categoryFilter;
      return matchesQuery && matchesCategory;
    });
  }, [automations.data, query, categoryFilter]);

  async function createAutomation(form: AutomationFormState) {
    if (!token) return;
    setSubmitting(true);
    try {
      await apiRequest<Automation>("/automations", {
        method: "POST",
        token,
        body: JSON.stringify({ ...form, category_id: Number(form.category_id) }),
      });
      toast({ title: "Automação criada", kind: "success" });
      setModalOpen(false);
      await automations.refetch();
    } catch (err) {
      toast({ title: "Falha ao criar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Buscar por nome ou slug…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <Select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="sm:w-56">
          <option value="">Todas as categorias</option>
          {categories.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
        <Button onClick={() => setModalOpen(true)}>
          <Plus className="h-4 w-4" /> Nova automação
        </Button>
      </div>

      {automations.error ? (
        <ErrorState message={automations.error} onRetry={automations.refetch} />
      ) : automations.loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40 rounded-lg" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Workflow}
          title="Nenhuma automação"
          description={query || categoryFilter ? "Nenhum resultado para o filtro atual." : "Crie sua primeira automação."}
          action={
            !query && !categoryFilter ? (
              <Button onClick={() => setModalOpen(true)}>
                <Plus className="h-4 w-4" /> Nova automação
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((a) => (
            <AutomationCard key={a.id} automation={a} categoryName={categoryName.get(a.category_id)} />
          ))}
        </div>
      )}

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Nova automação"
        description="Cadastre uma automação e defina prioridade, executor e limites."
        className="max-w-2xl"
      >
        <AutomationForm categories={categories.data ?? []} onSubmit={createAutomation} submitting={submitting} />
      </Modal>
    </div>
  );
}
