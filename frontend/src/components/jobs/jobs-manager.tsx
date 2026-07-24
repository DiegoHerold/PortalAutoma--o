"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Plus, ListChecks, X } from "lucide-react";

import { DispatchDialog } from "@/components/jobs/dispatch-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Tabs } from "@/components/ui/tabs";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { StatusBadge, PriorityBadge } from "@/components/ui/status-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { useRealtime } from "@/hooks/use-realtime";
import { useRealtimeStatus } from "@/components/layout/realtime-provider";
import { apiRequest } from "@/lib/api";
import { priorityMeta } from "@/lib/status";
import { formatTime, formatCountdown } from "@/lib/utils";
import type { Job } from "@/types/job";
import type { Automation } from "@/types/automation";
import type { Worker } from "@/types/worker";

const CANCELLABLE = new Set(["pending", "queued", "running"]);

const POLL = 4000;
const FILTERS = ["active", "all", "queued", "running", "done"] as const;
type Filter = (typeof FILTERS)[number];

export function JobsManager() {
  const { token } = useAuth();
  const { toast } = useToast();
  const jobs = useApi<Job[]>("/jobs", { pollMs: POLL });
  const automations = useApi<Automation[]>("/automations");
  const workers = useApi<Worker[]>("/workers");
  const { setState } = useRealtimeStatus();
  const [filter, setFilter] = useState<Filter>("active");
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
    automations.data?.forEach((a) => map.set(a.id, a.name));
    return map;
  }, [automations.data]);
  const workerName = useMemo(() => {
    const map = new Map<number, string>();
    workers.data?.forEach((w) => map.set(w.id, w.name));
    return map;
  }, [workers.data]);

  const list = jobs.data ?? [];
  const counts = {
    active: list.filter((j) => ["queued", "pending", "running"].includes(j.status)).length,
    queued: list.filter((j) => ["queued", "pending"].includes(j.status)).length,
    running: list.filter((j) => j.status === "running").length,
    done: list.filter((j) => ["success", "failed", "cancelled"].includes(j.status)).length,
    all: list.length,
  };

  const filtered = useMemo(() => {
    const byFilter = (j: Job) => {
      if (filter === "all") return true;
      if (filter === "active") return ["queued", "pending", "running"].includes(j.status);
      if (filter === "queued") return ["queued", "pending"].includes(j.status);
      if (filter === "running") return j.status === "running";
      return ["success", "failed", "cancelled"].includes(j.status);
    };
    return [...list].filter(byFilter).sort((a, b) => {
      const pr = priorityMeta(a.priority).rank - priorityMeta(b.priority).rank;
      if (pr !== 0) return pr;
      return (a.queue_position ?? a.id) - (b.queue_position ?? b.id);
    });
  }, [list, filter]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs
          value={filter}
          onValueChange={(v) => setFilter(v as Filter)}
          items={[
            { value: "active", label: "Ativos", count: counts.active },
            { value: "queued", label: "Na fila", count: counts.queued },
            { value: "running", label: "Executando", count: counts.running },
            { value: "done", label: "Concluídos", count: counts.done },
            { value: "all", label: "Todos", count: counts.all },
          ]}
        />
        <Button onClick={() => setDispatchOpen(true)}>
          <Plus className="h-4 w-4" /> Disparar job
        </Button>
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
                <TH>Início est.</TH>
                <TH>Término est.</TH>
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
                  <TD className="max-w-[200px] truncate">
                    {job.automation_name ?? automationName.get(job.automation_id) ?? `#${job.automation_id}`}
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
                    {job.status === "running" ? (
                      <span className="text-muted-foreground">iniciado {formatTime(job.started_at)}</span>
                    ) : (
                      formatEta(job.estimated_start)
                    )}
                  </TD>
                  <TD className="tabular text-sm">
                    {job.estimated_end ? (
                      <span title={formatTime(job.estimated_end)}>{formatCountdown(job.estimated_end)}</span>
                    ) : (
                      "—"
                    )}
                  </TD>
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

function formatEta(iso?: string | null): string {
  if (!iso) return "—";
  return formatTime(iso);
}
