"use client";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { jobStatusMeta } from "@/lib/status";
import { formatDateTime, formatDuration } from "@/lib/utils";
import type { ExecutionAttempt, TaskExecution } from "@/types/flow";

export function AttemptsTab({
  tasks,
  attempts,
  loading,
  error,
  onRetry,
  nodeLabelByTask,
  agentLabelById,
}: {
  tasks: TaskExecution[];
  attempts: ExecutionAttempt[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  nodeLabelByTask: Map<string, string>;
  agentLabelById: Map<string, string>;
}) {
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (loading) return <Skeleton className="h-40 rounded-lg" />;
  if (tasks.length === 0) {
    return <EmptyState title="Sem tentativas" description="Nenhum nó de automação foi despachado ainda." />;
  }

  const sortedTasks = [...tasks].sort((a, b) => a.created_at.localeCompare(b.created_at));

  return (
    <div className="space-y-4">
      {sortedTasks.map((task) => {
        const taskAttempts = attempts
          .filter((a) => a.task_execution_id === task.id)
          .sort((a, b) => (a.offered_at ?? "").localeCompare(b.offered_at ?? ""));
        const meta = jobStatusMeta(task.status);
        return (
          <div key={task.id} className="overflow-hidden rounded-lg border border-border bg-card">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-muted/30 px-4 py-2.5">
              <div>
                <p className="font-medium">{nodeLabelByTask.get(task.id) ?? `Nó ${task.id.slice(0, 8)}`}</p>
                <p className="text-xs text-muted-foreground">
                  {task.scheduling_attempts} tentativa(s) de agendamento · tentativa atual #{task.current_attempt_number}
                </p>
              </div>
              <Badge tone={meta.tone}>{meta.label}</Badge>
            </div>
            {taskAttempts.length === 0 ? (
              <p className="px-4 py-3 text-sm text-muted-foreground">Ainda sem execution attempts.</p>
            ) : (
              <div className="divide-y divide-border">
                {taskAttempts.map((attempt, index) => {
                  const attemptMeta = jobStatusMeta(attempt.status);
                  const started = attempt.started_at ? new Date(attempt.started_at).getTime() : null;
                  const completed = attempt.completed_at ? new Date(attempt.completed_at).getTime() : null;
                  const duration = started && completed ? (completed - started) / 1000 : null;
                  return (
                    <div key={attempt.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm">
                      <span className="tabular w-8 shrink-0 text-xs text-muted-foreground">#{index + 1}</span>
                      <Badge tone={attemptMeta.tone} className="shrink-0">
                        {attemptMeta.label}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {agentLabelById.get(attempt.agent_id ?? "") ?? (attempt.agent_id ? `Agent ${attempt.agent_id.slice(0, 8)}` : "sem Agent")}
                      </span>
                      <span className="tabular text-xs text-muted-foreground">{formatDateTime(attempt.started_at)}</span>
                      <span className="tabular text-xs text-muted-foreground">{formatDuration(duration)}</span>
                      {attempt.failure_summary && <span className="text-xs text-destructive">{attempt.failure_summary}</span>}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
