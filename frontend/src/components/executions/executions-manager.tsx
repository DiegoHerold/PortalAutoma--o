"use client";

import { useCallback, useEffect, useMemo, useState, type ComponentType } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Clock3,
  ExternalLink,
  Filter,
  History,
  Loader,
  Plus,
  RotateCw,
  Search,
  XCircle,
} from "lucide-react";

import { TriggerJobDialog } from "@/components/executions/trigger-job-dialog";
import { useRealtimeStatus } from "@/components/layout/realtime-provider";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { PriorityBadge, StatusBadge } from "@/components/ui/status-badge";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { useRealtime, type ConnectionState } from "@/hooks/use-realtime";
import { apiRequest } from "@/lib/api";
import {
  executionLifecycleStatus,
  executionOriginLabel,
  executionTypeLabel,
  isExecutionActiveStatus,
  isExecutionCancelledStatus,
  isExecutionFailureStatus,
  isExecutionRunningStatus,
  isExecutionSuccessStatus,
  isExecutionWaitingStatus,
  priorityLabelFromScore,
  priorityMeta,
} from "@/lib/status";
import { cn, formatDateTime, formatDuration, relativeFromNow } from "@/lib/utils";
import type { Automation } from "@/types/automation";
import type { Execution } from "@/types/execution";
import type { TaskExecution } from "@/types/flow";
import type { Worker } from "@/types/worker";

type DispatchQueueResponse = { items: TaskExecution[] };

const PAGE_SIZE = 50;
const POLL = 5000;
const STALE_EVENT_SECONDS = 8 * 60;

const VIEW_FILTERS = ["active", "waiting", "running", "attention", "succeeded", "failed", "cancelled", "all"] as const;
const SOURCE_FILTERS = ["all", "manual", "api", "trigger", "webhook", "schedule", "flow", "retry", "reprocess", "system"] as const;
const SORT_OPTIONS = ["smart", "recent", "oldest", "duration", "priority", "status"] as const;

type ViewFilter = (typeof VIEW_FILTERS)[number];
type SourceFilter = (typeof SOURCE_FILTERS)[number];
type SortOption = (typeof SORT_OPTIONS)[number];

