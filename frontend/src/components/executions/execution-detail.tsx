"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Ban, ExternalLink, RotateCw, Wifi, WifiOff } from "lucide-react";

import { DetailJson } from "@/components/shared/detail-json";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { SectionCard } from "@/components/shared/section-card";
import { TimelineTab } from "@/components/flows/execution/timeline-tab";
import { MetricsTab } from "@/components/flows/execution/metrics-tab";
import { ArtifactsTab } from "@/components/flows/execution/artifacts-tab";
import { AttemptsTab } from "@/components/flows/execution/attempts-tab";
import { DispatchDiagnosticsTab } from "@/components/executions/dispatch-diagnostics-tab";
import { ExecutionLogViewer } from "@/components/executions/execution-log-viewer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { API_BASE_URL } from "@/lib/constants";
import { EVENT_TYPE_LABELS, eventTypeLabel, executionLifecycleStatus, executionOriginLabel, executionTypeLabel, isExecutionActiveStatus } from "@/lib/status";
import { formatDateTime, formatDuration } from "@/lib/utils";
import type {
  Execution,
  ExecutionArtifact,
  ExecutionDetails,
  ExecutionEventsPage,
  ExecutionMetric,
  ExecutionProcess,
  ExecutionProgress,
} from "@/types/execution";
import type { FlowExecution, FlowExecutionDetails } from "@/types/flow";

