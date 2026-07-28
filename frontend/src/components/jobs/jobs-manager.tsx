"use client";

import { useEffect, useMemo, useState, type ComponentType } from "react";
import Link from "next/link";
import { Activity, AlertCircle, Clock3, ListChecks, Plus, Search, Timer, X } from "lucide-react";

import { DispatchDialog } from "@/components/jobs/dispatch-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge, PriorityBadge } from "@/components/ui/status-badge";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { useRealtimeStatus } from "@/components/layout/realtime-provider";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { useRealtime } from "@/hooks/use-realtime";
import { apiRequest } from "@/lib/api";
import { priorityMeta } from "@/lib/status";
import { formatCountdown, formatDateTime, formatDuration, formatTime } from "@/lib/utils";
import type { Automation } from "@/types/automation";
import type { Job } from "@/types/job";
import type { Worker } from "@/types/worker";

const CANCELLABLE = new Set(["pending", "queued", "running"]);
const POLL = 4000;
const FILTERS = ["active", "all", "queued", "running", "failed", "done"] as const;
type Filter = (typeof FILTERS)[number];

export function JobsManager() {
  const { token } = useAuth();
  const { toast } = useToast();
  const jobs = useApi<Job[]>("/jobs", { pollMs: POLL });
  const automations = useApi<Automation[]>("/automations");
  const workers = useApi<Worker[]>("/workers");
  const { setState } = useRealtimeStatus();
  const [filter, setFilter] = useState<Filter>("active");
  const [query, setQuery] = useState("");
  const [dispatchOpen, setDispatchOpen] = useState(false);
  const [cancellingId, setCancellingId] = useState<number | null>(null);

  async function cancelJob(job: Job) {
    if (!token) return;
    if (!window.confirm(`Cancelar o job #${job.id}?`)) return;
    setCancellingId(job.id);
    try {
      await apiRequest(`/jobs/${job.id}:cancel`, { method: "POST", token });
      toast({ title: `Job #${job.id} cancelado`, kind: "success" });
      await jobs.refetch();
    } catch (err) {
      toast({ title: "Falha ao cancelar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setCancellingId(null);
    }
  }

  const { state } = useRealtime<Job>({
    wsPath: "/ws/executions",
    onMessage: () => void jobs.refetch(),
    onPoll: () => void jobs.refetch(),
    pollMs: POLL,
  });
  useEffect(() => setState(state), [state, setState]);

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

  const list = jobs.data ?? [];
  const counts = {
    active: list.filter((job) => ["queued", "pending", "running"].includes(job.status)).length,
    queued: list.filter((job) => ["queued", "pending"].includes(job.status)).length,
    running: list.filter((job) => job.status === "running").length,
    failed: list.filter((job) => job.status === "failed").length,
    done: list.filter((job) => ["success", "failed", "cancelled"].includes(job.status)).length,
    all: list.length,
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const byFilter = (job: Job) => {
      if (filter === "all") return true;
      if (filter === "active") return ["queued", "pending", "running"].includes(job.status);
      if (filter === "queued") return ["queued", "pending"].includes(job.status);
      if (filter === "running") return job.status === "running";
      if (filter === "failed") return job.status === "failed";
      return ["success", "failed", "cancelled"].includes(job.status);
    };
    const byQuery = (job: Job) => {
      if (!q) return true;
      const automation = job.automation_name ?? automationName.get(job.automation_id) ?? "";
      const worker = job.assigned_worker_id
        ? job.worker_name ?? workerName.get(job.assigned_worker_id) ?? String(job.assigned_worker_id)
        : "aguardando";
      return [String(job.id), automation, worker, job.status, job.priority].some((value) => value.toLowerCase().includes(q));
    };
    return [...list]
      .filter((job) => byFilter(job) && byQuery(job))
      .sort((a, b) => {
        const priority = priorityMeta(a.priority).rank - priorityMeta(b.priority).rank;
        if (priority !== 0) return priority;
        return (a.queue_position ?? a.id) - (b.queue_position ?? b.id);
      });
  }, [list, filter, query, automationName, workerName]);

  const nextQueued = filtered.find((job) => ["queued", "pending"].includes(job.status));
  const runningJobs = list.filter((job) => job.status === "running");
  const failedLast = list.find((job) => job.status === "failed");

  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-4">
        <JobMetric icon={Activity} label="Ativos" value={counts.active} hint={`${counts.running} em execução`} />
        <JobMetric icon={Clock3} label="Na fila" value={counts.queued} hint={nextQueued ? `Próximo: #${nextQueued.id}` : "Fila vazia"} />
        <JobMetric
          icon={Timer}
          label="Tempo estimado"
          value={runningJobs[0]?.estimated_duration_seconds ? formatDuration(runningJobs[0].estimated_duration_seconds) : "—"}
          hint={runningJobs[0] ? `Job #${runningJobs[0].id}` : "Sem execução ativa"}
        />
        <JobMetric icon={AlertCircle} label="Falhas" value={counts.failed} hint={failedLast ? `Última: #${failedLast.id}` : "Sem falhas"} />
      </div>

      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <Tabs
          value={filter}
          onValueChange={(value) => setFilter(value as Filter)}
          items={[
            { value: "active", label: "Ativos", count: counts.active },
            { value: "queued", label: "Fila", count: counts.queued },
            { value: "running", label: "Rodando", count: counts.running },
            { value: "failed", label: "Falhas", count: counts.failed },
            { value: "done", label: "Concluídos", count: counts.done },
            { value: "all", label: "Todos", count: counts.all },
          ]}
          className="max-w-full overflow-x-auto"
        />
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="relative sm:w-72">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Buscar job, automação ou worker..."
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <Button onClick={() => setDispatchOpen(true)}>
            <Plus className="h-4 w-4" /> Disparar job
          </Button>
        </div>
      </div>

      {jobs.error ? (
        <ErrorState message={jobs.error} onRetry={jobs.refetch} />
      ) : jobs.loading ? (
        <Skeleton className="h-72 rounded-lg" />
      ) : filtered.length === 0 ? (
        <EmptyState icon={ListChecks} title="Nenhum job" description="Nada corresponde a este filtro." />
      ) : (
        <div className="rounded-lg border border-border bg-card">
          <Table>
            <THead>
              <TR className="hover:bg-transparent">
                <TH>Job</TH>
                <TH>Automação</TH>
                <TH>Prioridade</TH>
                <TH>Status</TH>
                <TH>Worker</TH>
                <TH>Estimativas</TH>
                <TH>Criado</TH>
                <TH className="text-right">Fila</TH>
                <TH className="text-right">Ações</TH>
              </TR>
            </THead>
            <TBody>
              {filtered.map((job) => (
                <TR key={job.id}>
                  <TD>
                    <Link href={`/jobs/${job.id}`} className="tabular font-medium hover:text-primary">
                      #{job.id}
                    </Link>
                  </TD>
                  <TD className="max-w-[220px]">
                    <span className="block truncate font-medium">
                      {job.automation_name ?? automationName.get(job.automation_id) ?? `#${job.automation_id}`}
                    </span>
                    {job.error_message && (
                      <span className="block truncate text-xs text-destructive" title={job.error_message}>
                        {job.error_message}
                      </span>
                    )}
                  </TD>
                  <TD>
                    <PriorityBadge priority={job.priority} />
                  </TD>
                  <TD>
                    <StatusBadge status={job.status} />
                  </TD>
                  <TD className="text-sm text-muted-foreground">
                    {job.assigned_worker_id
                      ? job.worker_name ?? workerName.get(job.assigned_worker_id) ?? `#${job.assigned_worker_id}`
                      : "aguardando"}
                  </TD>
                  <TD className="tabular text-sm">
                    <span className="block">
                      {job.status === "running" ? `iniciado ${formatTime(job.started_at)}` : formatEta(job.estimated_start)}
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      fim {job.estimated_end ? formatCountdown(job.estimated_end) : "—"}
                    </span>
                  </TD>
                  <TD className="tabular text-sm text-muted-foreground">{formatDateTime(job.created_at)}</TD>
                  <TD className="tabular text-right text-sm text-muted-foreground">
                    {job.queue_position != null ? `${job.queue_position}º` : "—"}
                  </TD>
                  <TD className="text-right">
                    {CANCELLABLE.has(job.status) && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => void cancelJob(job)}
                        disabled={cancellingId === job.id}
                        className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                      >
                        <X className="h-3.5 w-3.5" /> Cancelar
                      </Button>
                    )}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </div>
      )}

      <DispatchDialog
        open={dispatchOpen}
        onClose={() => setDispatchOpen(false)}
        automations={automations.data ?? []}
        onDispatched={() => void jobs.refetch()}
      />
    </div>
  );
}

function JobMetric({
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

function formatEta(iso?: string | null): string {
  if (!iso) return "—";
  return formatTime(iso);
}
