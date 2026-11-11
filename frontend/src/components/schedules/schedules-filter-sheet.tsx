"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input, Label } from "@/components/ui/input";
import { Sheet } from "@/components/ui/sheet";
import { DEFAULT_TIMEZONE, STATUS_FILTER_OPTIONS, type ScheduleFilters } from "@/lib/schedule-filters";
import { cn } from "@/lib/utils";
import type { Automation } from "@/types/automation";
import type { Flow } from "@/types/flow";

/**
 * Nível 3 — filtros avançados (seção 7). Abre em Sheet, não ocupa espaço permanente do
 * calendário. Cobre os campos sustentados pelo domínio real hoje (target, automação/fluxo
 * específicos, status temporal, responsável, timezone). Campos do enunciado sem suporte real
 * no backend hoje (organização, tags, origem, Agent, overlap/misfire policy como filtro,
 * duração) ficam de fora — ver pendências no relatório final, não inventamos parâmetros que
 * a API não aceita.
 */
export function SchedulesFilterSheet({
  open,
  onClose,
  filters,
  automations,
  flows,
  ownerOptions,
  onApply,
}: {
  open: boolean;
  onClose: () => void;
  filters: ScheduleFilters;
  automations: Automation[];
  flows: Flow[];
  ownerOptions: string[];
  onApply: (next: ScheduleFilters) => void;
}) {
  const [draft, setDraft] = useState<ScheduleFilters>(filters);
  const [automationSearch, setAutomationSearch] = useState("");
  const [flowSearch, setFlowSearch] = useState("");

  if (!open) return null;

  const visibleAutomations = automations.filter((a) => a.name.toLowerCase().includes(automationSearch.toLowerCase()));
  const visibleFlows = flows.filter((f) => f.name.toLowerCase().includes(flowSearch.toLowerCase()));

  function toggleStatus(value: string) {
    setDraft((d) => ({ ...d, statuses: d.statuses.includes(value) ? d.statuses.filter((s) => s !== value) : [...d.statuses, value] }));
  }

  function toggleAutomation(id: number) {
    setDraft((d) => ({ ...d, automationIds: d.automationIds.includes(id) ? d.automationIds.filter((v) => v !== id) : [...d.automationIds, id] }));
  }

  function toggleFlow(id: string) {
    setDraft((d) => ({ ...d, flowIds: d.flowIds.includes(id) ? d.flowIds.filter((v) => v !== id) : [...d.flowIds, id] }));
  }

  function toggleOwner(owner: string) {
    setDraft((d) => ({ ...d, owners: d.owners.includes(owner) ? d.owners.filter((v) => v !== owner) : [...d.owners, owner] }));
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Filtros avançados"
      description="Refine a Central de Agendamentos sem sair da visão atual."
      widthClassName="w-full sm:max-w-md"
      footer={
        <>
          <Button
            variant="ghost"
            onClick={() => {
              setDraft({ ...draft, statuses: [], automationIds: [], flowIds: [], owners: [], timezone: DEFAULT_TIMEZONE });
            }}
          >
            Limpar
          </Button>
          <Button
            onClick={() => {
              onApply(draft);
              onClose();
            }}
          >
            Aplicar filtros
          </Button>
        </>
      }
    >
      <div className="space-y-6">
        <section className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Tipo de destino</h3>
          <div className="grid grid-cols-3 gap-2">
            {(["all", "automation", "flow"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setDraft((d) => ({ ...d, targetType: t }))}
                className={cn(
                  "rounded-md border p-2 text-center text-xs font-medium transition-colors",
                  draft.targetType === t ? "border-primary bg-primary/5 text-primary" : "border-input text-muted-foreground hover:border-primary/50",
                )}
              >
                {t === "all" ? "Todos" : t === "automation" ? "Automações" : "Fluxos"}
              </button>
            ))}
          </div>
        </section>

        <section className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Status</h3>
          <div className="grid grid-cols-2 gap-1.5">
            {STATUS_FILTER_OPTIONS.map((opt) => (
              <label key={opt.value} className="flex items-center gap-2 text-xs">
                <input type="checkbox" className="h-3.5 w-3.5 accent-primary" checked={draft.statuses.includes(opt.value)} onChange={() => toggleStatus(opt.value)} />
                {opt.label}
              </label>
            ))}
          </div>
        </section>

        {draft.targetType !== "flow" && (
          <section className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Automações específicas</h3>
              {draft.automationIds.length > 0 && <span className="text-xs text-muted-foreground">{draft.automationIds.length} selecionadas</span>}
            </div>
            <Input placeholder="Buscar automação..." value={automationSearch} onChange={(e) => setAutomationSearch(e.target.value)} className="h-8 text-xs" />
            <div className="max-h-40 space-y-1 overflow-y-auto rounded-md border border-border p-2">
              {visibleAutomations.length === 0 && <p className="text-xs text-muted-foreground">Nenhuma automação encontrada.</p>}
              {visibleAutomations.map((a) => (
                <label key={a.id} className="flex items-center gap-2 text-xs">
                  <input type="checkbox" className="h-3.5 w-3.5 accent-primary" checked={draft.automationIds.includes(a.id)} onChange={() => toggleAutomation(a.id)} />
                  <span className="truncate">{a.name}</span>
                </label>
              ))}
            </div>
          </section>
        )}

        {draft.targetType !== "automation" && (
          <section className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Fluxos específicos</h3>
              {draft.flowIds.length > 0 && <span className="text-xs text-muted-foreground">{draft.flowIds.length} selecionados</span>}
            </div>
            <Input placeholder="Buscar fluxo..." value={flowSearch} onChange={(e) => setFlowSearch(e.target.value)} className="h-8 text-xs" />
            <div className="max-h-40 space-y-1 overflow-y-auto rounded-md border border-border p-2">
              {visibleFlows.length === 0 && <p className="text-xs text-muted-foreground">Nenhum fluxo encontrado.</p>}
              {visibleFlows.map((f) => (
                <label key={f.id} className="flex items-center gap-2 text-xs">
                  <input type="checkbox" className="h-3.5 w-3.5 accent-primary" checked={draft.flowIds.includes(f.id)} onChange={() => toggleFlow(f.id)} />
                  <span className="truncate">{f.name}</span>
                </label>
              ))}
            </div>
          </section>
        )}

        {ownerOptions.length > 0 && (
          <section className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Responsável</h3>
            <div className="max-h-32 space-y-1 overflow-y-auto rounded-md border border-border p-2">
              {ownerOptions.map((owner) => (
                <label key={owner} className="flex items-center gap-2 text-xs">
                  <input type="checkbox" className="h-3.5 w-3.5 accent-primary" checked={draft.owners.includes(owner)} onChange={() => toggleOwner(owner)} />
                  {owner}
                </label>
              ))}
            </div>
          </section>
        )}

        <section className="space-y-2">
          <Field>
            <Label htmlFor="filter-tz">Timezone de exibição</Label>
            <Input id="filter-tz" value={draft.timezone} onChange={(e) => setDraft((d) => ({ ...d, timezone: e.target.value || DEFAULT_TIMEZONE }))} className="tabular" />
          </Field>
        </section>
      </div>
    </Sheet>
  );
}
