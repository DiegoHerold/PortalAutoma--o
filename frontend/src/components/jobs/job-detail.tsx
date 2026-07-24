"use client";

import Link from "next/link";
import { useState } from "react";
import { X } from "lucide-react";

import { SectionCard } from "@/components/shared/section-card";
import { ErrorState } from "@/components/shared/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge, PriorityBadge } from "@/components/ui/status-badge";
import { DetailJson } from "@/components/shared/detail-json";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { formatDateTime, formatCountdown } from "@/lib/utils";
import type { Job } from "@/types/job";

const CANCELLABLE = new Set(["pending", "queued", "running"]);

export function JobDetail({ id }: { id: string }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const job = useApi<Job>(`/jobs/${id}`, { pollMs: 4000 });
  const [cancelling, setCancelling] = useState(false);

  if (job.error) return <ErrorState message={job.error} onRetry={job.refetch} />;
  if (job.loading || !job.data) return <Skeleton className="h-64 rounded-lg" />;
  const j = job.data;

  async function cancelJob() {
    if (!token) return;
    if (!window.confirm(`Cancelar o job #${j.id}?`)) return;
    setCancelling(true);
    try {
      await apiRequest(`/jobs/${j.id}:cancel`, { method: "POST", token });
      toast({ title: `Job #${j.id} cancelado`, kind: "success" });
      await job.refetch();
    } catch (err) {
      toast({ title: "Falha ao cancelar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setCancelling(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <SectionCard title="Payload">
          <DetailJson data={j.payload_json ?? {}} />
        </SectionCard>
        {j.error_message && (
          <SectionCard title="Erro">
            <p className="tabular rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
              {j.error_message}
            </p>
          </SectionCard>
        )}
      </div>

      <div className="space-y-6">
        <SectionCard title="Estado">
          <div className="space-y-3">
            <Row label="Status" value={<StatusBadge status={j.status} />} />
            <Row label="Prioridade" value={<PriorityBadge priority={j.priority} />} />
            <Row
              label="Automação"
              value={
                <Link href={`/automations/${j.automation_id}`} className="text-sm font-medium hover:text-primary">
                  #{j.automation_id}
                </Link>
              }
            />
            <Row label="Worker" value={<span className="tabular text-sm">{j.assigned_worker_id ? `#${j.assigned_worker_id}` : "aguardando"}</span>} />
            <Row label="Posição na fila" value={<span className="tabular text-sm">{j.queue_position != null ? `${j.queue_position}º` : "—"}</span>} />
            <Row label="Início est." value={<span className="tabular text-sm">{formatDateTime(j.estimated_start)}</span>} />
            <Row
              label="Término est."
              value={<span className="tabular text-sm">{j.estimated_end ? formatCountdown(j.estimated_end) : "—"}</span>}
            />
          </div>
        </SectionCard>
        {CANCELLABLE.has(j.status) && (
          <SectionCard title="Ações">
            <Button
              variant="destructive"
              className="w-full"
              onClick={() => void cancelJob()}
              disabled={cancelling}
            >
              <X className="h-4 w-4" /> {cancelling ? "Cancelando..." : "Cancelar job"}
            </Button>
          </SectionCard>
        )}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm text-muted-foreground">{label}</span>
      {value}
    </div>
  );
}
