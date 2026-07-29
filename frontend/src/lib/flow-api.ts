import { apiRequest } from "@/lib/api";
import type {
  Flow,
  FlowEdge,
  FlowExecution,
  FlowExecutionDetails,
  FlowNode,
  FlowValidationResult,
  FlowVersion,
} from "@/types/flow";

// ---- Flow ----

export function createFlow(
  token: string,
  body: { key: string; name: string; description?: string | null; category_id?: number | null; tags?: string[] },
) {
  return apiRequest<Flow>("/flows", { method: "POST", token, body: JSON.stringify(body) });
}

export function updateFlow(
  token: string,
  flowId: string,
  body: Partial<{ name: string; description: string | null; category_id: number | null; tags: string[]; status: string }>,
) {
  return apiRequest<Flow>(`/flows/${flowId}`, { method: "PATCH", token, body: JSON.stringify(body) });
}

export function archiveFlow(token: string, flowId: string) {
  return apiRequest<Flow>(`/flows/${flowId}/archive`, { method: "POST", token });
}

export function listFlowVersions(token: string, flowId: string) {
  return apiRequest<FlowVersion[]>(`/flows/${flowId}/versions`, { token });
}

export function getFlowVersion(token: string, flowVersionId: string) {
  return apiRequest<FlowVersion>(`/flow-versions/${flowVersionId}`, { token });
}

export function listFlowNodes(token: string, flowVersionId: string) {
  return apiRequest<FlowNode[]>(`/flow-versions/${flowVersionId}/nodes`, { token });
}

export function listFlowEdges(token: string, flowVersionId: string) {
  return apiRequest<FlowEdge[]>(`/flow-versions/${flowVersionId}/edges`, { token });
}

export async function getFlowGraph(token: string, flowVersionId: string) {
  const [version, nodes, edges] = await Promise.all([
    getFlowVersion(token, flowVersionId),
    listFlowNodes(token, flowVersionId),
    listFlowEdges(token, flowVersionId),
  ]);
  return { version, nodes, edges };
}

// ---- FlowVersion ----

export function createFlowVersion(
  token: string,
  flowId: string,
  body: { version: string; definition?: Record<string, unknown>; input_schema?: Record<string, unknown> | null; output_schema?: Record<string, unknown> | null; release_notes?: string | null },
) {
  return apiRequest<FlowVersion>(`/flows/${flowId}/versions`, { method: "POST", token, body: JSON.stringify(body) });
}

export function updateFlowVersionDraft(
  token: string,
  flowVersionId: string,
  body: Partial<{ definition: Record<string, unknown>; input_schema: Record<string, unknown> | null; output_schema: Record<string, unknown> | null; release_notes: string | null }>,
) {
  return apiRequest<FlowVersion>(`/flow-versions/${flowVersionId}`, { method: "PATCH", token, body: JSON.stringify(body) });
}

export function validateFlowVersion(token: string, flowVersionId: string) {
  return apiRequest<FlowValidationResult>(`/flow-versions/${flowVersionId}/validate`, { method: "POST", token });
}

export function publishFlowVersion(token: string, flowVersionId: string) {
  return apiRequest<FlowVersion>(`/flow-versions/${flowVersionId}/publish`, { method: "POST", token });
}

export function deprecateFlowVersion(token: string, flowVersionId: string) {
  return apiRequest<FlowVersion>(`/flow-versions/${flowVersionId}/deprecate`, { method: "POST", token });
}

export function blockFlowVersion(token: string, flowVersionId: string) {
  return apiRequest<FlowVersion>(`/flow-versions/${flowVersionId}/block`, { method: "POST", token });
}

// ---- FlowNode / FlowEdge ----

export type FlowNodeInput = {
  key: string;
  name?: string | null;
  node_type?: string;
  automation_version_id?: number | null;
  configuration?: Record<string, unknown>;
  input_mapping?: Record<string, unknown>;
  output_mapping?: Record<string, unknown>;
  condition?: Record<string, unknown> | null;
  retry_policy?: Record<string, unknown>;
  timeout_policy?: Record<string, unknown>;
  failure_policy?: string;
  execution_policy?: Record<string, unknown>;
  position_metadata?: Record<string, unknown>;
};

export function addFlowNode(token: string, flowVersionId: string, body: FlowNodeInput) {
  return apiRequest<FlowNode>(`/flow-versions/${flowVersionId}/nodes`, { method: "POST", token, body: JSON.stringify(body) });
}

export function updateFlowNode(token: string, nodeId: string, body: Partial<FlowNodeInput>) {
  return apiRequest<FlowNode>(`/flow-nodes/${nodeId}`, { method: "PATCH", token, body: JSON.stringify(body) });
}