export function ExecutionsManager() {
  const { token } = useAuth();
  const { toast } = useToast();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const view = parseViewFilter(searchParams.get("status"));
  const source = parseSourceFilter(searchParams.get("source") ?? searchParams.get("origin"));
  const sort = parseSortOption(searchParams.get("sort"));
  const triggerId = searchParams.get("trigger_id") ?? "";
  const entity = searchParams.get("entity") ?? "";
  const agent = searchParams.get("agent") ?? "";
  const from = searchParams.get("from") ?? "";
  const to = searchParams.get("to") ?? "";
  const query = searchParams.get("q") ?? "";
  const page = parsePage(searchParams.get("page"));

  const [queryDraft, setQueryDraft] = useState(query);
  const [dispatchOpen, setDispatchOpen] = useState(false);
  const [highlightId, setHighlightId] = useState<string | number | null>(null);
  const [cancellingId, setCancellingId] = useState<string | number | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);
  const [livePolling, setLivePolling] = useState(true);
  const [queuePolling, setQueuePolling] = useState(true);

  const executions = useApi<Execution[]>(executionsPath(source, triggerId, page), { pollMs: livePolling ? POLL : undefined });
  const queue = useApi<DispatchQueueResponse>("/dispatch/queue?limit=50", { pollMs: livePolling || queuePolling ? POLL : undefined });
  const automations = useApi<Automation[]>("/automations");
  const workers = useApi<Worker[]>("/workers");
  const { setState } = useRealtimeStatus();

  const refreshAll = useCallback(async () => {
    await Promise.all([executions.refetch(), queue.refetch()]);
    setLastUpdatedAt(Date.now());
  }, [executions, queue]);

  const { state } = useRealtime<Execution>({
    wsPath: "/ws/executions",
    onMessage: () => void refreshAll(),
    onPoll: () => void refreshAll(),
    pollMs: POLL,
  });

  useEffect(() => setState(state), [state, setState]);

  useEffect(() => {
    setQueryDraft(query);
  }, [query]);

  const setQuery = useCallback(
    (patch: Record<string, string | null>) => {
      const params = new URLSearchParams(searchParams.toString());
      Object.entries(patch).forEach(([key, value]) => {
        if (key === "source") params.delete("origin");
        if (!value) params.delete(key);
        else params.set(key, value);
      });
      const qs = params.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  useEffect(() => {
    const id = window.setTimeout(() => {
      if (queryDraft !== query) setQuery({ q: queryDraft.trim() || null, page: null });
    }, 350);
    return () => window.clearTimeout(id);
  }, [queryDraft, query, setQuery]);

  useEffect(() => {
    const list = executions.data ?? [];
    if (executions.data) {
      setLastUpdatedAt(Date.now());
      setLivePolling(list.some((execution) => isExecutionActiveStatus(executionLifecycleStatus(execution))));
    }
  }, [executions.data]);

  useEffect(() => {
    if (queue.data) {
      setLastUpdatedAt(Date.now());
      setQueuePolling(queue.data.items.length > 0);
    }
  }, [queue.data]);

  const automationName = useMemo(() => {
    const map = new Map<number, string>();
    automations.data?.forEach((automation) => map.set(automation.id, automation.name));
    return map;
  }, [automations.data]);

  const workerName = useMemo(() => {
    const map = new Map<number, string>();
    workers.data?.forEach((worker) => map.set(worker.id, worker.name));
    return map;
  }, [workers.data]);

  const list = executions.data ?? [];
  const queueItems = queue.data?.items ?? [];

  const counts = useMemo(() => {
    const today = new Date();
    return {
      active: list.filter((execution) => isExecutionActiveStatus(executionLifecycleStatus(execution))).length,
      waiting: list.filter((execution) => isExecutionWaitingStatus(executionLifecycleStatus(execution))).length,
      running: list.filter((execution) => isExecutionRunningStatus(executionLifecycleStatus(execution))).length,
      attention: list.filter((execution) => isAttentionExecution(execution)).length,
      succeededToday: list.filter((execution) => isExecutionSuccessStatus(executionLifecycleStatus(execution)) && isSameLocalDay(executionFinishedAt(execution) ?? execution.created_at, today)).length,
      failedToday: list.filter((execution) => isExecutionFailureStatus(executionLifecycleStatus(execution)) && isSameLocalDay(executionFinishedAt(execution) ?? execution.created_at, today)).length,
      cancelled: list.filter((execution) => isExecutionCancelledStatus(executionLifecycleStatus(execution))).length,
      all: list.length,
    };
  }, [list]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const entityQuery = entity.trim().toLowerCase();
    const agentQuery = agent.trim().toLowerCase();
    return sortExecutions(
      list
        .filter((execution) => matchesView(execution, view))
        .filter((execution) => matchesSource(execution, source))
        .filter((execution) => !triggerId || String(execution.trigger_id ?? "") === triggerId)
        .filter((execution) => matchesPeriod(execution, from, to))
        .filter((execution) => !entityQuery || entityFields(execution, automationName).some((value) => value.toLowerCase().includes(entityQuery)))
        .filter((execution) => !agentQuery || agentLabel(execution, workerName).toLowerCase().includes(agentQuery))
        .filter((execution) => !q || searchableFields(execution, automationName, workerName).some((value) => value.toLowerCase().includes(q))),
      sort,
    );
  }, [list, view, source, triggerId, from, to, entity, agent, query, sort, automationName, workerName]);

  const activeExecutions = filtered.filter((execution) => isExecutionActiveStatus(executionLifecycleStatus(execution)));
  const historyExecutions = filtered.filter((execution) => !isExecutionActiveStatus(executionLifecycleStatus(execution)));
  const activeChips = activeFilterChips({ view, source, sort, query, entity, agent, from, to, triggerId });
  const shouldShowLiveSections = view === "active" || view === "waiting" || view === "running" || view === "attention" || view === "all";
  const loading = executions.loading && !executions.data;

  async function cancelExecution(execution: Execution) {
    if (!token) return;
    if (!window.confirm(`Cancelar a execução #${execution.id}?`)) return;
    setCancellingId(execution.id);
    try {
      await apiRequest(`/executions/${execution.id}/cancel`, {
        method: "POST",
        token,
        body: JSON.stringify({ reason: "Cancelado pelo Portal." }),
      });
      toast({ title: "Cancelamento solicitado", kind: "success" });
      await refreshAll();
    } catch (err) {
      toast({ title: "Falha ao cancelar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setCancellingId(null);
    }
  }

  function handleDispatched(execution: Execution) {
    setHighlightId(execution.id);
    setQuery({ status: null, page: null });
    void refreshAll();
  }

  return (
    <div className="space-y-5">
      <ExecutionsHeader
        state={state}
        lastUpdatedAt={lastUpdatedAt}
        loading={executions.loading || queue.loading}
        onRefresh={() => void refreshAll()}
        onDispatch={() => setDispatchOpen(true)}
      />

      <OperationalSummary
        counts={counts}
        activeView={view}
        loading={loading}
        onSelect={(next) => setQuery({ status: next === "active" ? null : next, page: null })}
      />

      <ExecutionFilters
        view={view}
        source={source}
        sort={sort}
        query={queryDraft}
        entity={entity}
        agent={agent}
        from={from}
        to={to}
        chips={activeChips}
        onQueryChange={setQueryDraft}
        onChange={(patch) => setQuery({ ...patch, page: null })}
        onClear={() => {
          setQueryDraft("");
          setQuery({ status: null, source: null, origin: null, sort: null, q: null, entity: null, agent: null, from: null, to: null, trigger_id: null, page: null });
        }}
      />

      {executions.error ? (
        <ErrorState message={executions.error} onRetry={executions.refetch} />
      ) : loading ? (
        <Skeleton className="h-80 rounded-lg" />
      ) : list.length === 0 ? (
        <EmptyState
          icon={History}
          title="Nenhuma execução registrada"
          description="Dispare um job ou aguarde uma automação ser iniciada."
          action={
            <Button onClick={() => setDispatchOpen(true)}>
              <Plus className="h-4 w-4" /> Disparar job
            </Button>
          }
        />
      ) : filtered.length === 0 ? (
        <EmptyState title="Nenhuma execução corresponde aos filtros selecionados" description="Ajuste filtros, período ou busca." />
      ) : (
        <>
          {shouldShowLiveSections && (
            <>
              <ActiveExecutions
                executions={activeExecutions}
                workerName={workerName}
                automationName={automationName}
                highlightId={highlightId}
                cancellingId={cancellingId}
                onCancel={(execution) => void cancelExecution(execution)}
              />

              <DispatchQueueSnapshot items={queueItems} loading={queue.loading} error={queue.error} onRetry={queue.refetch} />
            </>
          )}

          <ExecutionHistory executions={historyExecutions} workerName={workerName} automationName={automationName} highlightId={highlightId} />

          <ExecutionPagination
            page={page}
            loaded={list.length}
            filtered={filtered.length}
            onPrevious={() => setQuery({ page: page <= 2 ? null : String(page - 1) })}
            onNext={() => setQuery({ page: String(page + 1) })}
          />
        </>
      )}

      <TriggerJobDialog
        open={dispatchOpen}
        onClose={() => setDispatchOpen(false)}
        automations={automations.data ?? []}
        onDispatched={handleDispatched}
      />
    </div>
  );
}

function ExecutionsHeader({
  state,
  lastUpdatedAt,
  loading,
  onRefresh,
  onDispatch,
}: {
  state: ConnectionState;
  lastUpdatedAt: number | null;
  loading: boolean;
  onRefresh: () => void;
  onDispatch: () => void;
}) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="space-y-1.5">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Operação</p>
        <h1 className="font-display text-2xl font-semibold tracking-tight sm:text-3xl">Execuções</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Acompanhe execuções em andamento, consulte o histórico e inicie novos jobs.
        </p>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <RealtimeBadge state={state} />
          <span>{lastUpdatedAt ? `Atualizado ${relativeFromNow(new Date(lastUpdatedAt).toISOString())}` : "Aguardando primeira atualização"}</span>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" onClick={onRefresh} disabled={loading}>
          <RotateCw className={cn("h-4 w-4", loading && "animate-spin")} /> Atualizar
        </Button>
        <Button onClick={onDispatch}>
          <Plus className="h-4 w-4" /> Disparar job
        </Button>
      </div>
    </div>
  );
}

