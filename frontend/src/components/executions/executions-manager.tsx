"use client";

import { useEffect, useMemo, useState, type ComponentType } from "react";
import Link from "next/link";
import { Activity, CheckCircle2, History, Search, Timer, XCircle } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { useRealtimeStatus } from "@/components/layout/realtime-provider";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { useApi } from "@/hooks/use-api";
import { useRealtime } from "@/hooks/use-realtime";
import { formatDateTime, formatDuration } from "@/lib/utils";
import type { Execution } from "@/types/execution";

const POLL = 5000;
const FILTERS = ["active", "all", "success", "failed"] as const;
type Filter = (typeof FILTERS)[number];

export function ExecutionsManager() {
  const executions = useApi<Execution[]>("/executions", { pollMs: POLL });
  const { setState } = useRealtimeStatus();
  const [filter, setFilter] = useState<Filter>("active");
  const [query, setQuery] = useState("");

  const { state } = useRealtime<Execution>({
    wsPath: "/ws/executions",
    onMessage: () => void executions.refetch(),
    onPoll: () => void executions.refetch(),
    pollMs: POLL,
  });
  useEffect(() => setState(state), [state, setState]);

  const list = executions.data ?? [];
  const counts = {
    active: list.filter((execution) => ["created", "pending", "queued", "running"].includes(executionStatus(execution))).length,
    running: list.filter((execution) => executionStatus(execution) === "running").length,
    success: list.filter((execution) => ["success", "succeeded"].includes(executionStatus(execution))).length,
    failed: list.filter((execution) => ["failed", "timed_out"].includes(executionStatus(execution))).length,
    all: list.length,
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const byFilter = (execution: Execution) => {
      const status = executionStatus(execution);
      if (filter === "all") return true;
      if (filter === "active") return ["created", "pending", "queued", "running"].includes(status);
      if (filter === "success") return ["success", "succeeded"].includes(status);
      return status === filter;
    };
    const byQuery = (execution: Execution) => {
      if (!q) return true;
      return [
        String(execution.id),
        String(executionJobId(execution) ?? ""),
        executionStatus(execution),
        executionSummary(execution),
        executionWorkerId(execution) ? String(executionWorkerId(execution)) : "",
      ].some((value) => value.toLowerCase().includes(q));
    };
    return [...list].filter((execution) => byFilter(execution) && byQuery(execution));
  }, [list, filter, query]);

  if (executions.error) return <ErrorState message={executions.error} onRetry={executions.refetch} />;
  if (executions.loading) return <Skeleton className="h-72 rounded-lg" />;

  if (list.length === 0) {
    return <EmptyState icon={History} title="Sem execuções" description="Nenhuma execução registrada ainda." />;
  }

  const lastFinished = list.find((execution) => executionFinishedAt(execution));

  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-4">
        <ExecutionMetric icon={Activity} label="Ativas" value={counts.active} hint={`${counts.running} em execução`} />
        <ExecutionMetric icon={CheckCircle2} label="Sucesso" value={counts.success} hint="Execuções concluídas" />
        <ExecutionMetric icon={XCircle} label="Falhas" value={counts.failed} hint="Precisam de revisão" />
        <ExecutionMetric
          icon={Timer}
          label="Última duração"
          value={lastFinished ? durationBetween(lastFinished.started_at, executionFinishedAt(lastFinished)) : "—"}
          hint={lastFinished ? `Execução #${lastFinished.id}` : "Sem histórico concluído"}
        />
      </div>

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Tabs
          value={filter}
          onValueChange={(value) => setFilter(value as Filter)}
          items={[
            { value: "active", label: "Ativas", count: counts.active },
            { value: "success", label: "Sucesso", count: counts.success },
            { value: "failed", label: "Falhas", count: counts.failed },
            { value: "all", label: "Todas", count: counts.all },
          ]}
          className="max-w-full overflow-x-auto"
        />
        <div className="relative lg:w-80">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Buscar execução, job, worker ou resumo..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon={History} title="Nada neste filtro" description="Ajuste a busca ou escolha outro status." />
      ) : (
        <div className="rounded-lg border border-border bg-card">
          <Table>
            <THead>
              <TR className="hover:bg-transparent">
                <TH>Execução</TH>
                <TH>Job</TH>
                <TH>Status</TH>
                <TH>Worker</TH>
                <TH>Duração</TH>
                <TH>Início</TH>
                <TH>Término</TH>
                <TH>Resumo</TH>
              </TR>
            </THead>
            <TBody>
              {filtered.map((execution) => (
                <TR key={execution.id}>
                  <TD>
                    <Link href={`/executions/${execution.id}`} className="tabular font-medium hover:text-primary">
                      #{execution.id}
                    </Link>
                  </TD>
                  <TD>
                    {executionJobId(execution) ? (
                      <Link href={`/jobs/${executionJobId(execution)}`} className="tabular text-sm text-muted-foreground hover:text-primary">
                        #{executionJobId(execution)}
                      </Link>
                    ) : (
                      <span className="text-sm text-muted-foreground">—</span>
                    )}
                  </TD>
                  <TD>
                    <StatusBadge status={executionStatus(execution)} />
                  </TD>
                  <TD className="tabular text-sm text-muted-foreground">
                    {executionWorkerId(execution) ? `#${executionWorkerId(execution)}` : "aguardando"}
                  </TD>
                  <TD className="tabular text-sm">{durationBetween(execution.started_at, executionFinishedAt(execution))}</TD>
                  <TD className="tabular text-sm">{formatDateTime(execution.started_at)}</TD>
                  <TD className="tabular text-sm">{formatDateTime(executionFinishedAt(execution))}</TD>
                  <TD className="max-w-[320px] truncate text-sm text-muted-foreground">
                    {executionSummary(execution) || "—"}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function ExecutionMetric({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  hint: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <p className="tabular mt-2 text-2xl font-semibold">{value}</p>
      <p className="mt-1 truncate text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

function executionStatus(execution: Execution): string {
  return execution.execution_status ?? execution.status ?? "pending";
}

function executionJobId(execution: Execution): number | null {
  return execution.job_id ?? execution.legacy_job_id ?? null;
}

function executionWorkerId(execution: Execution): number | null {
  const workerId = execution.worker_id;
  return typeof workerId === "number" ? workerId : null;
}

function executionFinishedAt(execution: Execution): string | null {
  return execution.finished_at ?? execution.completed_at ?? null;
}

function executionSummary(execution: Execution): string {
  return execution.result_summary ?? execution.failure_summary ?? "";
}

function durationBetween(start?: string | null, end?: string | null): string {
  if (!start) return "—";
  const startMs = new Date(start).getTime();
  const endMs = end ? new Date(end).getTime() : Date.now();
  if (Number.isNaN(startMs) || Number.isNaN(endMs) || endMs < startMs) return "—";
  return formatDuration((endMs - startMs) / 1000);
}
