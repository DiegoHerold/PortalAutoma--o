"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { RefreshCw } from "lucide-react";

import { ErrorState } from "@/components/shared/error-state";
import { AgendaView } from "@/components/schedules/calendar/agenda-view";
import { groupItemsByDay } from "@/components/schedules/calendar/occurrence-utils";
import { DayView, type DayGroupBy } from "@/components/schedules/calendar/day-view";
import { MonthView } from "@/components/schedules/calendar/month-view";
import { WeekView } from "@/components/schedules/calendar/week-view";
import { ScheduleDetailSheet } from "@/components/schedules/schedule-detail-sheet";
import { ScheduleFormSheet } from "@/components/schedules/schedule-form-sheet";
import { SchedulesActiveFilters } from "@/components/schedules/schedules-active-filters";
import { SchedulesFilterBar, type QuickFilterState } from "@/components/schedules/schedules-filter-bar";
import { SchedulesFilterSheet } from "@/components/schedules/schedules-filter-sheet";
import { SchedulesHeader } from "@/components/schedules/schedules-header";
import { SchedulesNowView } from "@/components/schedules/schedules-now-view";
import { SchedulesSummary } from "@/components/schedules/schedules-summary";
import { ScheduleStatusLegend } from "@/components/schedules/schedule-status-legend";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { getWeekDays, parseDateKey, toDateKey } from "@/lib/calendar";
import { hasPermission } from "@/lib/permissions";
import {
  countActiveFilters,
  filtersToQueryPatch,
  parseFiltersFromParams,
  type ScheduleFilters,
} from "@/lib/schedule-filters";
import { parseScheduleView, scheduleViewHeaderLabel, scheduleViewRange, stepScheduleAnchor, type ScheduleView } from "@/lib/schedule-view";
import { relativeFromNow } from "@/lib/utils";
import type { Automation } from "@/types/automation";
import type { Flow } from "@/types/flow";
import type { Density } from "@/components/schedules/schedule-calendar-item";
import type { ScheduleCalendarItem, ScheduleCalendarResponse, TargetType } from "@/types/schedule";

const DENSITY_STORAGE_KEY = "schedules.density";