export function removeFlowNode(token: string, nodeId: string) {
  return apiRequest<void>(`/flow-nodes/${nodeId}`, { method: "DELETE", token });
}

export type FlowEdgeInput = {
  source_node_id: string;
  target_node_id: string;
  edge_type?: string;
  condition?: Record<string, unknown> | null;
  mapping?: Record<string, unknown>;
};

export function addFlowEdge(token: string, flowVersionId: string, body: FlowEdgeInput) {
  return apiRequest<FlowEdge>(`/flow-versions/${flowVersionId}/edges`, { method: "POST", token, body: JSON.stringify(body) });
}

export function removeFlowEdge(token: string, edgeId: string) {
  return apiRequest<void>(`/flow-edges/${edgeId}`, { method: "DELETE", token });
}

// ---- FlowExecution ----

export function createFlowExecution(
  token: string,
  body: { flow_version_id: string; input?: Record<string, unknown>; origin?: string },
) {
  return apiRequest<FlowExecutionDetails>("/flow-executions", { method: "POST", token, body: JSON.stringify(body) });
}

export function getFlowExecution(token: string, flowExecutionId: string) {
  return apiRequest<FlowExecutionDetails>(`/flow-executions/${flowExecutionId}`, { token });
}

export function cancelFlowExecution(token: string, flowExecutionId: string, reason?: string) {
  return apiRequest<FlowExecution>(`/flow-executions/${flowExecutionId}/cancel`, {
    method: "POST",
    token,
    body: JSON.stringify({ reason: reason ?? null }),
  });
}

/**
 * Clona todas as versões (com nós e arestas) de um Flow para outro, recém-criado.
 * Usado por "Duplicar" na lista de Fluxos e por "Criar nova versão a partir da publicada".
 * O backend não tem um endpoint de clonagem — a Ul monta a cópia chamando os
 * endpoints de criação em sequência, preservando IDs relativos via um mapa old->new.
 */
export async function cloneFlowVersionInto(
  token: string,
  targetFlowId: string,
  sourceVersion: FlowVersion,
  sourceNodes: FlowNode[],
  sourceEdges: FlowEdge[],
  newVersionLabel: string,
): Promise<FlowVersion> {
  const version = await createFlowVersion(token, targetFlowId, {
    version: newVersionLabel,
    definition: sourceVersion.definition,
    input_schema: sourceVersion.input_schema,
    output_schema: sourceVersion.output_schema,
    release_notes: sourceVersion.release_notes,
  });

  const nodeIdMap = new Map<string, string>();
  for (const node of sourceNodes) {
    const created = await addFlowNode(token, version.id, {
      key: node.key,
      name: node.name,
      node_type: node.node_type,
      automation_version_id: node.automation_version_id,
      configuration: node.configuration,
      input_mapping: node.input_mapping,
      output_mapping: node.output_mapping,
      condition: node.condition,
      retry_policy: node.retry_policy,
      timeout_policy: node.timeout_policy,
      failure_policy: node.failure_policy,
      execution_policy: node.execution_policy,
      position_metadata: node.position_metadata,
    });
    nodeIdMap.set(node.id, created.id);
  }

  for (const edge of sourceEdges) {
    const sourceId = nodeIdMap.get(edge.source_node_id);
    const targetId = nodeIdMap.get(edge.target_node_id);
    if (!sourceId || !targetId) continue;
    await addFlowEdge(token, version.id, {
      source_node_id: sourceId,
      target_node_id: targetId,
      edge_type: edge.edge_type,
      condition: edge.condition,
      mapping: edge.mapping,
    });
  }

  return version;
}

/** Escolhe a "melhor" versão para representar um Flow numa lista: publicada mais recente, senão o rascunho mais recente. */
export function pickHeadlineVersion(versions: FlowVersion[]): FlowVersion | null {
  if (versions.length === 0) return null;
  const published = versions.filter((v) => v.status === "published").sort((a, b) => b.created_at.localeCompare(a.created_at));
  if (published.length > 0) return published[0];
  return [...versions].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
}

export function nextSemver(versions: FlowVersion[]): string {
  let max = [0, 0, 0];
  for (const v of versions) {
    const match = /^(\d+)\.(\d+)\.(\d+)/.exec(v.version);
    if (!match) continue;
    const parts = [Number(match[1]), Number(match[2]), Number(match[3])];
    if (
      parts[0] > max[0] ||
      (parts[0] === max[0] && parts[1] > max[1]) ||
      (parts[0] === max[0] && parts[1] === max[1] && parts[2] > max[2])
    ) {
      max = parts;
    }
  }
  return `${max[0]}.${max[1]}.${max[2] + 1}`;
}
