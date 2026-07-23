"use client";

import { useEffect } from "react";
import Link from "next/link";
import { History } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { StatusBadge } from "@/components/ui/status-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { useRealtime } from "@/hooks/use-realtime";
import { useRealtimeStatus } from "@/components/layout/realtime-provider";
import { formatDateTime } from "@/lib/utils";
import type { Execution } from "@/types/execution";

const POLL = 5000;

export function ExecutionsManager() {
  const executions = useApi<Execution[]>("/executions", { pollMs: POLL });
  const { setState } = useRealtimeStatus();
  const { state } = useRealtime<Execution>({
    wsPath: "/ws/executions",
    onMessage: () => void executions.refetch(),
    onPoll: () => void executions.refetch(),
    pollMs: POLL,
  });
  useEffect(() => setState(state), [state, setState]);

  if (executions.error) return <ErrorState message={executions.error} onRetry={executions.refetch} />;
  if (executions.loading) return <Skeleton className="h-72 rounded-lg" />;
  const list = executions.data ?? [];
  if (list.length === 0)
    return <EmptyState icon={History} title="Sem execuções" description="Nenhuma execução registrada ainda." />;

  return (
    <div className="rounded-lg border border-border bg-card">
      <Table>
        <THead>
          <TR className="hover:bg-transparent">
            <TH>Execução</TH>
            <TH>Job</TH>
            <TH>Status</TH>
            <TH>Início</TH>
            <TH>Término</TH>
            <TH>Resumo</TH>
          </TR>
        </THead>
        <TBody>
          {list.map((ex) => (
            <TR key={ex.id}>
              <TD>
                <Link href={`/executions/${ex.id}`} className="tabular font-medium hover:text-primary">
                  #{ex.id}
                </Link>
              </TD>
              <TD className="tabular text-sm text-muted-foreground">#{ex.job_id}</TD>
              <TD>
                <StatusBadge status={ex.execution_status} />
              </TD>
              <TD className="tabular text-sm">{formatDateTime(ex.started_at)}</TD>
              <TD className="tabular text-sm">{formatDateTime(ex.finished_at)}</TD>
              <TD className="max-w-[280px] truncate text-sm text-muted-foreground">{ex.result_summary ?? "—"}</TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}
