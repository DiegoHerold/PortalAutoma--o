"use client";

import { useEffect, useMemo, type ComponentType } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Activity, CheckCircle2, Filter, GitBranch, History, Search, Timer, XCircle } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { useRealtimeStatus } from "@/components/layout/realtime-provider";
import { Input, Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { useApi } from "@/hooks/use-api";
import { useRealtime } from "@/hooks/use-realtime";
import { executionOriginLabel, executionTypeLabel } from "@/lib/status";
import { formatDateTime, formatDuration } from "@/lib/utils";
import type { Execution } from "@/types/execution";

const POLL = 5000;
const ACTIVE_STATUSES = new Set(["created", "pending", "ready", "queued", "offered", "accepted", "committed", "preparing", "running", "cancelling", "cancel_requested"]);
const SUCCESS_STATUSES = new Set(["success", "succeeded", "completed", "partially_succeeded"]);
const FAILURE_STATUSES = new Set(["failed", "timed_out", "lost", "rejected", "expired"]);

const STATUS_FILTERS = ["active", "all", "succeeded", "failed", "cancelled"] as const;
const SOURCE_FILTERS = ["all", "manual", "trigger", "schedule", "flow"] as const;

type StatusFilter = (typeof STATUS_FILTERS)[number];
type SourceFilter = (typeof SOURCE_FILTERS)[number];

export function ExecutionsManager() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const source = parseSourceFilter(searchParams.get("source") ?? searchParams.get("origin"));
  const triggerId = searchParams.get("trigger_id") ?? "";
  const executions = useApi<Execution[]>(executionsPath(source, triggerId), { pollMs: POLL });
  const { setState } = useRealtimeStatus();

  const status = parseStatusFilter(searchParams.get("status"));
  const query = searchParams.get("q") ?? "";
  const entity = searchParams.get("entity") ?? "";
  const from = searchParams.get("from") ?? "";
  const to = searchParams.get("to") ?? "";

  const { state } = useRealtime<Execution>({
    wsPath: "/ws/executions",
    onMessage: () => void executions.refetch(),
    onPoll: () => void executions.refetch(),
    pollMs: POLL,
  });
  useEffect(() => setState(state), [state, setState]);

  function setQuery(patch: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(patch).forEach(([key, value]) => {
      if (key === "source") params.delete("origin");
      if (!value) params.delete(key);
      else params.set(key, value);
    });
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  const list = executions.data ?? [];
  const counts = {
    active: list.filter((execution) => ACTIVE_STATUSES.has(executionStatus(execution))).length,
    running: list.filter((execution) => executionStatus(execution) === "running").length,
    succeeded: list.filter((execution) => SUCCESS_STATUSES.has(executionStatus(execution))).length,
    failed: list.filter((execution) => FAILURE_STATUSES.has(executionStatus(execution))).length,
    flow: list.filter(isFlowExecution).length,
    all: list.length,
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const entityQuery = entity.trim().toLowerCase();
    return [...list]
      .filter((execution) => matchesStatus(execution, status))
      .filter((execution) => matchesSource(execution, source))
      .filter((execution) => !triggerId || String(execution.trigger_id ?? "") === triggerId)
      .filter((execution) => matchesPeriod(execution, from, to))
      .filter((execution) => {
        if (!entityQuery) return true;
        return entityFields(execution).some((value) => value.toLowerCase().includes(entityQuery));
      })
      .filter((execution) => {
        if (!q) return true;
        return searchableFields(execution).some((value) => value.toLowerCase().includes(q));
      })
      .sort((a, b) => new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime());
  }, [list, status, source, from, to, entity, query]);

  if (executions.error) return <ErrorState message={executions.error} onRetry={executions.refetch} />;
  if (executions.loading) return <Skeleton className="h-72 rounded-lg" />;

  if (list.length === 0) {
    return <EmptyState icon={History} title="Sem execucoes" description="Nenhuma execucao registrada ainda." />;
  }

  const lastFinished = list.find((execution) => executionFinishedAt(execution));

  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-4">
        <ExecutionMetric icon={Activity} label="Ativas" value={counts.active} hint={`${counts.running} em execucao`} />
        <ExecutionMetric icon={GitBranch} label="Fluxos" value={counts.flow} hint="Execucoes originadas por Flow" />
        <ExecutionMetric icon={CheckCircle2} label="Sucesso" value={counts.succeeded} hint="Execucoes concluidas" />
        <ExecutionMetric
          icon={Timer}
          label="Ultima duracao"
          value={lastFinished ? durationBetween(lastFinished.started_at, executionFinishedAt(lastFinished)) : "-"}
          hint={lastFinished ? `Execucao #${lastFinished.id}` : "Sem historico concluido"}
        />
      </div>

      <div className="space-y-3">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <Tabs
            value={status}
            onValueChange={(value) => setQuery({ status: value === "active" ? null : value })}
            items={[
              { value: "active", label: "Ativas", count: counts.active },
              { value: "succeeded", label: "Sucesso", count: counts.succeeded },
              { value: "failed", label: "Falhas", count: counts.failed },
              { value: "cancelled", label: "Canceladas" },
              { value: "all", label: "Todas", count: counts.all },
            ]}
            className="max-w-full overflow-x-auto"
          />
          <div className="relative xl:w-80">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Buscar execucao, status, agent..."
              value={query}
              onChange={(event) => setQuery({ q: event.target.value })}
            />
          </div>
        </div>

        <div className="grid gap-2 rounded-lg border border-border bg-card p-3 md:grid-cols-5">
          <div className="md:col-span-1">
            <Select value={source} onChange={(event) => setQuery({ source: event.target.value === "all" ? null : event.target.value })}>
              <option value="all">Todas as origens</option>
              <option value="manual">Manual</option>
              <option value="trigger">Trigger</option>
              <option value="schedule">Agenda</option>
              <option value="flow">Fluxo</option>
            </Select>
          </div>
          <div className="relative md:col-span-2">
            <Filter className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Filtrar por automacao ou fluxo"
              value={entity}
              onChange={(event) => setQuery({ entity: event.target.value })}
            />
          </div>
          <Input type="date" value={from} onChange={(event) => setQuery({ from: event.target.value })} aria-label="Data inicial" />
          <Input type="date" value={to} onChange={(event) => setQuery({ to: event.target.value })} aria-label="Data final" />
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon={History} title="Nada neste filtro" description="Ajuste origem, periodo, status ou busca." />
      ) : (
        <div className="rounded-lg border border-border bg-card">
          <Table>
            <THead>
              <TR className="hover:bg-transparent">
                <TH>Execucao</TH>
                <TH>Tipo</TH>
                <TH>Origem</TH>
                <TH>Status</TH>
                <TH>Automacao / Fluxo</TH>
                <TH>Agent</TH>
                <TH>Duracao</TH>
                <TH>Inicio</TH>
                <TH>Termino</TH>
              </TR>
            </THead>
            <TBody>
              {filtered.map((execution) => {
                const flow = isFlowExecution(execution);
                return (
                  <TR key={execution.id}>
                    <TD>
                      <Link href={`/executions/${execution.id}`} className="tabular font-medium hover:text-primary">
                        #{execution.id}
                      </Link>
                    </TD>
                    <TD className="text-sm text-muted-foreground">{executionTypeLabel(flow ? "flow" : execution.type ?? "automation")}</TD>
                    <TD className="text-sm text-muted-foreground">{flow ? "Fluxo" : executionOriginLabel(execution.origin)}</TD>
                    <TD>
                      <StatusBadge status={executionStatus(execution)} />
                    </TD>
                    <TD className="max-w-[260px]">
                      <span className="block truncate text-sm font-medium">{entityLabel(execution)}</span>
                      {flow && <span className="block text-xs text-muted-foreground">Monitor de Flow disponivel no detalhe</span>}
                    </TD>
                    <TD className="text-sm text-muted-foreground">{agentLabel(execution)}</TD>
                    <TD className="tabular text-sm">{durationBetween(execution.started_at, executionFinishedAt(execution))}</TD>
                    <TD className="tabular text-sm">{formatDateTime(execution.started_at ?? execution.created_at)}</TD>
                    <TD className="tabular text-sm">{formatDateTime(executionFinishedAt(execution))}</TD>
                  </TR>
                );
              })}
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

function parseStatusFilter(value: string | null): StatusFilter {
  return STATUS_FILTERS.includes(value as StatusFilter) ? (value as StatusFilter) : "active";
}

function parseSourceFilter(value: string | null): SourceFilter {
  return SOURCE_FILTERS.includes(value as SourceFilter) ? (value as SourceFilter) : "all";
}

function executionsPath(source: SourceFilter, triggerId: string): string {
  const params = new URLSearchParams({ limit: "300" });
  if (source !== "all" && source !== "flow") params.set("origin", source === "schedule" ? "schedule" : source);
  if (triggerId) params.set("trigger_id", triggerId);
  return `/executions?${params.toString()}`;
}

function executionStatus(execution: Execution): string {
  return execution.execution_status ?? execution.status ?? "pending";
}

function executionFinishedAt(execution: Execution): string | null {
  return execution.finished_at ?? execution.completed_at ?? null;
}

function isFlowExecution(execution: Execution): boolean {
  return execution.type === "flow" || Boolean(execution.flow_execution_id || execution.flow_id || execution.flow_version_id || execution.flow_node_id);
}

function matchesStatus(execution: Execution, filter: StatusFilter): boolean {
  const status = executionStatus(execution);
  if (filter === "all") return true;
  if (filter === "active") return ACTIVE_STATUSES.has(status);
  if (filter === "succeeded") return SUCCESS_STATUSES.has(status);
  if (filter === "failed") return FAILURE_STATUSES.has(status);
  return status === "cancelled";
}

function matchesSource(execution: Execution, filter: SourceFilter): boolean {
  if (filter === "all") return true;
  if (filter === "flow") return isFlowExecution(execution);
  const origin = execution.origin ?? "";
  if (filter === "schedule") return origin === "schedule" || origin === "scheduled";
  return origin === filter;
}

function matchesPeriod(execution: Execution, from: string, to: string): boolean {
  const createdAt = execution.created_at ? new Date(execution.created_at).getTime() : null;
  if (!createdAt || Number.isNaN(createdAt)) return true;
  if (from) {
    const fromMs = new Date(`${from}T00:00:00`).getTime();
    if (!Number.isNaN(fromMs) && createdAt < fromMs) return false;
  }
  if (to) {
    const toMs = new Date(`${to}T23:59:59`).getTime();
    if (!Number.isNaN(toMs) && createdAt > toMs) return false;
  }
  return true;
}

function entityLabel(execution: Execution): string {
  if (isFlowExecution(execution)) {
    return execution.flow_name ?? execution.flow_id ?? execution.flow_execution_id ?? execution.flow_version_id ?? "Fluxo";
  }
  return execution.automation_name ?? (execution.automation_id != null ? `Automacao #${execution.automation_id}` : "Automacao avulsa");
}

function agentLabel(execution: Execution): string {
  if (execution.agent_name) return execution.agent_name;
  if (execution.agent_id) return `Agent ${execution.agent_id.slice(0, 8)}`;
  if (execution.worker_id) return `Worker #${execution.worker_id}`;
  return "aguardando";
}

function entityFields(execution: Execution): string[] {
  return [
    entityLabel(execution),
    execution.automation_name ?? "",
    execution.flow_name ?? "",
    execution.flow_id ?? "",
    execution.flow_execution_id ?? "",
    execution.flow_version_id ?? "",
    execution.automation_id != null ? String(execution.automation_id) : "",
  ].filter(Boolean);
}

function searchableFields(execution: Execution): string[] {
  return [
    String(execution.id),
    String(execution.legacy_job_id ?? ""),
    executionStatus(execution),
    execution.type ?? "",
    execution.origin ?? "",
    executionOriginLabel(execution.origin),
    executionTypeLabel(execution.type),
    entityLabel(execution),
    agentLabel(execution),
    execution.failure_summary ?? "",
  ].filter(Boolean);
}

function durationBetween(start?: string | null, end?: string | null): string {
  if (!start) return "-";
  const startMs = new Date(start).getTime();
  const endMs = end ? new Date(end).getTime() : Date.now();
  if (Number.isNaN(startMs) || Number.isNaN(endMs) || endMs < startMs) return "-";
  return formatDuration((endMs - startMs) / 1000);
}
