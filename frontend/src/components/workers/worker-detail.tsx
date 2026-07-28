"use client";

import { SectionCard } from "@/components/shared/section-card";
import { ErrorState } from "@/components/shared/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { WorkerStatusBadge } from "@/components/ui/status-badge";
import { DetailJson } from "@/components/shared/detail-json";
import { useApi } from "@/hooks/use-api";
import { cn, relativeFromNow, formatDateTime } from "@/lib/utils";
import type { Worker } from "@/types/worker";

export function WorkerDetail({ id }: { id: string }) {
  const worker = useApi<Worker>(`/workers/${id}`, { pollMs: 5000 });

  if (worker.error) return <ErrorState message={worker.error} onRetry={worker.refetch} />;
  if (worker.loading || !worker.data) return <Skeleton className="h-64 rounded-lg" />;

  const w = worker.data;
  const load = w.active_jobs ?? 0;
  const pct = w.max_concurrency > 0 ? Math.min(100, (load / w.max_concurrency) * 100) : 0;

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <SectionCard title="Informações">
          <div className="grid gap-4 sm:grid-cols-2">
            <Meta label="Hostname" value={<span className="tabular">{w.hostname}</span>} />
            <Meta label="IP" value={<span className="tabular">{w.ip_address ?? "—"}</span>} />
            <Meta label="Status" value={<WorkerStatusBadge status={w.status} />} />
            <Meta label="Ativo" value={w.is_active ? "Sim" : "Não"} />
            <Meta label="Último heartbeat" value={<span className="tabular">{formatDateTime(w.last_heartbeat_at)}</span>} />
            <Meta label="Concorrência" value={<span className="tabular">{load}/{w.max_concurrency}</span>} />
          </div>
        </SectionCard>
        <SectionCard title="Dados brutos">
          <DetailJson data={w} />
        </SectionCard>
      </div>

      <div className="space-y-6">
        <SectionCard title="Carga atual">
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Jobs ativos</span>
              <span className="tabular font-medium">
                {load}/{w.max_concurrency}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div
                className={cn("h-full rounded-full", pct >= 100 ? "bg-destructive" : "bg-primary")}
                style={{ width: `${pct}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground">Heartbeat {relativeFromNow(w.last_heartbeat_at)}</p>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="mt-1 text-sm font-medium">{value}</div>
    </div>
  );
}
