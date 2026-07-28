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
import { priorityLabelFromScore } from "@/lib/status";
import { formatDateTime } from "@/lib/utils";
import type { ExecutionDetails } from "@/types/execution";

const CANCELLABLE = new Set(["created", "pending", "queued", "ready", "offered", "accepted", "committed", "preparing", "running"]);

export function JobDetail({ id }: { id: string }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const job = useApi<ExecutionDetails>(`/executions/${id}`, { pollMs: 4000 });
  const [cancelling, setCancelling] = useState(false);

  if (job.error) return <ErrorState message={job.error} onRetry={job.refetch} />;
  if (job.loading || !job.data) return <Skeleton className="h-64 rounded-lg" />;
  const details = job.data;
  const execution = details.execution;
  const firstTask = details.tasks?.[0];
  const automationVersion = details.automation_version as
    | { automation_id?: number; automation_name?: string }
    | null
    | undefined;
  const agent = details.agent as { id?: string; name?: string } | null | undefined;
  const status = execution.status ?? "pending";
  const priority = priorityLabelFromScore(firstTask?.priority ?? null);

  async function cancelJob() {
    if (!token) return;
    if (!window.confirm(`Cancelar o job #${execution.id}?`)) return;
    setCancelling(true);
    try {
      await apiRequest(`/executions/${execution.id}/cancel`, { method: "POST", token });
      toast({ title: `Job #${execution.id} cancelado`, kind: "success" });
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
          <DetailJson data={firstTask?.parameters ?? execution.input ?? {}} />
        </SectionCard>
        {execution.failure_summary && (
          <SectionCard title="Erro">
            <p className="tabular rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
              {execution.failure_summary}
            </p>
          </SectionCard>
        )}
      </div>

      <div className="space-y-6">
        <SectionCard title="Estado">
          <div className="space-y-3">
            <Row label="Status" value={<StatusBadge status={status} />} />
            <Row label="Prioridade" value={<PriorityBadge priority={priority} />} />
            <Row
              label="Automação"
              value={
                automationVersion?.automation_id ? (
                  <Link href={`/automations/${automationVersion.automation_id}`} className="text-sm font-medium hover:text-primary">
                    {automationVersion.automation_name ?? `#${automationVersion.automation_id}`}
                  </Link>
                ) : (
                  <span className="text-sm text-muted-foreground">—</span>
                )
              }
            />
            <Row label="Worker" value={<span className="tabular text-sm">{agent?.name ?? (agent?.id ? `#${agent.id}` : "aguardando")}</span>} />
            <Row label="Criado" value={<span className="tabular text-sm">{formatDateTime(execution.created_at)}</span>} />
            <Row label="Iniciado" value={<span className="tabular text-sm">{formatDateTime(execution.started_at)}</span>} />
          </div>
        </SectionCard>
        {CANCELLABLE.has(status) && (
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
