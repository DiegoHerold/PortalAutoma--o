"use client";

import { useMemo, useState } from "react";

import { EmptyState } from "@/components/shared/empty-state";
import { ScheduleItemBlock } from "@/components/schedules/schedule-calendar-item";
import { ScheduleItemsSheet } from "@/components/schedules/schedule-items-sheet";
import { hourLabel, isSameDay, toDateKey } from "@/lib/calendar";
import { clampItemToDay, groupByOverlapGroup, MAX_INLINE_LANES } from "@/lib/schedule-calendar-layout";
import { targetLabel } from "@/components/schedules/schedule-calendar-item";
import { cn } from "@/lib/utils";
import type { ScheduleCalendarItem } from "@/types/schedule";

const HOUR_PX = 56;
export type DayGroupBy = "none" | "type" | "target" | "agent";

const GROUP_OPTIONS: { value: DayGroupBy; label: string }[] = [
  { value: "none", label: "Nenhum" },
  { value: "type", label: "Tipo" },
  { value: "target", label: "Automação/Fluxo" },
  { value: "agent", label: "Agent" },
];

function groupKeyFor(item: ScheduleCalendarItem, groupBy: DayGroupBy): string {
  if (groupBy === "type") return targetLabel(item.target_type);
  if (groupBy === "target") return item.target_name;
  if (groupBy === "agent") return item.agent ?? "Sem Agent atribuído";
  return "all";
}

export function DayView({
  date,
  items,
  onSelectItem,
  groupBy,
  onGroupByChange,
}: {
  date: Date;
  items: ScheduleCalendarItem[];
  onSelectItem: (item: ScheduleCalendarItem) => void;
  groupBy: DayGroupBy;
  onGroupByChange: (value: DayGroupBy) => void;
}) {
  const [cluster, setCluster] = useState<{ title: string; items: ScheduleCalendarItem[] } | null>(null);

  const dayKey = toDateKey(date);
  const dayItems = useMemo(() => items.filter((item) => clampItemToDay(item, date) !== null), [items, date, dayKey]);

  if (dayItems.length === 0) {
    return <EmptyState title="Nenhuma ocorrência neste dia" description="Ajuste os filtros ou escolha outro dia." />;
  }

  const groups = useMemo(() => {
    const map = new Map<string, ScheduleCalendarItem[]>();
    for (const item of dayItems) {
      const key = groupKeyFor(item, groupBy);
      const bucket = map.get(key) ?? [];
      bucket.push(item);
      map.set(key, bucket);
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dayItems, groupBy]);

  const columns = groupBy === "none" ? [["all", dayItems] as [string, ScheduleCalendarItem[]]] : groups;
  const totalHeight = 24 * HOUR_PX;
  const now = new Date();
  const nowOffsetPx = isSameDay(date, now) ? (now.getHours() * 60 + now.getMinutes()) * (HOUR_PX / 60) : null;

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <div className="flex items-center justify-end gap-1 border-b border-border bg-muted/20 px-2 py-1.5">
        <span className="mr-1 text-xs text-muted-foreground">Agrupar por:</span>
        {GROUP_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onGroupByChange(opt.value)}
            className={cn(
              "rounded px-2 py-0.5 text-xs font-medium transition-colors",
              groupBy === opt.value ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>
      {groupBy !== "none" && (
        <div className="grid border-b border-border bg-muted/40 text-xs font-medium text-muted-foreground" style={{ gridTemplateColumns: `56px repeat(${columns.length}, 1fr)` }}>
          <div />
          {columns.map(([key]) => (
            <div key={key} className="truncate border-l border-border px-2 py-2 text-center">
              {key}
            </div>
          ))}
        </div>
      )}
      <div className="relative max-h-[680px] overflow-y-auto">
        <div className="grid" style={{ gridTemplateColumns: `56px repeat(${columns.length}, 1fr)`, height: totalHeight }}>
          <div className="relative border-r border-border">
            {Array.from({ length: 24 }, (_, hour) => (
              <div key={hour} className="tabular absolute left-0 right-1 -translate-y-1/2 text-right text-xs text-muted-foreground" style={{ top: hour * HOUR_PX }}>
                {hourLabel(hour)}
              </div>
            ))}
          </div>
          {columns.map(([key, columnItems]) => {
            const blocks = columnItems
              .map((item) => {
                const clamped = clampItemToDay(item, date);
                if (!clamped) return null;
                return { item, top: (clamped.startMinutes / 60) * HOUR_PX, height: Math.max(((clamped.endMinutes - clamped.startMinutes) / 60) * HOUR_PX, 18), laneIndex: clamped.laneIndex };
              })
              .filter((b): b is { item: ScheduleCalendarItem; top: number; height: number; laneIndex: number } => b !== null);
            const overlapGroups = groupByOverlapGroup(columnItems);

            return (
              <div key={key} className="relative border-l border-border/60">
                {Array.from({ length: 24 }, (_, hour) => (
                  <div key={hour} className="absolute left-0 right-0 border-b border-border/40" style={{ top: hour * HOUR_PX, height: HOUR_PX }} />
                ))}
                {nowOffsetPx != null && (
                  <div className="absolute left-0 right-0 z-10 border-t-2 border-primary" style={{ top: nowOffsetPx }}>
                    <span className="absolute -left-1 -top-1 h-2 w-2 rounded-full bg-primary" />
                  </div>
                )}
                {[...overlapGroups.entries()].map(([groupKey, groupItems]) => {
                  if (groupItems.length > MAX_INLINE_LANES) {
                    const block = blocks.find((b) => b.item.id === groupItems[0].id);
                    if (!block) return null;
                    return (
                      <button
                        key={groupKey}
                        type="button"
                        onClick={() => setCluster({ title: `${groupItems.length} execuções simultâneas`, items: groupItems })}
                        className="absolute overflow-hidden rounded-md border border-warning/40 bg-warning/10 px-1.5 py-1 text-left text-xs font-medium text-warning shadow-sm"
                        style={{ top: block.top, height: block.height, left: "2%", width: "96%" }}
                      >
                        {groupItems.length} execuções — ver todas
                      </button>
                    );
                  }
                  return groupItems.map((item) => {
                    const block = blocks.find((b) => b.item.id === item.id);
                    if (!block) return null;
                    const widthPct = 100 / groupItems.length;
                    const leftPct = block.laneIndex * widthPct;
                    return (
                      <div key={item.id} className="absolute" style={{ top: block.top, height: block.height, left: `${leftPct}%`, width: `${widthPct}%` }}>
                        <div className="h-full px-0.5">
                          <ScheduleItemBlock item={item} onClick={() => onSelectItem(item)} compact={block.height < 40} />
                        </div>
                      </div>
                    );
                  });
                })}
              </div>
            );
          })}
        </div>
      </div>

      <ScheduleItemsSheet
        open={!!cluster}
        onClose={() => setCluster(null)}
        title={cluster?.title ?? ""}
        items={cluster?.items ?? []}
        onSelect={(item) => {
          setCluster(null);
          onSelectItem(item);
        }}
      />
    </div>
  );
}
