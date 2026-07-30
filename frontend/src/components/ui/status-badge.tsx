import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { jobStatusMeta, priorityMeta, webhookStatusMeta, workerStatusMeta } from "@/lib/status";

export function StatusBadge({ status, className }: { status?: string | null; className?: string }) {
  const meta = jobStatusMeta(status);
  const Icon = meta.icon;
  return (
    <Badge tone={meta.tone} className={className}>
      <Icon className={cn("h-3.5 w-3.5", status === "running" && "animate-spin")} />
      {meta.label}
    </Badge>
  );
}

export function WorkerStatusBadge({ status, className }: { status?: string | null; className?: string }) {
  const meta = workerStatusMeta(status);
  return (
    <Badge tone={meta.tone} className={className}>
      <span className={cn("h-2 w-2 rounded-full", meta.dot, status !== "offline" && "animate-pulse-dot")} />
      {meta.label}
    </Badge>
  );
}

export function PriorityBadge({ priority, className }: { priority?: string | null; className?: string }) {
  const meta = priorityMeta(priority);
  return (
    <Badge tone={meta.tone} className={className}>
      {meta.label}
    </Badge>
  );
}

export function WebhookStatusBadge({ status, className }: { status?: string | null; className?: string }) {
  const meta = webhookStatusMeta(status);
  const Icon = meta.icon;
  return (
    <Badge tone={meta.tone} className={className}>
      <Icon className="h-3.5 w-3.5" />
      {meta.label}
    </Badge>
  );
}

export function StatusDot({ status, className }: { status?: string | null; className?: string }) {
  const meta = jobStatusMeta(status);
  return <span className={cn("inline-block h-2.5 w-2.5 rounded-full", meta.dot, className)} />;
}
