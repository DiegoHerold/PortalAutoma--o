"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps, type NodeTypes } from "@xyflow/react";
import { AlertTriangle, GitMerge, GitFork, Loader2, Workflow, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { jobStatusMeta } from "@/lib/status";
import type { FlowCanvasNode } from "@/components/flows/editor/types";

const NODE_STYLES: Record<string, { icon: LucideIcon; accent: string; ring: string; bg: string }> = {
  automation: { icon: Workflow, accent: "text-primary", ring: "border-primary/40", bg: "bg-primary/5" },
  condition: { icon: GitFork, accent: "text-warning", ring: "border-warning/40", bg: "bg-warning/5" },
  join: { icon: GitMerge, accent: "text-info", ring: "border-info/40", bg: "bg-info/5" },
};

function BaseFlowNode({ data, selected }: NodeProps<FlowCanvasNode>) {
  const { flowNode, automationName, automationVersionLabel, issues, readOnly, runtimeStatus, runtimeMeta } = data;
  const style = NODE_STYLES[flowNode.node_type] ?? NODE_STYLES.automation;
  const Icon = style.icon;
  const hasIssues = issues.length > 0;
  const statusMeta = runtimeStatus ? jobStatusMeta(runtimeStatus) : null;
  const isRunning = runtimeStatus === "running";

  return (
    <div
      className={cn(
        "w-[240px] rounded-lg border-2 bg-card shadow-sm transition-shadow",
        hasIssues ? "border-destructive/60" : style.ring,
        selected && "shadow-lg ring-2 ring-primary/40",
        statusMeta && statusMeta.tone === "success" && "border-success/50",
        statusMeta && statusMeta.tone === "destructive" && "border-destructive/50",
      )}
    >
      <Handle type="target" position={Position.Top} className="!h-2.5 !w-2.5 !border-border !bg-muted-foreground" />

      <div className={cn("flex items-center gap-2 rounded-t-[6px] border-b border-border px-3 py-2", style.bg)}>
        <Icon className={cn("h-4 w-4 shrink-0", style.accent)} />
        <span className="truncate text-sm font-semibold">{flowNode.name || flowNode.key}</span>
        {isRunning && <Loader2 className="ml-auto h-3.5 w-3.5 shrink-0 animate-spin text-info" />}
        {hasIssues && !runtimeStatus && <AlertTriangle className="ml-auto h-3.5 w-3.5 shrink-0 text-destructive" />}
      </div>

      <div className="space-y-1.5 px-3 py-2.5 text-xs text-muted-foreground">
        <p className="truncate font-mono text-[11px]">{flowNode.key}</p>

        {flowNode.node_type === "automation" && (
          <p className="truncate">
            {automationName ?? (flowNode.automation_version_id ? `Automação #${flowNode.automation_version_id}` : "sem automação")}
            {automationVersionLabel && <span className="text-muted-foreground/70"> · {automationVersionLabel}</span>}
          </p>
        )}

        {flowNode.failure_policy !== "fail_flow" && (
          <p className="truncate text-[11px] text-muted-foreground/80">on fail: {failurePolicyLabel(flowNode.failure_policy)}</p>
        )}

        {runtimeStatus ? (
          <div className="flex items-center justify-between pt-1">
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[10px] font-medium",
                statusMeta?.tone === "success" && "bg-success/15 text-success",
                statusMeta?.tone === "destructive" && "bg-destructive/15 text-destructive",
                statusMeta?.tone === "info" && "bg-info/15 text-info",
                statusMeta?.tone === "warning" && "bg-warning/15 text-warning",
                statusMeta?.tone === "neutral" && "bg-muted text-muted-foreground",
              )}
            >
              {statusMeta?.label}
            </span>
            {runtimeMeta?.attemptNumber ? <span className="text-[10px]">tentativa {runtimeMeta.attemptNumber}</span> : null}
          </div>
        ) : (
          hasIssues && <p className="truncate text-[11px] font-medium text-destructive">{issues.length} problema(s)</p>
        )}

        {runtimeMeta?.agentLabel && <p className="truncate text-[11px]">{runtimeMeta.agentLabel}</p>}
      </div>

      <Handle type="source" position={Position.Bottom} className="!h-2.5 !w-2.5 !border-border !bg-muted-foreground" />
      {readOnly && <div className="pointer-events-none absolute inset-0 rounded-lg bg-transparent" />}
    </div>
  );
}

function failurePolicyLabel(policy: string): string {
  switch (policy) {
    case "continue":
      return "continuar";
    case "skip_dependents":
      return "pular dependentes";
    case "continue_alternative_path":
      return "caminho alternativo";
    default:
      return policy;
  }
}

export const FlowNodeComponent = memo(BaseFlowNode);

// O record NodeTypes do @xyflow/react é genérico sobre NodeProps<Node> (data: Record<string, unknown>);
// nosso componente é tipado especificamente para FlowCanvasNode, então o cast é necessário e seguro
// (o próprio React Flow só invoca cada renderer com nós do tipo registrado sob a mesma chave).
export const flowNodeTypes = {
  automation: FlowNodeComponent,
  condition: FlowNodeComponent,
  join: FlowNodeComponent,
} as unknown as NodeTypes;
