"use client";

import { CalendarClock } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { describeCron } from "@/lib/cron";
import type { Schedule } from "@/types/schedule";
import type { Automation } from "@/types/automation";

export function SchedulesManager() {
  const schedules = useApi<Schedule[]>("/schedules");
  const automations = useApi<Automation[]>("/automations");

  if (schedules.error) return <ErrorState message={schedules.error} onRetry={schedules.refetch} />;
  if (schedules.loading)
    return (
      <div className="grid gap-4 md:grid-cols-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <Skeleton key={i} className="h-28 rounded-lg" />
        ))}
      </div>
    );
  const list = schedules.data ?? [];
  if (list.length === 0)
    return <EmptyState icon={CalendarClock} title="Sem agendamentos" description="Nenhum schedule cadastrado." />;

  const nameOf = (id: number) => automations.data?.find((a) => a.id === id)?.name ?? `Automação #${id}`;

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {list.map((s) => (
        <Card key={s.id} className="p-5">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="truncate font-display text-base font-semibold">{nameOf(s.automation_id)}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{describeCron(s.cron_expression)}</p>
            </div>
            <Badge tone={s.is_active ? "success" : "neutral"}>{s.is_active ? "Ativo" : "Inativo"}</Badge>
          </div>
          <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
            <code className="tabular rounded bg-muted px-2 py-1 text-xs">{s.cron_expression}</code>
            <span className="text-xs text-muted-foreground">{s.timezone}</span>
          </div>
        </Card>
      ))}
    </div>
  );
}
