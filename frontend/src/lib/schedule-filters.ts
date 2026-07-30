import type { TargetType } from "@/types/schedule";

/**
 * Estado de filtros da Central de Agendamentos, espelhado 1:1 na URL (seção 2/8/29):
 * /schedules?view=week&date=2026-07-29&target_type=automation,flow&status=running,scheduled
 * Cada campo aqui tem uma chave de URL correspondente — ver `parseFiltersFromParams`/`filtersToParams`.
 */
export type ScheduleFilters = {
  targetType: TargetType | "all";
  statuses: string[];
  automationIds: number[];
  flowIds: string[];
  owners: string[];
  search: string;
  timezone: string;
  group: "none" | "time" | "resource";
};

export const DEFAULT_TIMEZONE = "America/Sao_Paulo";

export function emptyFilters(): ScheduleFilters {
  return {
    targetType: "all",
    statuses: [],
    automationIds: [],
    flowIds: [],
    owners: [],
    search: "",
    timezone: DEFAULT_TIMEZONE,
    group: "none",
  };
}

function splitCsv(value: string | null): string[] {
  if (!value) return [];
  return value
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

export function parseFiltersFromParams(searchParams: URLSearchParams): ScheduleFilters {
  const targetTypeRaw = searchParams.get("target_type") ?? "all";
  const targetType: TargetType | "all" = targetTypeRaw === "automation" || targetTypeRaw === "flow" ? targetTypeRaw : "all";
  return {
    targetType,
    statuses: splitCsv(searchParams.get("status")),
    automationIds: splitCsv(searchParams.get("automation_ids")).map(Number).filter((n) => !Number.isNaN(n)),
    flowIds: splitCsv(searchParams.get("flow_ids")),
    owners: splitCsv(searchParams.get("owners")),
    search: searchParams.get("q") ?? "",
    timezone: searchParams.get("tz") || DEFAULT_TIMEZONE,
    group: (searchParams.get("group") as ScheduleFilters["group"]) || "none",
  };
}

/** Patch parcial pronto para `setQuery` (schedules-manager.tsx) — null remove a chave. */
export function filtersToQueryPatch(filters: ScheduleFilters): Record<string, string | null> {
  return {
    target_type: filters.targetType === "all" ? null : filters.targetType,
    status: filters.statuses.length ? filters.statuses.join(",") : null,
    automation_ids: filters.automationIds.length ? filters.automationIds.join(",") : null,
    flow_ids: filters.flowIds.length ? filters.flowIds.join(",") : null,
    owners: filters.owners.length ? filters.owners.join(",") : null,
    q: filters.search.trim() ? filters.search.trim() : null,
    tz: filters.timezone === DEFAULT_TIMEZONE ? null : filters.timezone,
    group: filters.group === "none" ? null : filters.group,
  };
}

export function countActiveFilters(filters: ScheduleFilters): number {
  let count = 0;
  if (filters.targetType !== "all") count += 1;
  count += filters.statuses.length;
  count += filters.automationIds.length > 0 ? 1 : 0;
  count += filters.flowIds.length > 0 ? 1 : 0;
  count += filters.owners.length;
  if (filters.search.trim()) count += 1;
  if (filters.timezone !== DEFAULT_TIMEZONE) count += 1;
  return count;
}

export const STATUS_FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: "future", label: "Futuro" },
  { value: "running", label: "Em andamento" },
  { value: "delayed", label: "Atrasado" },
  { value: "awaiting_trigger", label: "Aguardando disparo" },
  { value: "completed", label: "Concluído" },
  { value: "failed", label: "Falhou" },
  { value: "past_cancelled", label: "Cancelado" },
  { value: "past_skipped_overlap", label: "Ignorado (overlap)" },
  { value: "past_skipped_misfire", label: "Ignorado (misfire)" },
];
