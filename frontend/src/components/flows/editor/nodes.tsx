"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps, type NodeTypes } from "@xyflow/react";
import { AlertTriangle, GitFork, Loader2, Workflow, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { jobStatusMeta } from "@/lib/status";
import type { FlowCanvasNode } from "@/components/flows/editor/types";
import type { FlowNode } from "@/types/flow";
import { conditionBlockFor } from "@/components/flows/editor/block-catalog";
import { describeCondition } from "@/components/flows/editor/condition-editor";
import { ifElseRule, switchConfigOf } from "@/components/flows/editor/branch-logic";

// Estilo dos tipos "históricos", mantidos como estavam para não mudar a aparência de Flows
// já publicados. Os demais tipos (if_else, switch, join, merge, set_variable, map_fields,
// transform_data) buscam ícone/cor em block-catalog.ts — a mesma fonte usada pelo catálogo
// lateral — para que o nó no canvas seja reconhecível sem abrir a configuração.
const LEGACY_NODE_STYLES: Record<string, { icon: LucideIcon; accent: string; ring: string; bg: string }> = {
  automation: { icon: Workflow, accent: "text-primary", ring: "border-primary/40", bg: "bg-primary/5" },
  condition: { icon: GitFork, accent: "text-warning", ring: "border-warning/40", bg: "bg-warning/5" },
};

function styleFor(nodeType: string) {
  const legacy = LEGACY_NODE_STYLES[nodeType];
  if (legacy) return legacy;
  const block = conditionBlockFor(nodeType);
  if (block) return block.style;
  return LEGACY_NODE_STYLES.automation;
}

function dependencyLabel(node: FlowNode): string {
  return (node.execution_policy as Record<string, unknown> | undefined)?.dependency_policy === "any"
    ? "Continua com a primeira entrada"
    : "Espera todas as entradas";
}

function nodeSummary(node: FlowNode): string | null {
  switch (node.node_type) {
    case "condition":
      return "Libera a próxima etapa quando a regra for atendida.";
    case "join":
      return dependencyLabel(node);
    case "merge":
      return `${dependencyLabel(node)} · combina os campos em um único objeto.`;
    case "if_else": {
      const rule = ifElseRule(node);
      return rule ? describeCondition(rule) : "Sem regra definida — Verdadeiro sempre segue.";
    }
    case "switch": {
      const { cases, hasDefault } = switchConfigOf(node);
      if (cases.length === 0) return "Nenhum caso configurado ainda.";
      const labels = cases.map((c) => c.label || String(c.value)).join(", ");
      return hasDefault ? `${labels} + padrão` : labels;
    }
    case "set_variable": {
      const keys = Object.keys(node.input_mapping || {});
      return keys.length ? `define: ${keys.join(", ")}` : "Nenhuma variável definida ainda.";
    }
    case "map_fields": {
      const count = Object.keys(node.input_mapping || {}).length;
      return count ? `${count} campo(s) mapeado(s)` : "Nenhum campo mapeado ainda.";
    }
    case "transform_data": {
      const transforms = new Set<string>();
      for (const spec of Object.values(node.input_mapping || {})) {
        const t = (spec as { transform?: string | string[] } | undefined)?.transform;
        if (Array.isArray(t)) t.forEach((item) => transforms.add(item));
        else if (t) transforms.add(t);
      }
      return transforms.size ? Array.from(transforms).join(" · ") : "Nenhuma transformação definida ainda.";
    }
    default:
      return null;
  }
}

function ConvergingInputMarks() {
  return (
    <div className="pointer-events-none absolute -top-2.5 left-1/2 flex -translate-x-1/2 gap-1.5">
      <span className="h-1.5 w-1.5 rounded-full bg-border" />
      <span className="h-1.5 w-1.5 rounded-full bg-border" />
      <span className="h-1.5 w-1.5 rounded-full bg-border" />
    </div>
  );
}

function BranchOutputHandle({ id, leftPercent, label, dotClassName }: { id: string; leftPercent: number; label: string; dotClassName: string }) {
  return (
    <>
      <span
        className="pointer-events-none absolute -bottom-5 max-w-[90px] truncate whitespace-nowrap text-center text-xs font-medium text-muted-foreground"
        style={{ left: `${leftPercent}%`, transform: "translateX(-50%)" }}
        title={label}
      >
        {label}
      </span>
      <Handle
        type="source"
        position={Position.Bottom}
        id={id}
        style={{ left: `${leftPercent}%` }}
        className={cn("!h-2.5 !w-2.5 !border-border", dotClassName)}
      />
    </>
  );
}

/** Handles de saída coerentes com a função do bloco: um If/Else tem Verdadeiro/Falso, um
 * Switch tem um handle por caso + padrão, os demais têm uma única saída "Próxima etapa". */
function OutputHandles({ node }: { node: FlowNode }) {
  if (node.node_type === "if_else") {
    return (
      <>
        <BranchOutputHandle id="true" leftPercent={30} label="Verdadeiro" dotClassName="!bg-success" />
        <BranchOutputHandle id="false" leftPercent={70} label="Falso" dotClassName="!bg-destructive" />
      </>
    );
  }

  if (node.node_type === "switch") {
    const { cases, hasDefault } = switchConfigOf(node);
    const items: { id: string; label: string }[] = cases.map((c) => ({ id: c.id, label: c.label || String(c.value) }));
    if (hasDefault || items.length === 0) items.push({ id: "default", label: "Padrão" });
    const count = items.length;
    return (
      <>
        {items.map((item, index) => (
          <BranchOutputHandle
            key={item.id}
            id={item.id}
            leftPercent={((index + 1) / (count + 1)) * 100}
            label={item.label}
            dotClassName={item.id === "default" ? "!bg-muted-foreground" : "!bg-violet-500"}
          />
        ))}
      </>
    );
  }

  const label = node.node_type === "join" || node.node_type === "merge" ? "Continuar" : "Próxima etapa";
  return (
    <>
      <span className="pointer-events-none absolute -bottom-5 left-1/2 -translate-x-1/2 whitespace-nowrap text-xs font-medium text-muted-foreground">{label}</span>
      <Handle type="source" position={Position.Bottom} className="!h-2.5 !w-2.5 !border-border !bg-muted-foreground" />
    </>
  );
}

function BaseFlowNode({ data, selected }: NodeProps<FlowCanvasNode>) {
  const { flowNode, automationName, automationVersionLabel, issues, readOnly, runtimeStatus, runtimeMeta } = data;
  const style = styleFor(flowNode.node_type);
  const Icon = style.icon;
  const hasIssues = issues.length > 0;
  const statusMeta = runtimeStatus ? jobStatusMeta(runtimeStatus) : null;
  const isRunning = runtimeStatus === "running";
  const summary = nodeSummary(flowNode);
  const isMultiInput = flowNode.node_type === "join" || flowNode.node_type === "merge";
  const isSwitch = flowNode.node_type === "switch";
  const switchCaseCount = isSwitch ? switchConfigOf(flowNode).cases.length + (switchConfigOf(flowNode).hasDefault ? 1 : 0) : 0;
  const width = isSwitch ? Math.min(480, Math.max(240, 40 + Math.max(switchCaseCount, 1) * 90)) : 240;

  return (
    <div
      style={{ width }}
      className={cn(
        "rounded-lg border-2 bg-card shadow-sm transition-shadow",
        hasIssues ? "border-destructive/60" : style.ring,
        selected && "shadow-lg ring-2 ring-primary/40",
        statusMeta && statusMeta.tone === "success" && "border-success/50",
        statusMeta && statusMeta.tone === "destructive" && "border-destructive/50",
      )}
    >
      {isMultiInput && <ConvergingInputMarks />}
      <span className="pointer-events-none absolute -top-5 left-1/2 -translate-x-1/2 whitespace-nowrap text-xs font-medium text-muted-foreground">
        {isMultiInput ? "Entradas" : "Entrada"}
      </span>
      <Handle type="target" position={Position.Top} className="!h-2.5 !w-2.5 !border-border !bg-muted-foreground" />

      <div className={cn("flex items-center gap-2 rounded-t-[6px] border-b border-border px-3 py-2", style.bg)}>
        <Icon className={cn("h-4 w-4 shrink-0", style.accent)} />
        <span className="truncate text-sm font-semibold">{flowNode.name || flowNode.key}</span>
        {isRunning && <Loader2 className="ml-auto h-3.5 w-3.5 shrink-0 animate-spin text-info" />}
        {hasIssues && !runtimeStatus && <AlertTriangle className="ml-auto h-3.5 w-3.5 shrink-0 text-destructive" />}
      </div>

      <div className="space-y-1.5 px-3 py-2.5 text-xs text-muted-foreground">
        <p className="truncate font-mono text-xs">{flowNode.key}</p>

        {flowNode.node_type === "automation" && (
          <p className="truncate">
            {automationName ?? (flowNode.automation_version_id ? `Automação #${flowNode.automation_version_id}` : "sem automação")}
            {automationVersionLabel && <span className="text-muted-foreground/70"> · {automationVersionLabel}</span>}
          </p>
        )}

        {summary && <p className="leading-4 text-muted-foreground">{summary}</p>}

        {flowNode.failure_policy !== "fail_flow" && (
          <p className="truncate text-xs text-muted-foreground/80">on fail: {failurePolicyLabel(flowNode.failure_policy)}</p>
        )}

        {runtimeStatus ? (
          <div className="flex items-center justify-between pt-1">
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-xs font-medium",
                statusMeta?.tone === "success" && "bg-success/15 text-success",
                statusMeta?.tone === "destructive" && "bg-destructive/15 text-destructive",
                statusMeta?.tone === "info" && "bg-info/15 text-info",
                statusMeta?.tone === "warning" && "bg-warning/15 text-warning",
                statusMeta?.tone === "neutral" && "bg-muted text-muted-foreground",
              )}
            >
              {statusMeta?.label}
            </span>
            {runtimeMeta?.attemptNumber ? <span className="text-xs">tentativa {runtimeMeta.attemptNumber}</span> : null}
          </div>
        ) : (
          hasIssues && <p className="truncate text-xs font-medium text-destructive">{issues.length} problema(s)</p>
        )}

        {runtimeMeta?.agentLabel && <p className="truncate text-xs">{runtimeMeta.agentLabel}</p>}
      </div>

      <OutputHandles node={flowNode} />
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
  if_else: FlowNodeComponent,
  switch: FlowNodeComponent,
  merge: FlowNodeComponent,
  set_variable: FlowNodeComponent,
  map_fields: FlowNodeComponent,
  transform_data: FlowNodeComponent,
} as unknown as NodeTypes;