export function SchedulesManager() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { user } = useAuth();

  const view = parseScheduleView(searchParams.get("view"));
  const anchor = searchParams.get("date") ? parseDateKey(searchParams.get("date")!) : todayAnchor();
  const filters = useMemo(() => parseFiltersFromParams(searchParams), [searchParams]);
  const dayGroupBy = (searchParams.get("group") as DayGroupBy) || "none";

  const [density, setDensity] = useState<Density>("comfortable");
  useEffect(() => {
    const saved = typeof window !== "undefined" ? window.localStorage.getItem(DENSITY_STORAGE_KEY) : null;
    if (saved === "compact" || saved === "comfortable") setDensity(saved);
  }, []);
  function changeDensity(next: Density) {
    setDensity(next);
    if (typeof window !== "undefined") window.localStorage.setItem(DENSITY_STORAGE_KEY, next);
  }

  const [detailScheduleId, setDetailScheduleId] = useState<number | null>(null);
  const [detailItem, setDetailItem] = useState<ScheduleCalendarItem | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [formEditingId, setFormEditingId] = useState<number | null>(null);
  const [formPrefill, setFormPrefill] = useState<{ targetType?: TargetType; specificDate?: string } | undefined>();
  const [filterSheetOpen, setFilterSheetOpen] = useState(false);

  const automationsQuery = useApi<Automation[]>("/automations");
  const flowsQuery = useApi<Flow[]>("/flows");

  const range = useMemo(() => scheduleViewRange(view, anchor), [view, anchor]);

  const calendarUrl = useMemo(() => {
    const params = new URLSearchParams();
    params.set("from", toDateKey(range.from));
    params.set("to", toDateKey(range.to));
    params.set("timezone", filters.timezone);
    params.set("view", view);
    if (filters.targetType !== "all") params.set("target_type", filters.targetType);
    if (filters.automationIds.length) params.set("automation_ids", filters.automationIds.join(","));
    if (filters.flowIds.length) params.set("flow_ids", filters.flowIds.join(","));
    if (filters.statuses.length) params.set("statuses", filters.statuses.join(","));
    if (filters.owners.length) params.set("owners", filters.owners.join(","));
    if (filters.search.trim()) params.set("search", filters.search.trim());
    return `/schedules/calendar?${params.toString()}`;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range.from, range.to, filters, view]);

  // Tempo real (seção 31): polling moderado em vez de uma conexão SSE por item do calendário.
  // Janelas mais operacionais (Agora/Dia/Semana) atualizam mais rápido que Mês/Agenda.
  const pollMs = view === "now" ? 15_000 : view === "day" || view === "week" ? 30_000 : 90_000;
  const calendarQuery = useApi<ScheduleCalendarResponse>(calendarUrl, { pollMs });

  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);
  useEffect(() => {
    if (calendarQuery.data) setLastUpdatedAt(Date.now());
  }, [calendarQuery.data]);

  const items = useMemo(() => calendarQuery.data?.items ?? [], [calendarQuery.data]);
  const itemsByDay = useMemo(() => groupItemsByDay(items), [items]);

  const automationById = useMemo(() => {
    const map = new Map<number, Automation>();
    automationsQuery.data?.forEach((a) => map.set(a.id, a));
    return map;
  }, [automationsQuery.data]);

  const flowById = useMemo(() => {
    const map = new Map<string, Flow>();
    flowsQuery.data?.forEach((f) => map.set(f.id, f));
    return map;
  }, [flowsQuery.data]);

  const ownerOptions = useMemo(() => Array.from(new Set(items.map((i) => i.responsible).filter((v): v is string => !!v))).sort(), [items]);

  function setQuery(patch: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(patch).forEach(([key, value]) => {
      if (!value) params.delete(key);
      else params.set(key, value);
    });
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  function updateView(next: ScheduleView) {
    setQuery({ view: next === "week" ? null : next });
  }

  function updateFilters(next: ScheduleFilters) {
    setQuery(filtersToQueryPatch(next));
  }

  const quickFilterState: QuickFilterState = { targetType: filters.targetType, statuses: filters.statuses };
  function updateQuickFilters(next: QuickFilterState) {
    updateFilters({ ...filters, targetType: next.targetType, statuses: next.statuses });
  }

  function stepAnchor(delta: number) {
    setQuery({ date: toDateKey(stepScheduleAnchor(view, anchor, delta)) });
  }

  const headerLabel = scheduleViewHeaderLabel(view, anchor);

  function openCreate(dateKey?: string) {
    setFormPrefill({ targetType: filters.targetType !== "all" ? filters.targetType : "automation", specificDate: dateKey });
    setFormEditingId(null);
    setFormOpen(true);
  }

  function openEditFromDetail(scheduleId: number) {
    setDetailScheduleId(null);
    setDetailItem(null);
    setFormPrefill(undefined);
    setFormEditingId(scheduleId);
    setFormOpen(true);
  }

  function openItem(item: ScheduleCalendarItem) {
    setDetailItem(item);
    setDetailScheduleId(item.schedule_id);
  }

  async function refetchAll() {
    await calendarQuery.refetch();
  }

  const canWrite = hasPermission(user, "schedule.update");
  const canTrigger = hasPermission(user, "schedule.trigger") || canWrite;

  const activeFilterCount = countActiveFilters(filters);

  return (
    <div className="space-y-4">
      <SchedulesHeader
        view={view}
        onViewChange={updateView}
        headerLabel={headerLabel}
        showDateNav={view !== "now"}
        onPrev={() => stepAnchor(-1)}
        onNext={() => stepAnchor(1)}
        onToday={() => setQuery({ date: null })}
        search={filters.search}
        onSearchChange={(value) => updateFilters({ ...filters, search: value })}
        timezone={filters.timezone}
        activeFilterCount={activeFilterCount}
        onOpenFilters={() => setFilterSheetOpen(true)}
        onCreate={() => openCreate()}
        canCreate={canWrite}
      />

      <SchedulesSummary summary={calendarQuery.data?.summary ?? null} />

      <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-3 lg:flex-row lg:items-center lg:justify-between">
        <SchedulesFilterBar state={quickFilterState} onChange={updateQuickFilters} />
        <span className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
          <RefreshCw className={cnAnim(calendarQuery.loading)} />
          {calendarQuery.loading && lastUpdatedAt == null ? "Carregando…" : lastUpdatedAt ? `Atualizado ${relativeFromNow(new Date(lastUpdatedAt).toISOString())}` : ""}
        </span>
      </div>

      <SchedulesActiveFilters filters={filters} automationById={automationById} flowById={flowById} onChange={updateFilters} onClearAll={() => updateFilters({ ...filters, targetType: "all", statuses: [], automationIds: [], flowIds: [], owners: [], search: "" })} />

      <ScheduleStatusLegend />

      {calendarQuery.error && !calendarQuery.data ? (
        <ErrorState message={calendarQuery.error} onRetry={calendarQuery.refetch} />
      ) : calendarQuery.loading && !calendarQuery.data ? (
        <Skeleton className="h-[560px] rounded-lg" />
      ) : view === "now" ? (
        <SchedulesNowView items={items} onSelect={openItem} />
      ) : view === "month" ? (
        <MonthView anchor={anchor} itemsByDay={itemsByDay} onSelectItem={openItem} onCreateForDate={openCreate} />
      ) : view === "week" ? (
        <WeekView days={getWeekDays(anchor)} items={items} onSelectItem={openItem} onCreateForDate={openCreate} />
      ) : view === "day" ? (
        <DayView date={anchor} items={items} onSelectItem={openItem} groupBy={dayGroupBy} onGroupByChange={(v) => setQuery({ group: v === "none" ? null : v })} />
      ) : (
        <AgendaView from={range.from} to={range.to} itemsByDay={itemsByDay} onSelectItem={openItem} density={density} onLoadMore={() => stepAnchor(1)} />
      )}

      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => changeDensity(density === "comfortable" ? "compact" : "comfortable")}
          className="text-xs text-muted-foreground underline-offset-2 hover:underline"
        >
          Densidade: {density === "comfortable" ? "Confortável" : "Compacta"} — alternar
        </button>
      </div>

      <ScheduleDetailSheet
        scheduleId={detailScheduleId}
        item={detailItem}
        open={detailScheduleId != null}
        onClose={() => {
          setDetailScheduleId(null);
          setDetailItem(null);
        }}
        automationById={automationById}
        flowById={flowById}
        onEdit={openEditFromDetail}
        onChanged={refetchAll}
        canWrite={canWrite}
        canTrigger={canTrigger}
      />

      <ScheduleFormSheet
        open={formOpen}
        onClose={() => setFormOpen(false)}
        editingId={formEditingId}
        prefill={formPrefill}
        automations={automationsQuery.data ?? []}
        flows={flowsQuery.data ?? []}
        onSaved={refetchAll}
      />

      <SchedulesFilterSheet
        open={filterSheetOpen}
        onClose={() => setFilterSheetOpen(false)}
        filters={filters}
        automations={automationsQuery.data ?? []}
        flows={flowsQuery.data ?? []}
        ownerOptions={ownerOptions}
        onApply={updateFilters}
      />
    </div>
  );
}

function cnAnim(spinning: boolean): string {
  return spinning ? "h-3 w-3 animate-spin" : "h-3 w-3";
}

function todayAnchor(): Date {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}