function RealtimeBadge({ state }: { state: ConnectionState }) {
  const online = state === "online";
  return (
    <Badge tone={online ? "success" : state === "polling" ? "warning" : "neutral"}>
      <span className={cn("h-2 w-2 rounded-full", online ? "bg-success" : state === "polling" ? "bg-warning" : "bg-muted-foreground", state !== "offline" && "animate-pulse-dot")} />
      {state === "online" ? "Tempo real ativo" : state === "polling" ? "Atualizando por polling" : state === "connecting" ? "Conectando" : "Tempo real offline"}
    </Badge>
  );
}

function OperationalSummary({
  counts,
  activeView,
  loading,
  onSelect,
}: {
  counts: {
    active: number;
    waiting: number;
    running: number;
    attention: number;
    succeededToday: number;
    failedToday: number;
    cancelled: number;
    all: number;
  };
  activeView: ViewFilter;
  loading: boolean;
  onSelect: (view: ViewFilter) => void;
}) {
  const items = [
    { view: "running", label: "Em execução", value: counts.running, icon: Loader, tone: "info", hint: "Ofertadas, preparando ou rodando" },
    { view: "waiting", label: "Aguardando", value: counts.waiting, icon: Clock3, tone: "warning", hint: "Criadas, prontas ou na fila" },
    { view: "attention", label: "Com atenção", value: counts.attention, icon: AlertTriangle, tone: "destructive", hint: "Falhas, timeout, expiradas ou perdidas" },
    { view: "succeeded", label: "Concluídas hoje", value: counts.succeededToday, icon: CheckCircle2, tone: "success", hint: "Sucesso nesta página carregada" },
    { view: "failed", label: "Falharam hoje", value: counts.failedToday, icon: XCircle, tone: "destructive", hint: "Falhas nesta página carregada" },
    { view: "cancelled", label: "Canceladas", value: counts.cancelled, icon: Ban, tone: "neutral", hint: "Histórico cancelado" },
  ] as const;

  return (
    <div className="grid gap-3 md:grid-cols-3 2xl:grid-cols-6">
      {items.map((item) => (
        <SummaryButton
          key={item.view}
          icon={item.icon}
          label={item.label}
          value={loading ? "..." : item.value}
          hint={item.hint}
          active={activeView === item.view}
          tone={item.tone}
          onClick={() => onSelect(item.view)}
        />
      ))}
    </div>
  );
}

