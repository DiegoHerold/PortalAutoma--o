"use client";

import { useMemo, useState } from "react";

import { ScheduleItemBlock } from "@/components/schedules/schedule-calendar-item";
import { ScheduleItemsSheet } from "@/components/schedules/schedule-items-sheet";
import { hourLabel, isSameDay, shortDayLabel, toDateKey } from "@/lib/calendar";
import { clampItemToDay, groupByOverlapGroup, MAX_INLINE_LANES } from "@/lib/schedule-calendar-layout";
import { cn } from "@/lib/utils";
import type { ScheduleCalendarItem } from "@/types/schedule";

const HOUR_PX = 48;

const RANGE_PRESETS = {
  full: { start: 0, end: 24, label: "24 horas" },
  business: { start: 6, end: 22, label: "Horário comercial" },
} as const;

export function WeekView({
  days,
  items,
  onSelectItem,
  onCreateForDate,
}: {
  days: Date[];
  items: ScheduleCalendarItem[];
  onSelectItem: (item: ScheduleCalendarItem) => void;
  onCreateForDate: (dateKey: string) => void;
}) {
  const [rangeKey, setRangeKey] = useState<keyof typeof RANGE_PRESETS>("business");
  const [cluster, setCluster] = useState<{ title: string; items: ScheduleCalendarItem[] } | null>(null);
  const range = RANGE_PRESETS[rangeKey];
  const today = new Date();
  const hours = useMemo(() => Array.from({ length: range.end - range.start }, (_, i) => range.start + i), [range]);
  const totalHeight = hours.length * HOUR_PX;

  const nowOffsetPx = (() => {
    const now = new Date();
    const minutes = now.getHours() * 60 + now.getMinutes();
    const rangeStartMin = range.start * 60;
    const rangeEndMin = range.end * 60;
    if (minutes < rangeStartMin || minutes > rangeEndMin) return null;
    return ((minutes - rangeStartMin) / 60) * HOUR_PX;
  })();

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <div className="flex items-center justify-end gap-1 border-b border-border bg-muted/20 px-2 py-1">
        {(Object.keys(RANGE_PRESETS) as (keyof typeof RANGE_PRESETS)[]).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setRangeKey(key)}
            className={cn(
              "rounded px-2 py-0.5 text-xs font-medium transition-colors",
              rangeKey === key ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {RANGE_PRESETS[key].label}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-[56px_repeat(7,1fr)] border-b border-border bg-muted/40 text-xs font-medium text-muted-foreground">
        <div />
        {days.map((date) => {
          const key = toDateKey(date);
          const isToday = isSameDay(date, today);
          return (
            <button
              key={key}
              type="button"
              onClick={() => onCreateForDate(key)}
              className={cn("border-l border-border px-2 py-2 text-center hover:bg-accent/40", isToday && "text-primary")}
              title="Criar agendamento neste dia"
            >
              {shortDayLabel(date)}
            </button>
          );
        })}
      </div>
      <div className="relative max-h-[600px] overflow-y-auto">
        <div className="grid grid-cols-[56px_repeat(7,1fr)]" style={{ height: totalHeight }}>
          <div className="relative border-r border-border">
            {hours.map((hour) => (
              <div key={hour} className="tabular absolute left-0 right-1 -translate-y-1/2 text-right text-xs text-muted-foreground" style={{ top: (hour - range.start) * HOUR_PX }}>
                {hourLabel(hour)}
              </div>
            ))}
          </div>
          {days.map((date) => {
            const key = toDateKey(date);
            const dayBlocks = clampItemsForColumn(items, date, range.start, range.end);
            const groups = groupByOverlapGroup(dayBlocks.map((b) => b.item));

            return (
              <div key={key} className="relative border-l border-border/60">
                {hours.map((hour) => (
                  <div key={hour} className="absolute left-0 right-0 border-b border-border/40" style={{ top: (hour - range.start) * HOUR_PX, height: HOUR_PX }} />
                ))}
                {isSameDay(date, today) && nowOffsetPx != null && (
                  <div className="absolute left-0 right-0 z-10 border-t-2 border-primary" style={{ top: nowOffsetPx }}>
                    <span className="absolute -left-1 -top-1 h-2 w-2 rounded-full bg-primary" />
                  </div>
                )}
                {[...groups.entries()].map(([groupKey, groupItems]) => {
                  if (groupItems.length > MAX_INLINE_LANES) {
                    const block = dayBlocks.find((b) => b.item.id === groupItems[0].id)!;
                    return (
                      <button
                        key={groupKey}
                        type="button"
                        onClick={() => setCluster({ title: `${groupItems.length} execuções simultâneas`, items: groupItems })}
                        className="absolute overflow-hidden rounded-md border border-warning/40 bg-warning/10 px-1.5 py-1 text-left text-xs font-medium text-warning shadow-sm"
                        style={{ top: block.topPx, height: Math.max(block.heightPx, 20), left: "2%", width: "96%" }}
                      >
                        {groupItems.length} execuções — ver todas
                      </button>
                    );
                  }
                  return groupItems.map((item) => {
                    const block = dayBlocks.find((b) => b.item.id === item.id)!;
                    const widthPct = 100 / groupItems.length;
                    const leftPct = block.laneIndex * widthPct;
                    return (
                      <div key={item.id} className="absolute" style={{ top: block.topPx, height: Math.max(block.heightPx, 20), left: `${leftPct}%`, width: `${widthPct}%` }}>
                        <div className="h-full px-0.5">
                          <ScheduleItemBlock item={item} onClick={() => onSelectItem(item)} compact={block.heightPx < 34} />
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

type PositionedBlock = { item: ScheduleCalendarItem; topPx: number; heightPx: number; laneIndex: number };

function clampItemsForColumn(items: ScheduleCalendarItem[], date: Date, rangeStart: number, rangeEnd: number): PositionedBlock[] {
  const rangeStartMin = rangeStart * 60;
  const rangeEndMin = rangeEnd * 60;
  const result: PositionedBlock[] = [];
  for (const item of items) {
    const clamped = clampItemToDay(item, date);
    if (!clamped) continue;
    const start = Math.max(clamped.startMinutes, rangeStartMin);
    const end = Math.min(clamped.endMinutes, rangeEndMin);
    if (end <= start) continue;
    result.push({
      item,
      topPx: ((start - rangeStartMin) / 60) * HOUR_PX,
      heightPx: Math.max(((end - start) / 60) * HOUR_PX, 14),
      laneIndex: clamped.laneIndex,
    });
  }
  return result;
}
