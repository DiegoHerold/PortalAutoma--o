"use client";

import { useState } from "react";
import { Bot, Workflow } from "lucide-react";

import { ScheduleItemPill } from "@/components/schedules/schedule-calendar-item";
import { ScheduleItemsSheet } from "@/components/schedules/schedule-items-sheet";
import { dayLabel, getMonthGridDays, isSameDay, toDateKey, WEEKDAY_HEADER_LABELS } from "@/lib/calendar";
import { cn } from "@/lib/utils";
import type { ScheduleCalendarItem } from "@/types/schedule";

const VISIBLE_PER_CELL = 3;

export function MonthView({
  anchor,
  itemsByDay,
  onSelectItem,
  onCreateForDate,
}: {
  anchor: Date;
  itemsByDay: Map<string, ScheduleCalendarItem[]>;
  onSelectItem: (item: ScheduleCalendarItem) => void;
  onCreateForDate: (dateKey: string) => void;
}) {
  const gridDays = getMonthGridDays(anchor);
  const today = new Date();
  const [expandedDay, setExpandedDay] = useState<string | null>(null);

  const expandedItems = expandedDay ? (itemsByDay.get(expandedDay) ?? []) : [];

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <div className="grid grid-cols-7 border-b border-border bg-muted/40 text-xs font-medium text-muted-foreground">
        {WEEKDAY_HEADER_LABELS.map((label) => (
          <div key={label} className="px-2 py-2 text-center">
            {label}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {gridDays.map(({ date, inMonth }) => {
          const key = toDateKey(date);
          const dayItems = itemsByDay.get(key) ?? [];
          const isToday = isSameDay(date, today);
          const visible = dayItems.slice(0, VISIBLE_PER_CELL);
          const overflow = dayItems.length - visible.length;
          const automationCount = dayItems.filter((i) => i.target_type === "automation").length;
          const flowCount = dayItems.filter((i) => i.target_type === "flow").length;
          const failedCount = dayItems.filter((i) => i.temporal_status.startsWith("past_failed") || i.temporal_status === "past_dispatch_failed" || i.temporal_status === "past_timed_out").length;
          const runningCount = dayItems.filter((i) => ["running", "preparing", "cancelling"].includes(i.temporal_status)).length;

          return (
            <div
              key={key}
              className={cn(
                "flex min-h-[116px] flex-col items-stretch gap-1 border-b border-r border-border p-1.5 text-left transition-colors",
                !inMonth && "bg-muted/20 text-muted-foreground",
              )}
            >
              <button
                type="button"
                onClick={() => setExpandedDay(key)}
                className="flex items-center justify-between gap-1 self-stretch rounded hover:bg-accent/40"
                aria-label={`Ver resumo de ${dayLabel(date)}`}
              >
                <span
                  className={cn(
                    "rounded-full px-1.5 text-xs font-medium",
                    isToday ? "bg-primary text-primary-foreground" : "text-muted-foreground",
                  )}
                >
                  {date.getDate()}
                </span>
                {dayItems.length > 0 && (
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    {automationCount > 0 && (
                      <span className="flex items-center gap-0.5">
                        <Bot className="h-2.5 w-2.5" /> {automationCount}
                      </span>
                    )}
                    {flowCount > 0 && (
                      <span className="flex items-center gap-0.5">
                        <Workflow className="h-2.5 w-2.5" /> {flowCount}
                      </span>
                    )}
                  </span>
                )}
              </button>

              {(failedCount > 0 || runningCount > 0) && (
                <div className="flex gap-1">
                  {runningCount > 0 && <span className="rounded-full bg-info/15 px-1.5 text-xs font-medium text-info">{runningCount} ativas</span>}
                  {failedCount > 0 && <span className="rounded-full bg-destructive/15 px-1.5 text-xs font-medium text-destructive">{failedCount} falhas</span>}
                </div>
              )}

              <div className="flex flex-1 flex-col gap-1 overflow-hidden">
                {visible.map((item) => (
                  <ScheduleItemPill key={item.id} item={item} onClick={() => onSelectItem(item)} />
                ))}
                {overflow > 0 && (
                  <button
                    type="button"
                    onClick={() => setExpandedDay(key)}
                    className="px-1 text-left text-xs font-medium text-primary hover:underline"
                  >
                    + {overflow} outros
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <ScheduleItemsSheet
        open={!!expandedDay}
        onClose={() => setExpandedDay(null)}
        title={expandedDay ? `Resumo do dia — ${dayLabel(new Date(expandedDay + "T00:00:00"))}` : ""}
        items={expandedItems}
        onSelect={(item) => {
          setExpandedDay(null);
          onSelectItem(item);
        }}
        groupByBucket
        onCreate={
          expandedDay
            ? () => {
                const key = expandedDay;
                setExpandedDay(null);
                onCreateForDate(key);
              }
            : undefined
        }
      />
    </div>
  );
}