function SummaryButton({
  icon: Icon,
  label,
  value,
  hint,
  active,
  tone,
  onClick,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  hint: string;
  active: boolean;
  tone: "neutral" | "success" | "warning" | "info" | "destructive";
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-lg border border-border bg-card p-4 text-left transition-colors hover:bg-muted/50",
        active && "border-primary/50 ring-1 ring-primary/20",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <Icon className={cn("h-4 w-4", toneColor(tone))} />
      </div>
      <p className="tabular mt-2 text-2xl font-semibold">{value}</p>
      <p className="mt-1 truncate text-xs text-muted-foreground">{hint}</p>
    </button>
  );
}

function ExecutionFilters({
  view,
  source,
  sort,
  query,
  entity,
  agent,
  from,
  to,
  chips,
  onQueryChange,
  onChange,
  onClear,
}: {
  view: ViewFilter;
  source: SourceFilter;
  sort: SortOption;
  query: string;
  entity: string;
  agent: string;
  from: string;
  to: string;
  chips: Array<{ label: string; patch: Record<string, string | null> }>;
  onQueryChange: (value: string) => void;
  onChange: (patch: Record<string, string | null>) => void;
  onClear: () => void;
}) {
  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <Tabs
          value={view}
          onValueChange={(value) => onChange({ status: value === "active" ? null : value })}
          items={[
            { value: "active", label: "Agora" },
            { value: "waiting", label: "Aguardando" },
            { value: "running", label: "Rodando" },
            { value: "attention", label: "Atenção" },
            { value: "succeeded", label: "Concluídas" },
            { value: "failed", label: "Falhas" },
            { value: "cancelled", label: "Canceladas" },
            { value: "all", label: "Todas" },
          ]}
          className="max-w-full overflow-x-auto"
        />
        <div className="relative xl:w-80">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" placeholder="Buscar execução, status, agent..." value={query} onChange={(event) => onQueryChange(event.target.value)} />
        </div>
      </div>

      <div className="grid gap-2 rounded-lg border border-border bg-card p-3 md:grid-cols-6">
        <Select value={source} onChange={(event) => onChange({ source: event.target.value === "all" ? null : event.target.value })}>
          <option value="all">Todas as origens</option>
          <option value="manual">Manual</option>
          <option value="api">API</option>
          <option value="trigger">Trigger</option>
          <option value="webhook">Webhook</option>
          <option value="schedule">Agenda</option>
          <option value="flow">Fluxo</option>
          <option value="retry">Retry</option>
          <option value="reprocess">Reprocesso</option>
          <option value="system">Sistema</option>
        </Select>
        <Select value={sort} onChange={(event) => onChange({ sort: event.target.value === "smart" ? null : event.target.value })}>
          <option value="smart">Prioridade operacional</option>
          <option value="recent">Mais recentes</option>
          <option value="oldest">Mais antigas</option>
          <option value="duration">Maior duração</option>
          <option value="priority">Prioridade</option>
          <option value="status">Status</option>
        </Select>
        <div className="relative md:col-span-2">
          <Filter className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" placeholder="Automação ou fluxo" value={entity} onChange={(event) => onChange({ entity: event.target.value || null })} />
        </div>
        <Input placeholder="Agent" value={agent} onChange={(event) => onChange({ agent: event.target.value || null })} />
        <div className="grid grid-cols-2 gap-2 md:col-span-6 lg:col-span-1">
          <Input type="date" value={from} onChange={(event) => onChange({ from: event.target.value || null })} aria-label="Data inicial" />
          <Input type="date" value={to} onChange={(event) => onChange({ to: event.target.value || null })} aria-label="Data final" />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {chips.map((chip) => (
          <button
            key={chip.label}
            type="button"
            onClick={() => onChange(chip.patch)}
            className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground"
          >
            {chip.label}
            <span aria-hidden>×</span>
          </button>
        ))}
        {chips.length > 0 && (
          <Button variant="ghost" size="sm" onClick={onClear}>
            Limpar filtros
          </Button>
        )}
        <span className="text-xs text-muted-foreground">Filtros e ordenação são aplicados localmente sobre a página carregada de `/executions`.</span>
      </div>
    </div>
  );
}

