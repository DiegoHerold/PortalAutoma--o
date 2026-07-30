"use client";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { jobStatusMeta } from "@/lib/status";
import { formatDateTime, formatDuration } from "@/lib/utils";

type TaskExecutionLike = {
  id: string;
  status: string;
  created_at?: string | null;
  current_attempt_number?: number | null;
  scheduling_attempts?: number | null;
  failure_summary?: string | null;
};

type ExecutionAttemptLike = {
  id: string;
  task_execution_id: string;
  attempt_number?: number | null;
  agent_id?: string | null;
  status: string;
  offered_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  failure_summary?: string | null;
  error_message?: string | null;
  error_code?: string | null;
};

export function AttemptsTab({
  tasks,
  attempts,
  loading,
  error,
  onRetry,
  nodeLabelByTask,
  agentLabelById,
  onRetryTask,
  retryingTaskId,
}: {
  tasks: TaskExecutionLike[];
  attempts: ExecutionAttemptLike[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  nodeLabelByTask: Map<string, string>;
  agentLabelById: Map<string, string>;
  onRetryTask?: (taskId: string, sourceAttemptId?: string | null) => void;
  retryingTaskId?: string | null;
}) {
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (loading) return <Skeleton className="h-40 rounded-lg" />;
  if (tasks.length === 0) {
    return <EmptyState title="Sem tentativas" description="Nenhuma task foi despachada ainda." />;
  }

  const sortedTasks = [...tasks].sort((a, b) => (a.created_at ?? "").localeCompare(b.created_at ?? ""));

  return (
    <div className="space-y-4">
      {sortedTasks.map((task) => {
        const taskAttempts = attempts
          .filter((a) => a.task_execution_id === task.id)
          .sort((a, b) => (a.offered_at ?? "").localeCompare(b.offered_at ?? ""));
        const meta = jobStatusMeta(task.status);
        const latestAttempt = taskAttempts[taskAttempts.length - 1] ?? null;
        return (
          <div key={task.id} className="overflow-hidden rounded-lg border border-border bg-card">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-muted/30 px-4 py-2.5">
              <div>
                <p className="font-medium">{nodeLabelByTask.get(task.id) ?? `Task ${task.id.slice(0, 8)}`}</p>
                <p className="text-xs text-muted-foreground">
                  {task.scheduling_attempts ?? 0} tentativa(s) de agendamento - tentativa atual #{task.current_attempt_number ?? 0}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={meta.tone}>{meta.label}</Badge>
                {onRetryTask && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onRetryTask(task.id, latestAttempt?.id ?? null)}
                    disabled={retryingTaskId === task.id}
                  >
                    {retryingTaskId === task.id ? "Reagendando..." : "Retry"}
                  </Button>
                )}
              </div>
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
                  const failure = attempt.failure_summary ?? attempt.error_message ?? null;
                  return (
                    <div key={attempt.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm">
                      <span className="tabular w-8 shrink-0 text-xs text-muted-foreground">#{attempt.attempt_number ?? index + 1}</span>
                      <Badge tone={attemptMeta.tone} className="shrink-0">
                        {attemptMeta.label}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {agentLabelById.get(attempt.agent_id ?? "") ?? (attempt.agent_id ? `Agent ${attempt.agent_id.slice(0, 8)}` : "sem Agent")}
                      </span>
                      <span className="tabular text-xs text-muted-foreground">{formatDateTime(attempt.started_at)}</span>
                      <span className="tabular text-xs text-muted-foreground">{formatDuration(duration)}</span>
                      {failure && <span className="text-xs text-destructive">{failure}</span>}
                      {attempt.error_code && <span className="tabular text-xs text-muted-foreground">{attempt.error_code}</span>}
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
