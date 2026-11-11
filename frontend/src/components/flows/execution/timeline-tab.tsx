"use client";

import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/input";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { eventTypeLabel } from "@/lib/status";
import { formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";
import type { ExecutionEventsPage } from "@/types/execution";

type EventItem = ExecutionEventsPage["items"][number];

const LEVEL_COLOR: Record<string, string> = {
  ERROR: "text-destructive",
  CRITICAL: "text-destructive",
  WARNING: "text-warning",
  INFO: "text-info",
  DEBUG: "text-muted-foreground",
};

export function TimelineTab({
  events,
  loading,
  error,
  onRetry,
  nodeLabelByTask,
  agentLabelById,
  nodeFilter,
  onNodeFilterChange,
}: {
  events: EventItem[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  nodeLabelByTask: Map<string, string>;
  agentLabelById: Map<string, string>;
  nodeFilter: string | null;
  onNodeFilterChange: (taskExecutionId: string | null) => void;
}) {
  const [typeFilter, setTypeFilter] = useState("");
  const [agentFilter, setAgentFilter] = useState("");

  const eventTypes = useMemo(() => Array.from(new Set(events.map((e) => e.event_type))).sort(), [events]);
  const agentOptions = useMemo(() => Array.from(new Set(events.map((e) => e.agent_id).filter(Boolean))) as string[], [events]);

  const filtered = useMemo(() => {
    return events
      .filter((e) => !typeFilter || e.event_type === typeFilter)
      .filter((e) => !agentFilter || e.agent_id === agentFilter)
      .filter((e) => !nodeFilter || e.task_execution_id === nodeFilter)
      .sort((a, b) => (b.occurred_at || "").localeCompare(a.occurred_at || ""));
  }, [events, typeFilter, agentFilter, nodeFilter]);

  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-10 rounded-lg" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Select className="w-56" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="">Todos os tipos de evento</option>
          {eventTypes.map((t) => (
            <option key={t} value={t}>
              {eventTypeLabel(t)}
            </option>
          ))}
        </Select>
        {agentOptions.length > 0 && (
          <Select className="w-48" value={agentFilter} onChange={(e) => setAgentFilter(e.target.value)}>
            <option value="">Todos os Agents</option>
            {agentOptions.map((id) => (
              <option key={id} value={id}>
                {agentLabelById.get(id) ?? `Agent ${id.slice(0, 8)}`}
              </option>
            ))}
          </Select>
        )}
        {nodeFilter && (
          <Badge tone="primary" className="cursor-pointer" onClick={() => onNodeFilterChange(null)}>
            Nó: {nodeLabelByTask.get(nodeFilter) ?? nodeFilter.slice(0, 8)} · limpar ✕
          </Badge>
        )}
      </div>

      {filtered.length === 0 ? (
        <EmptyState title="Nenhum evento" description="Nenhum evento estruturado corresponde aos filtros atuais." />
      ) : (
        <ol className="relative space-y-4 rounded-lg border border-border bg-card p-4 pl-8">
          <span className="absolute left-[19px] top-4 h-[calc(100%-2rem)] w-px bg-border" />
          {filtered.map((event) => (
            <li key={event.id} className="relative">
              <span
                className={cn(
                  "absolute -left-[13px] top-1 h-2.5 w-2.5 rounded-full border-2 border-background",
                  event.level === "ERROR" || event.level === "CRITICAL"
                    ? "bg-destructive"
                    : event.level === "WARNING"
                      ? "bg-warning"
                      : "bg-info",
                )}
              />
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium">{eventTypeLabel(event.event_type)}</span>
                {event.level && (
                  <span className={cn("text-xs font-semibold uppercase", LEVEL_COLOR[event.level] ?? "text-muted-foreground")}>
                    {event.level}
                  </span>
                )}
                <span className="tabular text-xs text-muted-foreground">{formatDateTime(event.occurred_at)}</span>
                {event.task_execution_id && (
                  <button
                    type="button"
                    className="text-xs text-primary underline underline-offset-2"
                    onClick={() => onNodeFilterChange(event.task_execution_id!)}
                  >
                    {nodeLabelByTask.get(event.task_execution_id) ?? "nó"}
                  </button>
                )}
                {event.agent_id && (
                  <span className="text-xs text-muted-foreground">{agentLabelById.get(event.agent_id) ?? `Agent ${event.agent_id.slice(0, 8)}`}</span>
                )}
              </div>
              {event.message && <p className="mt-1 text-xs text-muted-foreground">{event.message}</p>}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
