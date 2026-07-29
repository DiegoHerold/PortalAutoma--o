"use client";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { formatDateTime } from "@/lib/utils";
import type { ExecutionMetric } from "@/types/execution";

export function MetricsTab({
  metrics,
  loading,
  error,
  onRetry,
  nodeLabelByTask,
}: {
  metrics: ExecutionMetric[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  nodeLabelByTask: Map<string, string>;
}) {
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (loading) return <Skeleton className="h-40 rounded-lg" />;
  if (metrics.length === 0) {
    return <EmptyState title="Sem métricas" description="Nenhuma automação deste Fluxo reportou métricas até agora." />;
  }

  const sorted = [...metrics].sort((a, b) => b.occurred_at.localeCompare(a.occurred_at));

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <Table>
        <THead>
          <TR>
            <TH>Métrica</TH>
            <TH>Nó</TH>
            <TH>Valor</TH>
            <TH>Tipo</TH>
            <TH>Quando</TH>
          </TR>
        </THead>
        <TBody>
          {sorted.map((m) => (
            <TR key={m.id}>
              <TD className="font-medium">{m.metric_name}</TD>
              <TD className="text-sm text-muted-foreground">{nodeLabelByTask.get(m.task_execution_id) ?? "—"}</TD>
              <TD className="tabular text-sm">
                {m.value}
                {m.unit ? ` ${m.unit}` : ""}
              </TD>
              <TD className="text-sm text-muted-foreground">{m.metric_type}</TD>
              <TD className="text-sm text-muted-foreground">{formatDateTime(m.occurred_at)}</TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}
