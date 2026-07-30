"use client";

import { X } from "lucide-react";

import { DEFAULT_TIMEZONE, STATUS_FILTER_OPTIONS, type ScheduleFilters } from "@/lib/schedule-filters";
import type { Automation } from "@/types/automation";
import type { Flow } from "@/types/flow";

function Chip({ children, onRemove }: { children: React.ReactNode; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-foreground">
      {children}
      <button type="button" onClick={onRemove} className="rounded-full p-0.5 hover:bg-background" aria-label="Remover filtro">
        <X className="h-3 w-3" />
      </button>
    </span>
  );
}

/** Nível 2 — filtros ativos como chips compactos acima do calendário (seção 8). */
export function SchedulesActiveFilters({
  filters,
  automationById,
  flowById,
  onChange,
  onClearAll,
}: {
  filters: ScheduleFilters;
  automationById: Map<number, Automation>;
  flowById: Map<string, Flow>;
  onChange: (next: ScheduleFilters) => void;
  onClearAll: () => void;
}) {
  const chips: { key: string; label: string; onRemove: () => void }[] = [];

  if (filters.targetType !== "all") {
    chips.push({
      key: "target",
      label: filters.targetType === "flow" ? "Fluxos" : "Automações",
      onRemove: () => onChange({ ...filters, targetType: "all" }),
    });
  }
  for (const status of filters.statuses) {
    const label = STATUS_FILTER_OPTIONS.find((s) => s.value === status)?.label ?? status;
    chips.push({ key: `status:${status}`, label, onRemove: () => onChange({ ...filters, statuses: filters.statuses.filter((s) => s !== status) }) });
  }
  if (filters.automationIds.length) {
    const label =
      filters.automationIds.length === 1
        ? (automationById.get(filters.automationIds[0])?.name ?? `Automação #${filters.automationIds[0]}`)
        : `${filters.automationIds.length} automações selecionadas`;
    chips.push({ key: "automation_ids", label, onRemove: () => onChange({ ...filters, automationIds: [] }) });
  }
  if (filters.flowIds.length) {
    const label = filters.flowIds.length === 1 ? (flowById.get(filters.flowIds[0])?.name ?? `Fluxo`) : `${filters.flowIds.length} fluxos selecionados`;
    chips.push({ key: "flow_ids", label, onRemove: () => onChange({ ...filters, flowIds: [] }) });
  }
  for (const owner of filters.owners) {
    chips.push({ key: `owner:${owner}`, label: `Responsável: ${owner}`, onRemove: () => onChange({ ...filters, owners: filters.owners.filter((o) => o !== owner) }) });
  }
  if (filters.search.trim()) {
    chips.push({ key: "search", label: `Busca: "${filters.search.trim()}"`, onRemove: () => onChange({ ...filters, search: "" }) });
  }
  if (filters.timezone !== DEFAULT_TIMEZONE) {
    chips.push({ key: "tz", label: `Timezone: ${filters.timezone}`, onRemove: () => onChange({ ...filters, timezone: DEFAULT_TIMEZONE }) });
  }

  if (chips.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {chips.map((chip) => (
        <Chip key={chip.key} onRemove={chip.onRemove}>
          {chip.label}
        </Chip>
      ))}
      <button type="button" onClick={onClearAll} className="text-xs font-medium text-muted-foreground underline-offset-2 hover:underline">
        Limpar tudo
      </button>
    </div>
  );
}
