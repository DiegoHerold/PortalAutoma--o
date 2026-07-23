"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Server, Cpu, Activity } from "lucide-react";

import { Card } from "@/components/ui/card";
import { WorkerStatusBadge } from "@/components/ui/status-badge";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { useRealtime } from "@/hooks/use-realtime";
import { useRealtimeStatus } from "@/components/layout/realtime-provider";
import { cn, relativeFromNow } from "@/lib/utils";
import type { Worker } from "@/types/worker";

const POLL = 5000;

export function WorkersManager() {
  const workers = useApi<Worker[]>("/workers", { pollMs: POLL });
  const { setState } = useRealtimeStatus();
  const { state } = useRealtime<Worker>({
    wsPath: "/ws/executions",
    onMessage: () => void workers.refetch(),
    onPoll: () => void workers.refetch(),
    pollMs: POLL,
  });
  useEffect(() => setState(state), [state, setState]);

  if (workers.error) return <ErrorState message={workers.error} onRetry={workers.refetch} />;
  if (workers.loading)
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-40 rounded-lg" />
        ))}
      </div>
    );

  const list = workers.data ?? [];
  if (list.length === 0) return <EmptyState icon={Server} title="Sem workers" description="Nenhum worker registrado." />;

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {list.map((w) => {
        const load = w.active_jobs ?? 0;
        const pct = w.max_concurrency > 0 ? Math.min(100, (load / w.max_concurrency) * 100) : 0;
        return (
          <Link key={w.id} href={`/workers/${w.id}`} className="group">
            <Card className="h-full p-5 transition-colors hover:border-primary/40">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate font-display text-base font-semibold">{w.name}</h3>
                  <p className="tabular mt-0.5 truncate text-xs text-muted-foreground">{w.hostname}</p>
                </div>
                <WorkerStatusBadge status={w.status} />
              </div>

              <div className="mt-4 space-y-2">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5">
                    <Cpu className="h-3.5 w-3.5" /> Capacidade
                  </span>
                  <span className="tabular font-medium text-foreground">
                    {load}/{w.max_concurrency}
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn("h-full rounded-full", pct >= 100 ? "bg-destructive" : "bg-primary")}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>

              <div className="mt-4 flex items-center gap-1.5 text-xs text-muted-foreground">
                <Activity className="h-3.5 w-3.5" />
                Heartbeat {relativeFromNow(w.last_heartbeat_at)}
              </div>
            </Card>
          </Link>
        );
      })}
    </div>
  );
}
