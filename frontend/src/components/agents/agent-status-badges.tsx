import { Badge } from "@/components/ui/badge";
import { WorkerStatusBadge } from "@/components/ui/status-badge";
import { agentAdministrativeStatusMeta, agentHealthStatusMeta, agentOccupancyStatusMeta } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { Agent } from "@/types/agent";

/** connectivity_status reaproveita workerStatusMeta (mesmos valores: connecting/online/stale/disconnected/offline). */
export function ConnectivityBadge({ status, className }: { status: Agent["connectivity_status"]; className?: string }) {
  return <WorkerStatusBadge status={status} className={className} />;
}

export function AdministrativeStatusBadge({ status, className }: { status: Agent["administrative_status"]; className?: string }) {
  const meta = agentAdministrativeStatusMeta(status);
  return (
    <Badge tone={meta.tone} className={className}>
      {meta.label}
    </Badge>
  );
}

export function HealthStatusBadge({ status, className }: { status: Agent["health_status"]; className?: string }) {
  const meta = agentHealthStatusMeta(status);
  return (
    <Badge tone={meta.tone} className={className}>
      {meta.label}
    </Badge>
  );
}

export function OccupancyStatusBadge({ status, className }: { status: Agent["occupancy_status"]; className?: string }) {
  const meta = agentOccupancyStatusMeta(status);
  return (
    <Badge tone={meta.tone} className={className}>
      {meta.label}
    </Badge>
  );
}

/** Combinação compacta das 4 dimensões de status, usada nos cards da lista. */
export function AgentStatusRow({ agent, className }: { agent: Agent; className?: string }) {
  return (
    <div className={cn("flex flex-wrap items-center gap-1.5", className)}>
      <ConnectivityBadge status={agent.connectivity_status} />
      <AdministrativeStatusBadge status={agent.administrative_status} />
      {agent.health_status !== "healthy" && <HealthStatusBadge status={agent.health_status} />}
      {agent.occupancy_status !== "idle" && <OccupancyStatusBadge status={agent.occupancy_status} />}
    </div>
  );
}
