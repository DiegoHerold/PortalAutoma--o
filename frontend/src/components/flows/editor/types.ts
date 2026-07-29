import type { Node, Edge } from "@xyflow/react";
import type { FlowEdgeType, FlowNode, FlowValidationIssue } from "@/types/flow";

export type FlowCanvasNodeData = {
  flowNode: FlowNode;
  automationName?: string;
  automationVersionLabel?: string;
  issues: FlowValidationIssue[];
  readOnly: boolean;
  /** Estado real de execução, presente apenas na tela de monitoramento (/flow-executions/[id]). */
  runtimeStatus?: string | null;
  runtimeMeta?: {
    attemptNumber?: number | null;
    agentLabel?: string | null;
    startedAt?: string | null;
    completedAt?: string | null;
    lastMessage?: string | null;
    logCount?: number;
    artifactCount?: number;
  };
  [key: string]: unknown;
};

export type FlowCanvasNode = Node<FlowCanvasNodeData, string>;

export type FlowCanvasEdgeData = {
  edgeType: FlowEdgeType;
  condition: Record<string, unknown> | null;
  hasMapping: boolean;
  issues: FlowValidationIssue[];
  readOnly: boolean;
  /** Estado de execução do caminho, presente apenas no monitoramento. */
  runtimeState?: "waiting" | "released" | "running" | "done" | "skipped" | "failed" | null;
  [key: string]: unknown;
};

export type FlowCanvasEdge = Edge<FlowCanvasEdgeData, string>;