export function ExecutionDetail({ id }: { id: string }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const tab = searchParams.get("tab") ?? "resumo";
  const eventType = searchParams.get("event_type") ?? "";
  const eventLevel = searchParams.get("event_level") ?? "";
  const logLevel = searchParams.get("log_level") ?? "";
  const metricName = searchParams.get("metric_name") ?? "";
  const taskFilter = searchParams.get("task") ?? "";

  const [terminal, setTerminal] = useState(false);
  const [sseConnected, setSseConnected] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<number | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [retryingTaskId, setRetryingTaskId] = useState<string | null>(null);

  const details = useApi<ExecutionDetails | Execution>(`/executions/${id}`, { pollMs: terminal ? undefined : 4000 });
  const normalized = details.data ? normalizeDetails(details.data) : null;
  const execution = normalized?.execution ?? null;
  const status = execution ? executionLifecycleStatus(execution) : "pending";
  const active = isExecutionActiveStatus(status);

  useEffect(() => {
    if (!execution) return;
    setTerminal(!isExecutionActiveStatus(executionLifecycleStatus(execution)));
    setLastRefreshedAt(Date.now());
  }, [execution]);

  const tasks = useApi<ExecutionDetails["tasks"]>(`/executions/${id}/tasks`, { pollMs: terminal ? undefined : 4000 });
  const attempts = useApi<ExecutionDetails["attempts"]>(`/executions/${id}/attempts`, { pollMs: terminal ? undefined : 4000 });
  const timeline = useApi<ExecutionEventsPage>(`/executions/${id}/timeline?limit=500`, { pollMs: terminal ? undefined : 5000 });
  const events = useApi<ExecutionEventsPage>(eventsPath(id, eventType, eventLevel), { pollMs: terminal ? undefined : 5000 });
  const logs = useApi<ExecutionEventsPage>(logsPath(id, logLevel), { pollMs: terminal ? undefined : 5000 });
  const metrics = useApi<ExecutionMetric[]>(metricsPath(id, metricName), { pollMs: terminal ? undefined : 8000 });
  const progress = useApi<ExecutionProgress>(`/executions/${id}/progress`, { pollMs: terminal ? undefined : 4000 });
  const processes = useApi<ExecutionProcess[]>(`/executions/${id}/processes`, { pollMs: terminal ? undefined : 8000 });
  const artifacts = useApi<ExecutionArtifact[]>(`/executions/${id}/artifacts`, { pollMs: terminal ? undefined : 8000 });

  const shouldLoadFlowLinks = Boolean(execution && (execution.type === "flow" || tasks.data?.some((task) => stringFromRecord(task.input, "flow_execution_id"))));
  const flowExecutions = useApi<FlowExecution[]>(shouldLoadFlowLinks ? "/flow-executions?limit=500" : null, { enabled: shouldLoadFlowLinks });
  const flowExecution = useMemo(() => {
    if (!flowExecutions.data) return null;
    const taskFlowIds = new Set((tasks.data ?? []).map((task) => stringFromRecord(task.input, "flow_execution_id")).filter(Boolean));
    return flowExecutions.data.find((item) => item.execution_id === id || taskFlowIds.has(item.id)) ?? null;
  }, [flowExecutions.data, tasks.data, id]);
  const flowDetails = useApi<FlowExecutionDetails>(flowExecution ? `/flow-executions/${flowExecution.id}` : null, { enabled: !!flowExecution });

  const nodeLabelByTask = useMemo(() => {
    const map = new Map<string, string>();
    if (flowDetails.data) {
      flowDetails.data.node_executions.forEach((nodeExecution) => {
        if (!nodeExecution.task_execution_id) return;
        const node = flowDetails.data!.nodes.find((item) => item.id === nodeExecution.flow_node_id);
        map.set(nodeExecution.task_execution_id, node?.name || node?.key || `No ${nodeExecution.flow_node_id.slice(0, 8)}`);
      });
    }
    (tasks.data ?? []).forEach((task) => {
      if (map.has(task.id)) return;
      const nodeId = stringFromRecord(task.input, "flow_node_id");
      if (nodeId) map.set(task.id, `No ${nodeId.slice(0, 8)}`);
    });
    return map;
  }, [flowDetails.data, tasks.data]);

  const agentLabelById = useMemo(() => {
    const map = new Map<string, string>();
    const agent = normalized?.agent as { id?: string; name?: string } | null | undefined;
    if (agent?.id && agent.name) map.set(agent.id, agent.name);
    (attempts.data ?? []).forEach((attempt) => {
      if (attempt.agent_id && !map.has(attempt.agent_id)) map.set(attempt.agent_id, `Agent ${attempt.agent_id.slice(0, 8)}`);
    });
    return map;
  }, [normalized?.agent, attempts.data]);

  function setQuery(patch: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(patch).forEach(([key, value]) => {
      if (!value) params.delete(key);
      else params.set(key, value);
    });
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  const refetchAll = () => {
    void details.refetch();
    void tasks.refetch();
    void attempts.refetch();
    void timeline.refetch();
    void events.refetch();
    void logs.refetch();
    void metrics.refetch();
    void progress.refetch();
    void processes.refetch();
    void artifacts.refetch();
    void flowExecutions.refetch();
    void flowDetails.refetch();
  };

  useEffect(() => {
    if (!token || terminal) return;
    const source = new EventSource(`${API_BASE_URL}/executions/${id}/stream?token=${encodeURIComponent(token)}`);
    const refresh = () => refetchAll();
    source.onopen = () => setSseConnected(true);
    source.addEventListener("execution.event", refresh);
    source.addEventListener("execution.summary", refresh);
    source.addEventListener("execution.progress", refresh);
    source.addEventListener("execution.update", refresh);
    source.onerror = () => setSseConnected(false);
    return () => {
      source.close();
      setSseConnected(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, token, terminal]);

  async function cancelExecution() {
    if (!token || !execution) return;
    if (!window.confirm(`Cancelar a execucao #${execution.id}?`)) return;
    setCancelling(true);
    try {
      await apiRequest(`/executions/${execution.id}/cancel`, {
        method: "POST",
        token,
        body: JSON.stringify({ reason: "Cancelado pelo Portal." }),
      });
      toast({ title: "Cancelamento solicitado", kind: "success" });
      refetchAll();
    } catch (err) {
      toast({ title: "Falha ao cancelar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setCancelling(false);
    }
  }

  async function retryTask(taskId: string, sourceAttemptId?: string | null) {
    if (!token) return;
    setRetryingTaskId(taskId);
    try {
      await apiRequest(`/task-executions/${taskId}/retry`, {
        method: "POST",
        token,
        body: JSON.stringify({
          source_attempt_id: sourceAttemptId || undefined,
          reason: "Retry solicitado pelo Portal.",
        }),
      });
      toast({ title: "Retry agendado", description: `Task ${taskId.slice(0, 8)}`, kind: "success" });
      refetchAll();
    } catch (err) {
      toast({ title: "Falha ao reagendar task", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setRetryingTaskId(null);
    }
  }

  if (details.error) return <ErrorState message={details.error} onRetry={details.refetch} />;
  if (details.loading || !normalized || !execution) return <Skeleton className="h-64 rounded-lg" />;

  const telemetry = normalized.telemetry ?? execution.telemetry ?? null;
  const finishedAt = executionFinishedAt(execution);
  const duration = durationBetween(execution.started_at, finishedAt);
  const flowId = flowDetails.data?.flow_version?.flow_id ?? execution.flow_id ?? null;
  const flowNodeLinks = flowNodeLinksFor(tasks.data ?? [], flowExecution?.id ?? execution.flow_execution_id ?? null, nodeLabelByTask);
  const logItems = (logs.data?.items ?? []).map((event) => ({
    id: event.id,
    level: event.level ?? "INFO",
    message: event.message ?? String(event.payload?.message ?? ""),
    created_at: event.received_at ?? event.occurred_at,
  }));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={status} />
          <Badge tone="outline">{executionTypeLabel(execution.type)}</Badge>
          <Badge tone="outline">{execution.type === "flow" ? "Fluxo" : executionOriginLabel(execution.origin)}</Badge>
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            {sseConnected ? <Wifi className="h-3.5 w-3.5 text-success" /> : <WifiOff className="h-3.5 w-3.5" />}
            {terminal ? "encerrada" : "ao vivo"}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {flowExecution && (
            <Button size="sm" variant="outline" asChild>
              <Link href={`/flow-executions/${flowExecution.id}`}>
                <ExternalLink className="h-3.5 w-3.5" /> Monitor do Flow
              </Link>
            </Button>
          )}
          <Button size="sm" variant="outline" onClick={refetchAll}>
            <RotateCw className="h-3.5 w-3.5" /> Atualizar
          </Button>
          {active && (
            <Button size="sm" variant="destructive" onClick={cancelExecution} disabled={cancelling}>
              <Ban className="h-3.5 w-3.5" /> {cancelling ? "Cancelando..." : "Cancelar"}
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="Progresso" value={progressLabel(progress.data, telemetry?.progress_percentage)} hint={progress.data?.message ?? "Telemetria estruturada"} />
        <Metric label="Eventos" value={telemetry?.event_count ?? timeline.data?.items.length ?? 0} hint={`${telemetry?.log_count ?? logItems.length} logs`} />
        <Metric label="Artefatos" value={telemetry?.artifact_count ?? artifacts.data?.length ?? 0} hint={`${telemetry?.metric_count ?? metrics.data?.length ?? 0} metricas`} />
        <Metric label="Duracao" value={duration} hint={`Atualizado ${lastRefreshedAt ? formatDateTime(new Date(lastRefreshedAt).toISOString()) : "-"}`} />
      </div>

      <Tabs
        value={tab}
        onValueChange={(next) => setQuery({ tab: next === "resumo" ? null : next })}
        items={[
          { value: "resumo", label: "Resumo" },
          { value: "timeline", label: "Timeline", count: timeline.data?.items.length || undefined },
          { value: "eventos", label: "Eventos", count: events.data?.items.length || undefined },
          { value: "logs", label: "Logs", count: logItems.length || undefined },
          { value: "metricas", label: "Metricas" },
          { value: "processos", label: "Processos", count: processes.data?.length || undefined },
          { value: "progresso", label: "Progresso" },
          { value: "tentativas", label: "Tasks" },
          { value: "artefatos", label: "Artefatos", count: artifacts.data?.length || undefined },
          { value: "diagnostico", label: "Diagnóstico avançado" },
        ]}
        className="max-w-full overflow-x-auto"
      />

      {tab === "resumo" && (
        <OverviewTab
          execution={execution}
          details={normalized}
          flowExecution={flowExecution}
          flowId={flowId}
          flowNodeLinks={flowNodeLinks}
          progress={progress.data}
          duration={duration}
        />
      )}

      {tab === "timeline" && (
        <TimelineTab
          events={(timeline.data?.items ?? []).filter((event) => !taskFilter || event.task_execution_id === taskFilter)}
          loading={timeline.loading}
          error={timeline.error}
          onRetry={timeline.refetch}
          nodeLabelByTask={nodeLabelByTask}
          agentLabelById={agentLabelById}
          nodeFilter={taskFilter || null}
          onNodeFilterChange={(taskId) => setQuery({ task: taskId })}
        />
      )}

      {tab === "eventos" && (
        <EventsTab
          page={events.data}
          loading={events.loading}
          error={events.error}
          onRetry={events.refetch}
          eventType={eventType}
          level={eventLevel}
          onFilterChange={(patch) => setQuery(patch)}
          nodeLabelByTask={nodeLabelByTask}
          agentLabelById={agentLabelById}
        />
      )}

      {tab === "logs" && (
        <LogsTab
          logs={logItems}
          loading={logs.loading}
          error={logs.error}
          onRetry={logs.refetch}
          level={logLevel}
          onLevelChange={(level) => setQuery({ log_level: level })}
        />
      )}

      {tab === "metricas" && (
        <div className="space-y-3">
          <div className="max-w-xs">
            <Input placeholder="Filtrar metric_name" value={metricName} onChange={(event) => setQuery({ metric_name: event.target.value })} />
          </div>
          <MetricsTab metrics={metrics.data ?? []} loading={metrics.loading} error={metrics.error} onRetry={metrics.refetch} nodeLabelByTask={nodeLabelByTask} />
        </div>
      )}

      {tab === "processos" && <ProcessesTab processes={processes.data ?? []} loading={processes.loading} error={processes.error} onRetry={processes.refetch} />}

      {tab === "progresso" && <ProgressTab progress={progress.data} loading={progress.loading} error={progress.error} onRetry={progress.refetch} />}

      {tab === "tentativas" && (
        <AttemptsTab
          tasks={tasks.data ?? normalized.tasks}
          attempts={attempts.data ?? normalized.attempts}
          loading={tasks.loading}
          error={tasks.error}
          onRetry={tasks.refetch}
          nodeLabelByTask={nodeLabelByTask}
          agentLabelById={agentLabelById}
          onRetryTask={(taskId, sourceAttemptId) => void retryTask(taskId, sourceAttemptId)}
          retryingTaskId={retryingTaskId}
        />
      )}

      {tab === "artefatos" && (
        <ArtifactsTab artifacts={artifacts.data ?? []} loading={artifacts.loading} error={artifacts.error} onRetry={artifacts.refetch} nodeLabelByTask={nodeLabelByTask} />
      )}

      {tab === "diagnostico" && <DispatchDiagnosticsTab executionId={String(execution.id)} attempts={attempts.data ?? normalized.attempts} />}
    </div>
  );
}

function OverviewTab({
  execution,
  details,
  flowExecution,
  flowId,
  flowNodeLinks,
  progress,
  duration,
}: {
  execution: Execution;
  details: ExecutionDetails;
  flowExecution: FlowExecution | null;
  flowId: string | null;
  flowNodeLinks: Array<{ taskId: string; nodeId: string; label: string; href: string }>;
  progress: ExecutionProgress | null;
  duration: string;
}) {
  const result = execution.result ?? execution.result_payload_json ?? details.current_attempt?.result ?? null;
  const payload = details.tasks[0]?.parameters ?? execution.input ?? {};
  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div className="space-y-5 lg:col-span-2">
        <SectionCard title="Entrada">
          <DetailJson data={payload} />
        </SectionCard>
        {result && (
          <SectionCard title="Saida">
            <DetailJson data={result} />
          </SectionCard>
        )}
        {execution.failure_summary && (
          <SectionCard title="Falha">
            <p className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{execution.failure_summary}</p>
          </SectionCard>
        )}
      </div>

      <div className="space-y-5">
        <SectionCard title="Execucao">
          <div className="space-y-3">
            <InfoRow label="Status" value={<StatusBadge status={executionLifecycleStatus(execution)} />} />
            <InfoRow label="Tipo" value={<span className="text-sm">{executionTypeLabel(execution.type)}</span>} />
            <InfoRow label="Origem" value={<span className="text-sm">{executionOriginLabel(execution.origin)}</span>} />
            <InfoRow label="Criada" value={<span className="tabular text-sm">{formatDateTime(execution.created_at)}</span>} />
            <InfoRow label="Inicio" value={<span className="tabular text-sm">{formatDateTime(execution.started_at)}</span>} />
            <InfoRow label="Termino" value={<span className="tabular text-sm">{formatDateTime(executionFinishedAt(execution))}</span>} />
            <InfoRow label="Duracao" value={<span className="tabular text-sm">{duration}</span>} />
          </div>
        </SectionCard>

        {(flowExecution || flowId || flowNodeLinks.length > 0) && (
          <SectionCard title="Fluxo de origem">
            <div className="space-y-3">
              {flowExecution && (
                <InfoRow
                  label="Monitor"
                  value={
                    <Link href={`/flow-executions/${flowExecution.id}`} className="text-sm font-medium text-primary hover:underline">
                      {flowExecution.id}
                    </Link>
                  }
                />
              )}
              {flowId && (
                <InfoRow
                  label="Fluxo"
                  value={
                    <Link href={`/flows/${flowId}`} className="text-sm font-medium text-primary hover:underline">
                      {flowId}
                    </Link>
                  }
                />
              )}
              {flowNodeLinks.length > 0 && (
                <div className="border-t border-border pt-3">
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Nos</p>
                  <div className="flex flex-wrap gap-2">
                    {flowNodeLinks.map((item) => (
                      <Link key={item.taskId} href={item.href} className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary hover:bg-primary/15">
                        {item.label}
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </SectionCard>
        )}

        <SectionCard title="Progresso">
          <div className="space-y-3">
            <InfoRow label="Percentual" value={<span className="tabular text-sm">{progressLabel(progress, execution.telemetry?.progress_percentage)}</span>} />
            <InfoRow label="Atual" value={<span className="tabular text-sm">{progress?.current ?? "-"}</span>} />
            <InfoRow label="Total" value={<span className="tabular text-sm">{progress?.total ?? "-"}</span>} />
            {progress?.message && <p className="border-t border-border pt-3 text-sm text-muted-foreground">{progress.message}</p>}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}

function EventsTab({
  page,
  loading,
  error,
  onRetry,
  eventType,
  level,
  onFilterChange,
  nodeLabelByTask,
  agentLabelById,
}: {
  page: ExecutionEventsPage | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  eventType: string;
  level: string;
  onFilterChange: (patch: Record<string, string | null>) => void;
  nodeLabelByTask: Map<string, string>;
  agentLabelById: Map<string, string>;
}) {
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (loading) return <Skeleton className="h-40 rounded-lg" />;
  const items = page?.items ?? [];
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Select className="w-64" value={eventType} onChange={(event) => onFilterChange({ event_type: event.target.value })}>
          <option value="">Todos os eventos</option>
          {Object.entries(EVENT_TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
        <Select className="w-44" value={level} onChange={(event) => onFilterChange({ event_level: event.target.value })}>
          <option value="">Todos os niveis</option>
          <option value="DEBUG">Debug</option>
          <option value="INFO">Info</option>
          <option value="WARNING">Warning</option>
          <option value="ERROR">Error</option>
          <option value="CRITICAL">Critical</option>
        </Select>
      </div>
      {items.length === 0 ? (
        <EmptyState title="Nenhum evento" description="Nenhum evento estruturado corresponde aos filtros atuais." />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <Table>
            <THead>
              <TR>
                <TH>Evento</TH>
                <TH>Nivel</TH>
                <TH>Task</TH>
                <TH>Agent</TH>
                <TH>Quando</TH>
                <TH>Mensagem</TH>
              </TR>
            </THead>
            <TBody>
              {items.map((item) => (
                <TR key={item.id}>
                  <TD className="text-sm font-medium">{eventTypeLabel(item.event_type)}</TD>
                  <TD className="tabular text-xs text-muted-foreground">{item.level ?? "-"}</TD>
                  <TD className="text-sm text-muted-foreground">{item.task_execution_id ? nodeLabelByTask.get(item.task_execution_id) ?? item.task_execution_id.slice(0, 8) : "-"}</TD>
                  <TD className="text-sm text-muted-foreground">{item.agent_id ? agentLabelById.get(item.agent_id) ?? `Agent ${item.agent_id.slice(0, 8)}` : "-"}</TD>
                  <TD className="tabular text-sm text-muted-foreground">{formatDateTime(item.occurred_at)}</TD>
                  <TD className="max-w-[320px] truncate text-sm text-muted-foreground">{item.message ?? String(item.payload?.message ?? "-")}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
          {page?.next_cursor && <p className="border-t border-border px-4 py-2 text-xs text-muted-foreground">Ha mais eventos disponiveis via cursor.</p>}
        </div>
      )}
    </div>
  );
}

function LogsTab({
  logs,
  loading,
  error,
  onRetry,
  level,
  onLevelChange,
}: {
  logs: Array<{ id: string | number; level: string; message: string; created_at: string }>;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  level: string;
  onLevelChange: (level: string | null) => void;
}) {
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (loading) return <Skeleton className="h-64 rounded-lg" />;
  return (
    <div className="space-y-3">
      <Select className="w-44" value={level} onChange={(event) => onLevelChange(event.target.value)}>
        <option value="">Todos os niveis</option>
        <option value="DEBUG">Debug</option>
        <option value="INFO">Info</option>
        <option value="WARNING">Warning</option>
        <option value="ERROR">Error</option>
        <option value="CRITICAL">Critical</option>
      </Select>
      {logs.length === 0 ? <EmptyState title="Sem logs" description="Esta execucao ainda nao registrou logs estruturados." /> : <ExecutionLogViewer logs={logs} />}
    </div>
  );
}

function ProcessesTab({
  processes,
  loading,
  error,
  onRetry,
}: {
  processes: ExecutionProcess[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (loading) return <Skeleton className="h-40 rounded-lg" />;
  if (processes.length === 0) return <EmptyState title="Sem processos" description="Nenhum processo foi reportado pela telemetria." />;
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <Table>
        <THead>
          <TR>
            <TH>Processo</TH>
            <TH>Status</TH>
            <TH>PID</TH>
            <TH>Exit</TH>
            <TH>Inicio</TH>
            <TH>Fim</TH>
            <TH>Comando</TH>
          </TR>
        </THead>
        <TBody>
          {processes.map((process) => (
            <TR key={process.process_id}>
              <TD className="font-medium">{process.name ?? process.process_id}</TD>
              <TD>
                <StatusBadge status={process.status} />
              </TD>
              <TD className="tabular text-sm text-muted-foreground">{process.pid ?? "-"}</TD>
              <TD className="tabular text-sm text-muted-foreground">{process.exit_code ?? "-"}</TD>
              <TD className="tabular text-sm text-muted-foreground">{formatDateTime(process.started_at)}</TD>
              <TD className="tabular text-sm text-muted-foreground">{formatDateTime(process.exited_at)}</TD>
              <TD className="max-w-[320px] truncate text-sm text-muted-foreground">{process.command ?? "-"}</TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}

function ProgressTab({
  progress,
  loading,
  error,
  onRetry,
}: {
  progress: ExecutionProgress | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (loading) return <Skeleton className="h-40 rounded-lg" />;
  if (!progress) return <EmptyState title="Sem progresso" description="Nenhum evento task.progress foi recebido." />;
  return (
    <section className="space-y-4 rounded-lg border border-border bg-card p-5">
      <div>
        <h2 className="font-display text-base font-semibold tracking-tight">Progresso estruturado</h2>
        <p className="mt-0.5 text-sm text-muted-foreground">Ultimo evento task.progress recebido para esta execucao.</p>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div className="h-full bg-primary transition-all" style={{ width: `${Math.max(0, Math.min(100, progress.percentage ?? 0))}%` }} />
      </div>
      <div className="grid gap-3 sm:grid-cols-4">
        <ProgressCell label="Percentual" value={progressLabel(progress, null)} />
        <ProgressCell label="Atual" value={progress.current ?? "-"} />
        <ProgressCell label="Total" value={progress.total ?? "-"} />
        <ProgressCell label="Atualizado" value={formatDateTime(progress.updated_at)} />
      </div>
      {progress.message && <p className="text-sm text-muted-foreground">{progress.message}</p>}
    </section>
  );
}

function ProgressCell({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="tabular mt-1 text-lg font-semibold">{value}</p>
    </div>
  );
}

function Metric({ label, value, hint }: { label: string; value: string | number; hint: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="tabular mt-2 text-2xl font-semibold">{value}</p>
      <p className="mt-1 truncate text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm text-muted-foreground">{label}</span>
      {value}
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

function executionFinishedAt(execution: Execution): string | null {
  return execution.finished_at ?? execution.completed_at ?? null;
}

function durationBetween(start?: string | null, end?: string | null): string {
  if (!start) return "-";
  const startMs = new Date(start).getTime();
  const endMs = end ? new Date(end).getTime() : Date.now();
  if (Number.isNaN(startMs) || Number.isNaN(endMs) || endMs < startMs) return "-";
  return formatDuration((endMs - startMs) / 1000);
}

function progressLabel(progress: ExecutionProgress | null, fallback?: number | null): string {
  const value = progress?.percentage ?? fallback;
  return typeof value === "number" ? `${Math.round(value)}%` : "-";
}

function stringFromRecord(record: Record<string, unknown> | null | undefined, key: string): string | null {
  const value = record?.[key];
  return typeof value === "string" && value ? value : null;
}

function flowNodeLinksFor(
  tasks: ExecutionDetails["tasks"],
  flowExecutionId: string | null,
  nodeLabelByTask: Map<string, string>,
): Array<{ taskId: string; nodeId: string; label: string; href: string }> {
  if (!flowExecutionId) return [];
  return tasks
    .map((task) => {
      const nodeId = stringFromRecord(task.input, "flow_node_id");
      if (!nodeId) return null;
      return {
        taskId: task.id,
        nodeId,
        label: nodeLabelByTask.get(task.id) ?? `No ${nodeId.slice(0, 8)}`,
        href: `/flow-executions/${flowExecutionId}?node=${encodeURIComponent(nodeId)}`,
      };
    })
    .filter((item): item is { taskId: string; nodeId: string; label: string; href: string } => item !== null);
}

function eventsPath(executionId: string, eventType: string, level: string): string {
  const params = new URLSearchParams({ limit: "300" });
  if (eventType) params.set("event_type", eventType);
  if (level) params.set("level", level);
  return `/executions/${executionId}/events?${params.toString()}`;
}

function logsPath(executionId: string, level: string): string {
  const params = new URLSearchParams({ limit: "300" });
  if (level) params.set("level", level);
  return `/executions/${executionId}/logs?${params.toString()}`;
}

function metricsPath(executionId: string, metricName: string): string {
  const params = new URLSearchParams({ limit: "500" });
  if (metricName) params.set("metric_name", metricName);
  return `/executions/${executionId}/metrics?${params.toString()}`;
}
