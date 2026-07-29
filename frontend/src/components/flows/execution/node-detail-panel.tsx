"use client";

import { AlertTriangle, FileText, Layers, ScrollText } from "lucide-react";

import { Sheet } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DetailJson } from "@/components/shared/detail-json";
import { jobStatusMeta } from "@/lib/status";
import { formatDateTime, formatDuration } from "@/lib/utils";
import type { ExecutionAttempt, FlowNode, FlowNodeExecution, TaskExecution } from "@/types/flow";

export function NodeDetailPanel({
  node,
  nodeExecution,
  task,
  attempts,
  agentLabel,
  logCount,
  artifactCount,
  lastMessage,
  onClose,
  onViewLogs,
}: {
  node: FlowNode | null;
  nodeExecution: FlowNodeExecution | undefined;
  task: TaskExecution | undefined;
  attempts: ExecutionAttempt[];
  agentLabel: string | null;
  logCount: number;
  artifactCount: number;
  lastMessage: string | null;
  onClose: () => void;
  onViewLogs: () => void;
}) {
  if (!node) return null;
  const status = nodeExecution?.status ?? "pending";
  const meta = jobStatusMeta(status);
  const started = nodeExecution?.started_at ? new Date(nodeExecution.started_at).getTime() : null;
  const completed = nodeExecution?.completed_at ? new Date(nodeExecution.completed_at).getTime() : null;
  const duration = started && completed ? (completed - started) / 1000 : null;
  const currentAttempt = attempts[attempts.length - 1];

  return (
    <Sheet
      open={Boolean(node)}
      onClose={onClose}
      title={node.name || node.key}
      description={`${node.node_type} · ${node.key}`}
      widthClassName="w-full sm:max-w-lg"
    >
      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <Badge tone={meta.tone}>{meta.label}</Badge>
          {node.node_type === "automation" && (
            <Button size="sm" variant="outline" onClick={onViewLogs}>
              <ScrollText className="h-3.5 w-3.5" /> Ver logs deste nó
            </Button>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <InfoRow label="Agent" value={agentLabel ?? "—"} />
          <InfoRow label="Tentativa atual" value={task ? `#${task.current_attempt_number}` : "—"} />
          <InfoRow label="Tentativas (scheduling)" value={task ? String(task.scheduling_attempts) : "—"} />
          <InfoRow label="Retries configurados" value={String((node.retry_policy as Record<string, unknown>)?.max_retries ?? 0)} />
          <InfoRow label="Início" value={formatDateTime(nodeExecution?.started_at)} />
          <InfoRow label="Fim" value={formatDateTime(nodeExecution?.completed_at)} />
          <InfoRow label="Duração" value={formatDuration(duration)} />
          <InfoRow label="Revisão" value={nodeExecution ? String(nodeExecution.revision) : "—"} />
        </div>

        <div className="flex gap-4 border-t border-border pt-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <ScrollText className="h-3.5 w-3.5" /> {logCount} log(s)
          </span>
          <span className="flex items-center gap-1">
            <FileText className="h-3.5 w-3.5" /> {artifactCount} artefato(s)
          </span>
          <span className="flex items-center gap-1">
            <Layers className="h-3.5 w-3.5" /> {attempts.length} execution attempt(s)
          </span>
        </div>

        {nodeExecution?.failure_summary && (
          <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {nodeExecution.failure_summary}
          </div>
        )}

        {lastMessage && (
          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
            <p className="mb-1 font-medium text-foreground">Última mensagem</p>
            {lastMessage}
          </div>
        )}

        {currentAttempt && (
          <div>
            <p className="mb-1.5 text-xs font-medium text-muted-foreground">Tentativa atual (execution attempt)</p>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <InfoRow label="Status" value={jobStatusMeta(currentAttempt.status).label} />
              <InfoRow label="Aceita em" value={formatDateTime(currentAttempt.accepted_at)} />
              <InfoRow label="Iniciada em" value={formatDateTime(currentAttempt.started_at)} />
              <InfoRow label="Concluída em" value={formatDateTime(currentAttempt.completed_at)} />
            </div>
          </div>
        )}

        {nodeExecution?.input && Object.keys(nodeExecution.input).length > 0 && (
          <div>
            <p className="mb-1.5 text-xs font-medium text-muted-foreground">Entrada (após mapeamento)</p>
            <DetailJson data={nodeExecution.input} />
          </div>
        )}

        {nodeExecution?.output && Object.keys(nodeExecution.output).length > 0 && (
          <div>
            <p className="mb-1.5 text-xs font-medium text-muted-foreground">Saída</p>
            <DetailJson data={nodeExecution.output} />
          </div>
        )}
      </div>
    </Sheet>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="tabular font-medium">{value}</p>
    </div>
  );
}