function ActiveExecutions({
  executions,
  workerName,
  automationName,
  highlightId,
  cancellingId,
  onCancel,
}: {
  executions: Execution[];
  workerName: Map<number, string>;
  automationName: Map<number, string>;
  highlightId: string | number | null;
  cancellingId: string | number | null;
  onCancel: (execution: Execution) => void;
}) {
  const visible = executions.slice(0, 12);
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-display text-lg font-semibold tracking-tight">Agora</h2>
          <p className="text-sm text-muted-foreground">Execuções aguardando despacho, ofertadas, preparando, rodando ou cancelando.</p>
        </div>
        {executions.length > visible.length && <Badge tone="outline">Mostrando {visible.length} de {executions.length}</Badge>}
      </div>

      {visible.length === 0 ? (
        <EmptyState className="py-8" title="Nenhuma execução em andamento agora" description="O histórico continua disponível abaixo." icon={Clock3} />
      ) : (
        <div className="grid gap-3 xl:grid-cols-2">
          {visible.map((execution) => (
            <ActiveExecutionCard
              key={execution.id}
              execution={execution}
              workerName={workerName}
              automationName={automationName}
              highlighted={String(highlightId ?? "") === String(execution.id)}
              cancelling={String(cancellingId ?? "") === String(execution.id)}
              onCancel={() => onCancel(execution)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function ActiveExecutionCard({
  execution,
  workerName,
  automationName,
  highlighted,
  cancelling,
  onCancel,
}: {
  execution: Execution;
  workerName: Map<number, string>;
  automationName: Map<number, string>;
  highlighted: boolean;
  cancelling: boolean;
  onCancel: () => void;
}) {
  const status = executionLifecycleStatus(execution);
  const progress = execution.telemetry?.progress_percentage;
  const lastSignalAt = execution.telemetry?.latest_event_at ?? null;
  const stale = isExecutionActiveStatus(status) && lastSignalAt ? secondsSince(lastSignalAt) > STALE_EVENT_SECONDS : false;
  return (
    <article className={cn("rounded-lg border border-border bg-card p-4", highlighted && "border-primary/60 ring-1 ring-primary/25")}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link href={`/executions/${execution.id}`} className="truncate font-medium hover:text-primary">
            {entityLabel(execution, automationName)}
          </Link>
          <p className="tabular mt-1 text-xs text-muted-foreground">Execução #{execution.id}</p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <StatusBadge status={status} />
          <PriorityBadge priority={priorityLabelFromScore(execution.priority)} />
        </div>
      </div>

      {typeof progress === "number" ? (
        <div className="mt-4 space-y-1.5">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Progresso</span>
            <span className="tabular">{Math.round(progress)}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div className="h-full bg-primary transition-all" style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} />
          </div>
        </div>
      ) : (
        <p className="mt-4 text-xs text-muted-foreground">Progresso estruturado ainda não informado.</p>
      )}

      <div className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
        <InfoPill label="Origem" value={execution.type === "flow" ? "Fluxo" : executionOriginLabel(execution.origin)} />
        <InfoPill label="Agent" value={agentLabel(execution, workerName)} />
        <InfoPill label="Início" value={formatDateTime(execution.started_at ?? execution.created_at)} />
        <InfoPill label="Duração" value={durationBetween(execution.started_at ?? execution.created_at, executionFinishedAt(execution))} />
      </div>

      {stale && (
        <p className="mt-3 rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
          Esta execução não recebe eventos há {relativeFromNow(lastSignalAt).replace("há ", "")}.
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-muted-foreground">{execution.telemetry?.log_count ? `${execution.telemetry.log_count} logs registrados` : "Sem logs recentes no resumo"}</span>
        <div className="flex items-center gap-2">
          <Button asChild variant="outline" size="sm">
            <Link href={`/executions/${execution.id}`}>
              <ExternalLink className="h-3.5 w-3.5" /> Detalhes
            </Link>
          </Button>
          {isExecutionActiveStatus(status) && (
            <Button variant="ghost" size="sm" onClick={onCancel} disabled={cancelling} className="text-destructive hover:bg-destructive/10 hover:text-destructive">
              {cancelling ? "Cancelando..." : "Cancelar"}
            </Button>
          )}
        </div>
      </div>
    </article>
  );
}

function DispatchQueueSnapshot({
  items,
  loading,
  error,
  onRetry,
}: {
  items: TaskExecution[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-display text-lg font-semibold tracking-tight">Prontas para despacho</h2>
          <p className="text-sm text-muted-foreground">Snapshot das tasks que o scheduler enxerga como candidatas agora.</p>
        </div>
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCw className="h-3.5 w-3.5" /> Atualizar snapshot
        </Button>
      </div>
      {error ? (
        <ErrorState message={error} onRetry={onRetry} />
      ) : loading ? (
        <Skeleton className="h-32 rounded-lg" />
      ) : items.length === 0 ? (
        <EmptyState className="py-8" title="Nenhuma task aguardando despacho" description="Não há item pronto para seleção de Agent neste momento." icon={Clock3} />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <Table>
            <THead>
              <TR>
                <TH>Task</TH>
                <TH>Status</TH>
                <TH>Prioridade</TH>
                <TH>Tentativas</TH>
                <TH>Próxima tentativa</TH>
                <TH className="text-right">Execução</TH>
              </TR>
            </THead>
            <TBody>
              {items.slice(0, 8).map((task) => (
                <TR key={task.id}>
                  <TD>
                    <span className="tabular text-sm font-medium">{task.id.slice(0, 12)}</span>
                    <span className="tabular block text-xs text-muted-foreground">exec {task.execution_id.slice(0, 12)}</span>
                  </TD>
                  <TD>
                    <StatusBadge status={task.status} />
                  </TD>
                  <TD className="tabular text-sm">{task.priority}</TD>
                  <TD className="tabular text-sm text-muted-foreground">{task.scheduling_attempts}</TD>
                  <TD className="tabular text-sm text-muted-foreground">{formatDateTime(task.next_scheduling_attempt_at)}</TD>
                  <TD className="text-right">
                    <Link href={`/executions/${task.execution_id}?tab=diagnostico`} className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
                      Diagnóstico <ExternalLink className="h-3 w-3" />
                    </Link>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
          {items.length > 8 && <p className="border-t border-border px-4 py-2 text-xs text-muted-foreground">Mostrando 8 de {items.length} tasks prontas.</p>}
        </div>
      )}
    </section>
  );
}

function ExecutionHistory({
  executions,
  workerName,
  automationName,
  highlightId,
}: {
  executions: Execution[];
  workerName: Map<number, string>;
  automationName: Map<number, string>;
  highlightId: string | number | null;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="font-display text-lg font-semibold tracking-tight">Histórico</h2>
        <p className="text-sm text-muted-foreground">Execuções concluídas, canceladas, expiradas ou com falha na mesma central.</p>
      </div>
      {executions.length === 0 ? (
        <EmptyState className="py-8" title="Nenhuma execução histórica neste filtro" description="As execuções ativas aparecem acima." icon={History} />
      ) : (
        <div className="rounded-lg border border-border bg-card">
          <Table>
            <THead>
              <TR className="hover:bg-transparent">
                <TH>Execução</TH>
                <TH>Automação / Fluxo</TH>
                <TH>Status</TH>
                <TH>Origem</TH>
                <TH>Agent</TH>
                <TH>Duração</TH>
                <TH>Início</TH>
                <TH>Resultado</TH>
              </TR>
            </THead>
            <TBody>
              {executions.map((execution) => {
                const highlighted = String(highlightId ?? "") === String(execution.id);
                return (
                  <TR key={execution.id} className={cn(highlighted && "bg-primary/5")}>
                    <TD>
                      <Link href={`/executions/${execution.id}`} className="tabular font-medium hover:text-primary">
                        #{execution.id}
                      </Link>
                    </TD>
                    <TD className="max-w-[260px]">
                      <span className="block truncate text-sm font-medium">{entityLabel(execution, automationName)}</span>
                      {isFlowExecution(execution) && <span className="block text-xs text-muted-foreground">Origem de Flow</span>}
                    </TD>
                    <TD>
                      <StatusBadge status={executionLifecycleStatus(execution)} />
                    </TD>
                    <TD className="text-sm text-muted-foreground">{isFlowExecution(execution) ? "Fluxo" : executionOriginLabel(execution.origin)}</TD>
                    <TD className="text-sm text-muted-foreground">{agentLabel(execution, workerName)}</TD>
                    <TD className="tabular text-sm">{durationBetween(execution.started_at, executionFinishedAt(execution))}</TD>
                    <TD className="tabular text-sm">{formatDateTime(execution.started_at ?? execution.created_at)}</TD>
                    <TD className="max-w-[220px] truncate text-sm text-muted-foreground">{execution.failure_summary ?? execution.result_summary ?? "—"}</TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        </div>
      )}
    </section>
  );
}

function ExecutionPagination({
  page,
  loaded,
  filtered,
  onPrevious,
  onNext,
}: {
  page: number;
  loaded: number;
  filtered: number;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3">
      <p className="text-xs text-muted-foreground">
        Página {page} · {loaded} registros carregados · {filtered} visíveis após filtros locais
      </p>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={onPrevious} disabled={page <= 1}>
          Anterior
        </Button>
        <Button variant="outline" size="sm" onClick={onNext} disabled={loaded < PAGE_SIZE}>
          Próxima
        </Button>
      </div>
    </div>
  );
}

function InfoPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-muted/50 px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="tabular mt-0.5 truncate font-medium">{value}</p>
    </div>
  );
}

function parseViewFilter(value: string | null): ViewFilter {
  return VIEW_FILTERS.includes(value as ViewFilter) ? (value as ViewFilter) : "active";
}

function parseSourceFilter(value: string | null): SourceFilter {
  return SOURCE_FILTERS.includes(value as SourceFilter) ? (value as SourceFilter) : "all";
}

function parseSortOption(value: string | null): SortOption {
  return SORT_OPTIONS.includes(value as SortOption) ? (value as SortOption) : "smart";
}

function parsePage(value: string | null): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

function executionsPath(source: SourceFilter, triggerId: string, page: number): string {
  const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String((page - 1) * PAGE_SIZE) });
  if (source !== "all" && source !== "flow") params.set("origin", source === "schedule" ? "schedule" : source);
  if (triggerId) params.set("trigger_id", triggerId);
  return `/executions?${params.toString()}`;
}

function activeFilterChips(values: {
  view: ViewFilter;
  source: SourceFilter;
  sort: SortOption;
  query: string;
  entity: string;
  agent: string;
  from: string;
  to: string;
  triggerId: string;
}): Array<{ label: string; patch: Record<string, string | null> }> {
  const chips: Array<{ label: string; patch: Record<string, string | null> }> = [];
  if (values.view !== "active") chips.push({ label: `Visão: ${viewLabel(values.view)}`, patch: { status: null } });
  if (values.source !== "all") chips.push({ label: `Origem: ${executionOriginLabel(values.source)}`, patch: { source: null, origin: null } });
  if (values.sort !== "smart") chips.push({ label: `Ordenação: ${sortLabel(values.sort)}`, patch: { sort: null } });
  if (values.query) chips.push({ label: `Busca: ${values.query}`, patch: { q: null } });
  if (values.entity) chips.push({ label: `Automação/Fluxo: ${values.entity}`, patch: { entity: null } });
  if (values.agent) chips.push({ label: `Agent: ${values.agent}`, patch: { agent: null } });
  if (values.from) chips.push({ label: `De: ${values.from}`, patch: { from: null } });
  if (values.to) chips.push({ label: `Até: ${values.to}`, patch: { to: null } });
  if (values.triggerId) chips.push({ label: `Trigger: ${values.triggerId}`, patch: { trigger_id: null } });
  return chips;
}

function viewLabel(view: ViewFilter): string {
  const labels: Record<ViewFilter, string> = {
    active: "Agora",
    waiting: "Aguardando",
    running: "Rodando",
    attention: "Atenção",
    succeeded: "Concluídas",
    failed: "Falhas",
    cancelled: "Canceladas",
    all: "Todas",
  };
  return labels[view];
}

function sortLabel(sort: SortOption): string {
  const labels: Record<SortOption, string> = {
    smart: "Prioridade operacional",
    recent: "Mais recentes",
    oldest: "Mais antigas",
    duration: "Maior duração",
    priority: "Prioridade",
    status: "Status",
  };
  return labels[sort];
}

function matchesView(execution: Execution, view: ViewFilter): boolean {
  const status = executionLifecycleStatus(execution);
  if (view === "all") return true;
  if (view === "active") return isExecutionActiveStatus(status);
  if (view === "waiting") return isExecutionWaitingStatus(status);
  if (view === "running") return isExecutionRunningStatus(status);
  if (view === "attention") return isAttentionExecution(execution);
  if (view === "succeeded") return isExecutionSuccessStatus(status);
  if (view === "failed") return isExecutionFailureStatus(status);
  return isExecutionCancelledStatus(status);
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

function sortExecutions(items: Execution[], sort: SortOption): Execution[] {
  const sorted = [...items];
  sorted.sort((a, b) => {
    if (sort === "oldest") return timeValue(a.created_at) - timeValue(b.created_at);
    if (sort === "duration") return durationValue(b) - durationValue(a);
    if (sort === "priority") return priorityMeta(priorityLabelFromScore(a.priority)).rank - priorityMeta(priorityLabelFromScore(b.priority)).rank;
    if (sort === "status") return executionLifecycleStatus(a).localeCompare(executionLifecycleStatus(b));
    if (sort === "smart") {
      const rank = operationalRank(a) - operationalRank(b);
      if (rank !== 0) return rank;
    }
    return timeValue(b.created_at) - timeValue(a.created_at);
  });
  return sorted;
}

function operationalRank(execution: Execution): number {
  const status = executionLifecycleStatus(execution);
  if (isExecutionActiveStatus(status)) return 0;
  if (isAttentionExecution(execution)) return 1;
  return 2;
}

function isAttentionExecution(execution: Execution): boolean {
  const status = executionLifecycleStatus(execution);
  if (isExecutionFailureStatus(status)) return true;
  const latest = execution.telemetry?.latest_event_at;
  return isExecutionActiveStatus(status) && latest ? secondsSince(latest) > STALE_EVENT_SECONDS : false;
}

function entityLabel(execution: Execution, automationName: Map<number, string>): string {
  if (isFlowExecution(execution)) {
    return execution.flow_name ?? execution.flow_id ?? execution.flow_execution_id ?? execution.flow_version_id ?? "Fluxo";
  }
  return execution.automation_name ?? (execution.automation_id != null ? automationName.get(execution.automation_id) ?? `Automação #${execution.automation_id}` : "Automação avulsa");
}

function agentLabel(execution: Execution, workerName: Map<number, string>): string {
  if (execution.agent_name) return execution.agent_name;
  if (execution.agent_id) return `Agent ${execution.agent_id.slice(0, 8)}`;
  if (execution.worker_id) return workerName.get(execution.worker_id) ?? `Worker #${execution.worker_id}`;
  return "aguardando Agent";
}

function entityFields(execution: Execution, automationName: Map<number, string>): string[] {
  return [
    entityLabel(execution, automationName),
    execution.automation_name ?? "",
    execution.flow_name ?? "",
    execution.flow_id ?? "",
    execution.flow_execution_id ?? "",
    execution.flow_version_id ?? "",
    execution.automation_id != null ? String(execution.automation_id) : "",
  ].filter(Boolean);
}

function searchableFields(execution: Execution, automationName: Map<number, string>, workerName: Map<number, string>): string[] {
  return [
    String(execution.id),
    String(execution.legacy_job_id ?? ""),
    executionLifecycleStatus(execution),
    execution.type ?? "",
    execution.origin ?? "",
    executionOriginLabel(execution.origin),
    executionTypeLabel(execution.type),
    entityLabel(execution, automationName),
    agentLabel(execution, workerName),
    execution.failure_summary ?? "",
  ].filter(Boolean);
}

function isFlowExecution(execution: Execution): boolean {
  return execution.type === "flow" || Boolean(execution.flow_execution_id || execution.flow_id || execution.flow_version_id || execution.flow_node_id);
}

function executionFinishedAt(execution: Execution): string | null {
  return execution.finished_at ?? execution.completed_at ?? null;
}

function durationBetween(start?: string | null, end?: string | null): string {
  if (!start) return "—";
  const startMs = new Date(start).getTime();
  const endMs = end ? new Date(end).getTime() : Date.now();
  if (Number.isNaN(startMs) || Number.isNaN(endMs) || endMs < startMs) return "—";
  return formatDuration((endMs - startMs) / 1000);
}

function durationValue(execution: Execution): number {
  const start = execution.started_at ?? execution.created_at;
  if (!start) return 0;
  const startMs = new Date(start).getTime();
  const endMs = executionFinishedAt(execution) ? new Date(executionFinishedAt(execution)!).getTime() : Date.now();
  if (Number.isNaN(startMs) || Number.isNaN(endMs) || endMs < startMs) return 0;
  return endMs - startMs;
}

function timeValue(value?: string | null): number {
  const time = value ? new Date(value).getTime() : 0;
  return Number.isNaN(time) ? 0 : time;
}

function secondsSince(value: string): number {
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return 0;
  return (Date.now() - time) / 1000;
}

function isSameLocalDay(value: string | null | undefined, date: Date): boolean {
  if (!value) return false;
  const candidate = new Date(value);
  if (Number.isNaN(candidate.getTime())) return false;
  return candidate.getFullYear() === date.getFullYear() && candidate.getMonth() === date.getMonth() && candidate.getDate() === date.getDate();
}

function toneColor(tone: "neutral" | "success" | "warning" | "info" | "destructive"): string {
  switch (tone) {
    case "success":
      return "text-success";
    case "warning":
      return "text-warning";
    case "info":
      return "text-info";
    case "destructive":
      return "text-destructive";
    default:
      return "text-muted-foreground";
  }
}
