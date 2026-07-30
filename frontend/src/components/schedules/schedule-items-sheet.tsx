"use client";

import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { EmptyState } from "@/components/shared/empty-state";
import { ScheduleItemRow } from "@/components/schedules/schedule-calendar-item";
import { temporalBucket } from "@/lib/status";
import type { ScheduleCalendarItem } from "@/types/schedule";

/**
 * Sheet genérico reaproveitado por dois casos do enunciado:
 *  - "Resumo do dia" (seção 15) ao clicar um dia na visão mensal — `groupByBucket`.
 *  - "Ver todas as N" (seção 12) ao expandir um cluster de execuções simultâneas — lista simples.
 */
export function ScheduleItemsSheet({
  open,
  onClose,
  title,
  description,
  items,
  onSelect,
  groupByBucket = false,
  onCreate,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  items: ScheduleCalendarItem[];
  onSelect: (item: ScheduleCalendarItem) => void;
  groupByBucket?: boolean;
  onCreate?: () => void;
}) {
  if (!open) return null;

  const sorted = [...items].sort((a, b) => a.planned_start.localeCompare(b.planned_start));

  const content = groupByBucket ? (
    <>
      <BucketSection label="Em andamento" items={sorted.filter((i) => temporalBucket(i.temporal_status) === "present")} onSelect={onSelect} />
      <BucketSection label="Passados" items={sorted.filter((i) => temporalBucket(i.temporal_status) === "past")} onSelect={onSelect} />
      <BucketSection label="Futuros" items={sorted.filter((i) => temporalBucket(i.temporal_status) === "future")} onSelect={onSelect} />
    </>
  ) : (
    <div className="divide-y divide-border/60 overflow-hidden rounded-lg border border-border">
      {sorted.map((item) => (
        <ScheduleItemRow key={item.id} item={item} onClick={() => onSelect(item)} />
      ))}
    </div>
  );

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={title}
      description={description}
      widthClassName="w-full sm:max-w-lg"
      footer={
        onCreate && (
          <Button variant="outline" size="sm" onClick={onCreate}>
            <Plus className="h-3.5 w-3.5" /> Criar agendamento neste dia
          </Button>
        )
      }
    >
      {sorted.length === 0 ? (
        <EmptyState title="Nenhuma ocorrência" description="Nada programado para este dia ainda." />
      ) : (
        <div className="space-y-5">{content}</div>
      )}
    </Sheet>
  );
}

function BucketSection({ label, items, onSelect }: { label: string; items: ScheduleCalendarItem[]; onSelect: (item: ScheduleCalendarItem) => void }) {
  if (items.length === 0) return null;
  return (
    <section className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label} ({items.length})
      </h3>
      <div className="divide-y divide-border/60 overflow-hidden rounded-lg border border-border">
        {items.map((item) => (
          <ScheduleItemRow key={item.id} item={item} onClick={() => onSelect(item)} />
        ))}
      </div>
    </section>
  );
}
