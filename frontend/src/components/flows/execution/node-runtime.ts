// Deriva o estado visual de nós e conexões do canvas de monitoramento a partir dos dados
// reais retornados por GET /flow-executions/{id} (FlowNodeExecution.dependency_state já
// registra, por aresta de entrada, se ela foi satisfeita — ver
// backend/modules/orchestration/flows/application/use_cases.py::_dependency_decision).

import type { FlowCanvasEdgeData } from "@/components/flows/editor/types";
import type { ExecutionAttempt, FlowEdge, FlowNodeExecution, TaskExecution } from "@/types/flow";

export const TERMINAL_NODE_STATUSES = new Set(["succeeded", "failed", "cancelled", "timed_out", "skipped"]);

type DependencyRecord = { edge_id: string; source_node_id: string; edge_type: string; source_status: string | null; satisfied: boolean };

export function nodeExecutionFor(nodeExecutions: FlowNodeExecution[], flowNodeId: string): FlowNodeExecution | undefined {
  return nodeExecutions.find((ne) => ne.flow_node_id === flowNodeId);
}

export function taskFor(tasks: TaskExecution[], taskExecutionId: string | null | undefined): TaskExecution | undefined {
  if (!taskExecutionId) return undefined;
  return tasks.find((t) => t.id === taskExecutionId);
}

export function attemptsFor(attempts: ExecutionAttempt[], taskExecutionId: string | null | undefined): ExecutionAttempt[] {
  if (!taskExecutionId) return [];
  return attempts
    .filter((a) => a.task_execution_id === taskExecutionId)
    .sort((a, b) => (a.offered_at ?? "").localeCompare(b.offered_at ?? ""));
}

export function agentLabelFor(agentId: string | null | undefined, agentNameById: Map<string, string>): string | null {
  if (!agentId) return null;
  const name = agentNameById.get(agentId);
  return name ? name : `Agent ${agentId.slice(0, 8)}`;
}

export function edgeRuntimeState(
  edge: FlowEdge,
  sourceExec: FlowNodeExecution | undefined,
  targetExec: FlowNodeExecution | undefined,
): FlowCanvasEdgeData["runtimeState"] {
  const deps = (targetExec?.dependency_state as { dependencies?: DependencyRecord[] } | undefined)?.dependencies;
  const dep = deps?.find((d) => d.edge_id === edge.id);

  if (dep) {
    if (!dep.satisfied) {
      const sourceTerminal = sourceExec ? TERMINAL_NODE_STATUSES.has(sourceExec.status) : false;
      return sourceTerminal ? "skipped" : "waiting";
    }
    switch (targetExec?.status) {
      case "pending":
      case "blocked":
        return "released";
      case "running":
        return "running";
      case "succeeded":
        return "done";
      case "failed":
      case "timed_out":
      case "cancelled":
        return "failed";
      case "skipped":
        return "skipped";
      default:
        return "released";
    }
  }

  // Sem dependency_state ainda registrado (nó de destino nunca avaliado) — estimativa a partir do nó de origem.
  if (!sourceExec || sourceExec.status === "pending" || sourceExec.status === "blocked" || sourceExec.status === "running") {
    return "waiting";
  }
  if (sourceExec.status === "skipped") return "skipped";
  const matches =
    edge.edge_type === "success"
      ? sourceExec.status === "succeeded"
      : edge.edge_type === "failure"
        ? ["failed", "timed_out", "cancelled"].includes(sourceExec.status)
        : true; // always / conditional — sem melhor informação, assume que pode ter sido percorrida
  return matches ? "released" : "skipped";
}

export function flowProgress(nodeExecutions: FlowNodeExecution[]): { done: number; total: number; percentage: number } {
  const total = nodeExecutions.length;
  const done = nodeExecutions.filter((ne) => TERMINAL_NODE_STATUSES.has(ne.status)).length;
  return { done, total, percentage: total > 0 ? Math.round((done / total) * 100) : 0 };
}
