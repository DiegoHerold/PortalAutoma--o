"use client";

import { useEffect } from "react";

import { SectionCard } from "@/components/shared/section-card";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { DetailJson } from "@/components/shared/detail-json";
import { ExecutionTimeline } from "@/components/executions/execution-timeline";
import { ExecutionLogViewer } from "@/components/executions/execution-log-viewer";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { API_BASE_URL } from "@/lib/constants";
import { formatDuration } from "@/lib/utils";
import type { Execution, ExecutionDetails, ExecutionDispatchInfo, ExecutionEventsPage, ExecutionLeaseInfo, ExecutionLogEntry } from "@/types/execution";

export function ExecutionDetail({ id }: { id: string }) {
  const execution = useApi<ExecutionDetails | Execution>(`/executions/${id}`, { pollMs: 4000 });
  const logs = useApi<ExecutionEventsPage>(`/executions/${id}/logs`, { pollMs: 4000 });
  const dispatch = useApi<ExecutionDispatchInfo>(`/executions/${id}/dispatch`, { pollMs: 4000 });
  const { token } = useAuth();
  const currentDetails = execution.data ? normalizeDetails(execution.data) : null;
  const currentAttemptId = currentDetails?.current_attempt?.id ?? null;
  const lease = useApi<ExecutionLeaseInfo>(currentAttemptId ? `/execution-attempts/${currentAttemptId}/lease` : null, {
    pollMs: 4000,
    enabled: !!currentAttemptId,
  });

  useEffect(() => {
    if (!token) return;
    const source = new EventSource(`${API_BASE_URL}/executions/${id}/stream?token=${encodeURIComponent(token)}`);
    const refetch = () => {
      void execution.refetch();
      void logs.refetch();
      void dispatch.refetch();
      void lease.refetch();
    };
    source.addEventListener("execution.event", refetch);
    source.addEventListener("execution.summary", refetch);
    source.addEventListener("execution.progress", refetch);
    source.onerror = () => source.close();
    return () => source.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, token]);

  if (execution.error) return <ErrorState message={execution.error} onRetry={execution.refetch} />;
  if (execution.loading || !execution.data) return <Skeleton className="h-64 rounded-lg" />;

  const details = normalizeDetails(execution.data);
  const ex = details.execution;
  const status = executionStatus(ex);
  const finishedAt = executionFinishedAt(ex);
  const started = ex.started_at ? new Date(ex.started_at).getTime() : null;
  const finished = finishedAt ? new Date(finishedAt).getTime() : null;
  const duration = started && finished ? (finished - started) / 1000 : null;
  const logItems = normalizeLogs(logs.data, ex.logs);
  const result = ex.result ?? ex.result_payload_json ?? details.current_attempt?.result ?? null;
  const summary = ex.result_summary ?? ex.failure_summary ?? details.current_attempt?.error_message ?? null;
  const jobId = ex.job_id ?? ex.legacy_job_id ?? null;
  const workerId = ex.worker_id ?? numberFromRecord(details.agent, "worker_id");
  const latestDecision = dispatch.data?.decisions?.[0] ?? null;
  const latestLease = lease.data?.lease ?? null;

  const steps = [
    { key: "created", label: "Execução criada", at: ex.created_at ?? ex.started_at, done: true },
    { key: "running", label: "Em execução", at: ex.started_at, done: !!started, current: !!started && !finished },
    {
      key: "finished",
      label: ["failed", "timed_out"].includes(status) ? "Falhou" : status === "cancelled" ? "Cancelada" : "Finalizada",
      at: finishedAt,
      done: !!finished,
      failed: ["failed", "timed_out"].includes(status),
    },
  ];

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <SectionCard title="Logs de execução">
          {logItems.length > 0 ? (
            <ExecutionLogViewer logs={logItems} />
          ) : (
            <EmptyState title="Sem logs" description="Esta execução não registrou logs." />
          )}
        </SectionCard>

        {result && (
          <SectionCard title="Resultado">
            <DetailJson data={result} />
          </SectionCard>
        )}
      </div>

      <div className="space-y-6">
        <SectionCard title="Status">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Situação</span>
              <StatusBadge status={status} />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Job</span>
              <span className="tabular text-sm font-medium">{jobId ? `#${jobId}` : "—"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Worker</span>
              <span className="tabular text-sm font-medium">{workerId ? `#${workerId}` : "—"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Duração</span>
              <span className="tabular text-sm font-medium">{formatDuration(duration)}</span>
            </div>
            {details.telemetry && (
              <div className="grid grid-cols-3 gap-2 border-t border-border pt-3 text-center">
                <TelemetryCount label="Eventos" value={details.telemetry.event_count ?? 0} />
                <TelemetryCount label="Logs" value={details.telemetry.log_count ?? 0} />
                <TelemetryCount label="Arquivos" value={details.telemetry.artifact_count ?? 0} />
              </div>
            )}
            {summary && <p className="border-t border-border pt-3 text-sm text-muted-foreground">{summary}</p>}
          </div>
        </SectionCard>

        <SectionCard title="Linha do tempo">
          <ExecutionTimeline steps={steps} />
        </SectionCard>

        <SectionCard title="Dispatch">
          <div className="space-y-3">
            <Row label="Agent" value={<span className="tabular text-sm">{latestDecision?.selected_agent_id ?? details.current_attempt?.agent_id ?? "aguardando"}</span>} />
            <Row label="Score" value={<span className="tabular text-sm">{formatScore(latestDecision)}</span>} />
            <Row label="Tentativa" value={<span className="tabular text-sm">{details.current_attempt ? `#${details.current_attempt.attempt_number}` : "—"}</span>} />
            <Row label="Lease" value={<span className="tabular text-sm">{latestLease ? latestLease.status : "—"}</span>} />
            {latestDecision?.decision_reason && <p className="border-t border-border pt-3 text-xs text-muted-foreground">{latestDecision.decision_reason}</p>}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}

function TelemetryCount({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="tabular text-sm font-semibold">{value}</p>
      <p className="truncate text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

function normalizeDetails(payload: ExecutionDetails | Execution): ExecutionDetails {
  if ("execution" in payload) return payload;
  return {
    execution: payload,
    tasks: [],
    attempts: [],
    current_attempt: null,
    current_offer: null,
    agent: null,
    automation_version: null,
    telemetry: payload.telemetry ?? null,
  };
}

function normalizeLogs(page: ExecutionEventsPage | null, fallback?: ExecutionLogEntry[]): ExecutionLogEntry[] {
  if (page?.items) {
    return page.items.map((item) => ({
      id: item.id,
      level: item.level ?? "INFO",
      message: item.message ?? String(item.payload?.message ?? ""),
      created_at: item.received_at ?? item.occurred_at,
    }));
  }
  return fallback ?? [];
}

function executionStatus(execution: Execution): string {
  return execution.execution_status ?? execution.status ?? "pending";
}

function executionFinishedAt(execution: Execution): string | null {
  return execution.finished_at ?? execution.completed_at ?? null;
}

function numberFromRecord(record: Record<string, unknown> | null | undefined, key: string): number | null {
  const value = record?.[key];
  return typeof value === "number" ? value : null;
}

function formatScore(decision: ExecutionDispatchInfo["decisions"][number] | null): string {
  const selected = decision?.candidates?.find((candidate) => candidate.agent_id === decision.selected_agent_id);
  return typeof selected?.score === "number" ? selected.score.toFixed(1) : "—";
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm text-muted-foreground">{label}</span>
      {value}
    </div>
  );
}
