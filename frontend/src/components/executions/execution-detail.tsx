"use client";

import { SectionCard } from "@/components/shared/section-card";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { DetailJson } from "@/components/shared/detail-json";
import { ExecutionTimeline } from "@/components/executions/execution-timeline";
import { ExecutionLogViewer } from "@/components/executions/execution-log-viewer";
import { useApi } from "@/hooks/use-api";
import { formatDuration } from "@/lib/utils";
import type { Execution } from "@/types/execution";

export function ExecutionDetail({ id }: { id: string }) {
  const execution = useApi<Execution>(`/executions/${id}`, { pollMs: 4000 });

  if (execution.error) return <ErrorState message={execution.error} onRetry={execution.refetch} />;
  if (execution.loading || !execution.data) return <Skeleton className="h-64 rounded-lg" />;

  const ex = execution.data;
  const started = ex.started_at ? new Date(ex.started_at).getTime() : null;
  const finished = ex.finished_at ? new Date(ex.finished_at).getTime() : null;
  const duration = started && finished ? (finished - started) / 1000 : null;

  const steps = [
    { key: "created", label: "Job criado", at: ex.started_at, done: true },
    { key: "running", label: "Em execução", at: ex.started_at, done: !!started, current: !!started && !finished },
    {
      key: "finished",
      label: ex.execution_status === "failed" ? "Falhou" : "Finalizado",
      at: ex.finished_at,
      done: !!finished,
      failed: ex.execution_status === "failed",
    },
  ];

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <SectionCard title="Logs de execução">
          {ex.logs && ex.logs.length > 0 ? (
            <ExecutionLogViewer logs={ex.logs} />
          ) : (
            <EmptyState title="Sem logs" description="Esta execução não registrou logs." />
          )}
        </SectionCard>

        {ex.result_payload_json && (
          <SectionCard title="Resultado">
            <DetailJson data={ex.result_payload_json} />
          </SectionCard>
        )}
      </div>

      <div className="space-y-6">
        <SectionCard title="Status">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Situação</span>
              <StatusBadge status={ex.execution_status} />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Job</span>
              <span className="tabular text-sm font-medium">#{ex.job_id}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Worker</span>
              <span className="tabular text-sm font-medium">{ex.worker_id ? `#${ex.worker_id}` : "—"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Duração</span>
              <span className="tabular text-sm font-medium">{formatDuration(duration)}</span>
            </div>
            {ex.result_summary && (
              <p className="border-t border-border pt-3 text-sm text-muted-foreground">{ex.result_summary}</p>
            )}
          </div>
        </SectionCard>

        <SectionCard title="Linha do tempo">
          <ExecutionTimeline steps={steps} />
        </SectionCard>
      </div>
    </div>
  );
}
