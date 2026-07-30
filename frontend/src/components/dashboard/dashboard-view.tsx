"use client";

import { useEffect, useMemo } from "react";
import Link from "next/link";
import { Workflow, ListChecks, Loader, Server, CheckCircle2, XCircle } from "lucide-react";

import { StatCard } from "@/components/dashboard/stat-card";
import { SectionCard } from "@/components/shared/section-card";
import { EmptyState } from "@/components/shared/empty-state";
import { WorkerStatusBadge, PriorityBadge, StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { useRealtime } from "@/hooks/use-realtime";
import { useRealtimeStatus } from "@/components/layout/realtime-provider";
import { executionLifecycleStatus, isExecutionActiveStatus, isExecutionSuccessStatus, isExecutionWaitingStatus, PRIORITY, priorityLabelFromScore } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { Execution } from "@/types/execution";
import type { Worker } from "@/types/worker";
import type { Automation } from "@/types/automation";

const POLL = 5000;

export function DashboardView() {
  const jobs = useApi<Execution[]>("/executions", { pollMs: POLL });
  const workers = useApi<Worker[]>("/workers", { pollMs: POLL });
  const automations = useApi<Automation[]>("/automations");
  const { setState } = useRealtimeStatus();

  const { state } = useRealtime<Execution>({
    wsPath: "/ws/executions",
    onMessage: () => {
      void jobs.refetch();
      void workers.refetch();
    },
    onPoll: () => {
      void jobs.refetch();
      void workers.refetch();
    },
    pollMs: POLL,
  });

  useEffect(() => setState(state), [state, setState]);

  const jobList = jobs.data ?? [];
  const workerList = workers.data ?? [];

  const kpis = useMemo(() => {
    const running = jobList.filter((j) => executionLifecycleStatus(j) === "running").length;
    const queued = jobList.filter((j) => isExecutionWaitingStatus(executionLifecycleStatus(j))).length;
    const success = jobList.filter((j) => isExecutionSuccessStatus(executionLifecycleStatus(j))).length;
    const failed = jobList.filter((j) => executionLifecycleStatus(j) === "failed").length;
    const online = workerList.filter((w) => w.status === "online" || w.status === "busy").length;
    return { running, queued, success, failed, online };
  }, [jobList, workerList]);

  const queueByPriority = useMemo(() => {
    const active = jobList.filter((j) => isExecutionWaitingStatus(executionLifecycleStatus(j)));
    return Object.keys(PRIORITY).map((p) => ({
      priority: p,
      count: active.filter((j) => priorityLabelFromScore(j.priority) === p).length,
    }));
  }, [jobList]);

  const activeJobs = jobList
    .filter((j) => isExecutionActiveStatus(executionLifecycleStatus(j)))
    .slice(0, 6);

  const loading = jobs.loading || workers.loading;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Em execução" value={kpis.running} icon={Loader} tone="info" loading={loading} />
        <StatCard label="Na fila" value={kpis.queued} icon={ListChecks} tone="warning" loading={loading} />
        <StatCard label="Workers ativos" value={`${kpis.online}/${workerList.length}`} icon={Server} tone="success" loading={loading} />
        <StatCard label="Concluídas" value={kpis.success} icon={CheckCircle2} tone="success" loading={loading} />
        <StatCard label="Falhas" value={kpis.failed} icon={XCircle} tone="destructive" loading={loading} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <SectionCard
          className="lg:col-span-2"
          title="Execuções em andamento"
          description="Execuções rodando ou aguardando Agent"
          actions={
            <Button asChild variant="ghost" size="sm">
              <Link href="/executions">Ver tudo</Link>
            </Button>
          }
          bodyClassName="p-0"
        >
          {loading ? (
            <div className="space-y-2 p-5">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12" />
              ))}
            </div>
          ) : activeJobs.length === 0 ? (
            <div className="p-5">
              <EmptyState title="Nada em andamento" description="Nenhuma execução ativa ou aguardando no momento." icon={ListChecks} />
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {activeJobs.map((job) => {
                const automation = automations.data?.find((a) => a.id === job.automation_id);
                return (
                  <li key={job.id}>
                    <Link
                      href={`/executions/${job.id}`}
                      className="flex items-center justify-between gap-3 px-5 py-3 transition-colors hover:bg-muted/50"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">
                          {job.automation_name ?? automation?.name ?? (job.automation_id != null ? `Automação #${job.automation_id}` : "—")}
                        </p>
                        <p className="tabular text-xs text-muted-foreground">Execução #{job.id}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <PriorityBadge priority={priorityLabelFromScore(job.priority)} />
                        <StatusBadge status={executionLifecycleStatus(job)} />
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </SectionCard>

        <div className="space-y-6">
          <SectionCard title="Fila por prioridade" bodyClassName="space-y-3">
            {queueByPriority.map(({ priority, count }) => {
              const max = Math.max(1, ...queueByPriority.map((q) => q.count));
              return (
                <div key={priority} className="space-y-1.5">
                  <div className="flex items-center justify-between text-sm">
                    <PriorityBadge priority={priority} />
                    <span className="tabular font-medium">{count}</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn("h-full rounded-full transition-all", barColor(priority))}
                      style={{ width: `${(count / max) * 100}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </SectionCard>

          <SectionCard
            title="Workers"
            actions={
              <Button asChild variant="ghost" size="sm">
                <Link href="/workers">Gerenciar</Link>
              </Button>
            }
            bodyClassName="p-0"
          >
            {loading ? (
              <div className="space-y-2 p-5">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-10" />
                ))}
              </div>
            ) : workerList.length === 0 ? (
              <div className="p-5">
                <EmptyState title="Sem workers" description="Nenhum worker registrado." icon={Server} />
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {workerList.slice(0, 5).map((w) => (
                  <li key={w.id} className="flex items-center justify-between gap-2 px-5 py-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{w.name}</p>
                      <p className="tabular truncate text-xs text-muted-foreground">{w.hostname}</p>
                    </div>
                    <WorkerStatusBadge status={w.status} />
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>
        </div>
      </div>
    </div>
  );
}

function barColor(priority: string): string {
  switch (priority) {
    case "critical":
      return "bg-destructive";
    case "high":
      return "bg-warning";
    case "normal":
      return "bg-info";
    default:
      return "bg-muted-foreground";
  }
}
