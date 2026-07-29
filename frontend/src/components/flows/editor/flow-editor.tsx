"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  Panel,
  MarkerType,
  useNodesState,
  useEdgesState,
  type Connection,
  type NodeMouseHandler,
  type EdgeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Plus, Wand2, ShieldCheck, Rocket, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { useApi } from "@/hooks/use-api";
import { flowNodeTypes } from "@/components/flows/editor/nodes";
import { NodePanel, type NodeConfigPatch } from "@/components/flows/editor/node-panel";
import { EdgePanel } from "@/components/flows/editor/edge-panel";
import { ValidationSummary } from "@/components/flows/editor/validation-panel";
import type { FlowCanvasEdge, FlowCanvasNode } from "@/components/flows/editor/types";
import {
  addFlowEdge,
  addFlowNode,
  getFlowVersion,
  listFlowEdges,
  listFlowNodes,
  publishFlowVersion,
  removeFlowEdge,
  removeFlowNode,
  updateFlowNode,
  validateFlowVersion,
} from "@/lib/flow-api";
import { apiRequest } from "@/lib/api";
import type { Automation } from "@/types/automation";
import type { AutomationVersion } from "@/types/automation-import";
import type { FlowEdge, FlowNode, FlowValidationIssue, FlowValidationResult, FlowVersion } from "@/types/flow";

const EDGE_COLOR: Record<string, string> = {
  success: "hsl(var(--success))",
  failure: "hsl(var(--destructive))",
  always: "hsl(var(--muted-foreground))",
  conditional: "hsl(var(--info))",
};

function issuesForNode(nodeId: string, issues: FlowValidationIssue[]): FlowValidationIssue[] {
  return issues.filter((issue) => (issue.details as { node_id?: string })?.node_id === nodeId);
}

function issuesForEdge(edgeId: string, issues: FlowValidationIssue[]): FlowValidationIssue[] {
  return issues.filter((issue) => (issue.details as { edge_id?: string })?.edge_id === edgeId);
}

function toRFNode(fn: FlowNode, issues: FlowValidationIssue[], readOnly: boolean, label: { name?: string; version?: string }): FlowCanvasNode {
  return {
    id: fn.id,
    type: fn.node_type,
    position: { x: Number(fn.position_metadata?.x ?? 0), y: Number(fn.position_metadata?.y ?? 0) },
    deletable: false,
    data: {
      flowNode: fn,
      issues: issuesForNode(fn.id, issues),
      readOnly,
      automationName: label.name,
      automationVersionLabel: label.version,
    },
  };
}

function toRFEdge(fe: FlowEdge, issues: FlowValidationIssue[], readOnly: boolean): FlowCanvasEdge {
  const edgeIssues = issuesForEdge(fe.id, issues);
  const hasIssues = edgeIssues.length > 0;
  const color = hasIssues ? "hsl(var(--destructive))" : EDGE_COLOR[fe.edge_type] ?? EDGE_COLOR.success;
  return {
    id: fe.id,
    source: fe.source_node_id,
    target: fe.target_node_id,
    deletable: false,
    label: hasIssues ? "problema" : fe.edge_type !== "success" ? fe.edge_type : undefined,
    style: { stroke: color, strokeWidth: hasIssues ? 3 : 2, strokeDasharray: hasIssues ? "4 3" : undefined },
    markerEnd: { type: MarkerType.ArrowClosed, color },
    data: { edgeType: fe.edge_type, condition: fe.condition, hasMapping: Object.keys(fe.mapping || {}).length > 0, issues: edgeIssues, readOnly },
  };
}

let nodeKeySeq = 0;
function generateNodeKey(nodeType: string) {
  nodeKeySeq += 1;
  return `${nodeType}_${Date.now().toString(36)}_${nodeKeySeq}`;
}

export function FlowEditor({
  flowVersion,
  onVersionChange,
}: {
  flowVersion: FlowVersion;
  onVersionChange: (version: FlowVersion) => void;
}) {
  const { token } = useAuth();
  const { toast } = useToast();
  const readOnly = flowVersion.status !== "draft";

  const [flowNodesRaw, setFlowNodesRaw] = useState<FlowNode[]>([]);
  const [flowEdgesRaw, setFlowEdgesRaw] = useState<FlowEdge[]>([]);
  const [loading, setLoading] = useState(true);
  const [validation, setValidation] = useState<FlowValidationResult | null>(null);
  const [validating, setValidating] = useState(false);
  const [publishing, setPublishing] = useState(false);

  const [nodes, setNodes, onNodesChange] = useNodesState<FlowCanvasNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowCanvasEdge>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);

  const automations = useApi<Automation[]>("/automations");
  const [automationVersions, setAutomationVersions] = useState<AutomationVersion[]>([]);
  const loadedAutomationIds = useRef(new Set<number>());

  const positionHistory = useRef<{ nodeId: string; previous: { x: number; y: number } }[]>([]);

  // Carrega nós/arestas desta versão e roda validação inicial.
  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const [rawNodes, rawEdges] = await Promise.all([listFlowNodes(token, flowVersion.id), listFlowEdges(token, flowVersion.id)]);
      setFlowNodesRaw(rawNodes);
      setFlowEdgesRaw(rawEdges);
      const automationVersionIds = Array.from(new Set(rawNodes.map((n) => n.automation_version_id).filter(Boolean))) as number[];
      const versionLookups = await Promise.all(
        automationVersionIds.map(async (id) => {
          try {
            return await apiRequest<AutomationVersion>(`/automation-versions/${id}`, { token });
          } catch {
            return null;
          }
        }),
      );
      setAutomationVersions((prev) => {
        const map = new Map(prev.map((v) => [v.id, v]));
        versionLookups.forEach((v) => v && map.set(v.id, v));
        return Array.from(map.values());
      });
      let result: FlowValidationResult | null = null;
      try {
        result = await validateFlowVersion(token, flowVersion.id);
      } catch {
        result = null;
      }
      setValidation(result);
    } catch (err) {
      toast({ title: "Falha ao carregar o Fluxo", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, flowVersion.id]);

  useEffect(() => {
    void load();
  }, [load]);

  const automationLabelFor = useCallback(
    (versionId: number | null) => {
      if (!versionId) return {};
      const version = automationVersions.find((v) => v.id === versionId);
      if (!version) return {};
      const automation = automations.data?.find((a) => a.id === version.automation_id);
      return { name: automation?.name, version: `v${version.version}` };
    },
    [automationVersions, automations.data],
  );

  // Reconstrói o grafo do React Flow sempre que os dados de domínio, validação ou labels mudarem.
  useEffect(() => {
    setNodes(flowNodesRaw.map((fn) => toRFNode(fn, validation?.issues ?? [], readOnly, automationLabelFor(fn.automation_version_id))));
    setEdges(flowEdgesRaw.map((fe) => toRFEdge(fe, validation?.issues ?? [], readOnly)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flowNodesRaw, flowEdgesRaw, validation, readOnly, automationVersions, automations.data]);

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) ?? null;
  const selectedEdge = edges.find((e) => e.id === selectedEdgeId) ?? null;

  const upstreamNodesFor = useCallback(
    (nodeId: string | null) => {
      if (!nodeId) return [];
      const ancestorIds = new Set<string>();
      const queue = [nodeId];
      while (queue.length) {
        const current = queue.pop()!;
        flowEdgesRaw.filter((e) => e.target_node_id === current).forEach((e) => {
          if (!ancestorIds.has(e.source_node_id)) {
            ancestorIds.add(e.source_node_id);
            queue.push(e.source_node_id);
          }
        });
      }
      return flowNodesRaw.filter((n) => ancestorIds.has(n.id)).map((n) => ({ key: n.key, name: n.name || n.key }));
    },
    [flowEdgesRaw, flowNodesRaw],
  );

  // Nós cuja saída pode ser referenciada na condição de uma conexão: o próprio nó de origem
  // (acabou de rodar) mais tudo que já rodou antes dele.
  const edgeUpstreamNodesFor = useCallback(
    (edgeSourceId: string | null) => {
      if (!edgeSourceId) return [];
      const sourceNode = flowNodesRaw.find((n) => n.id === edgeSourceId);
      const list = sourceNode ? [{ key: sourceNode.key, name: sourceNode.name || sourceNode.key }, ...upstreamNodesFor(edgeSourceId)] : upstreamNodesFor(edgeSourceId);
      const seen = new Set<string>();
      return list.filter((n) => (seen.has(n.key) ? false : (seen.add(n.key), true)));
    },
    [flowNodesRaw, upstreamNodesFor],
  );

  async function runValidation() {
    if (!token) return;
    setValidating(true);
    try {
      const result = await validateFlowVersion(token, flowVersion.id);
      setValidation(result);
      toast({ title: result.valid ? "Fluxo válido" : `${result.issues.length} problema(s) encontrado(s)`, kind: result.valid ? "success" : "warning" });
    } catch (err) {
      toast({ title: "Falha ao validar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setValidating(false);
    }
  }

  async function handlePublish() {
    if (!token) return;
    setPublishing(true);
    try {
      const fresh = await validateFlowVersion(token, flowVersion.id);
      setValidation(fresh);
      if (!fresh.valid) {
        toast({ title: "Corrija os problemas antes de publicar", kind: "error" });
        return;
      }
      const updated = await publishFlowVersion(token, flowVersion.id);
      toast({ title: "Versão publicada", kind: "success" });
      onVersionChange(updated);
    } catch (err) {
      toast({ title: "Falha ao publicar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setPublishing(false);
    }
  }

  async function handleAddNode(nodeType: "automation" | "condition" | "join") {
    if (!token) return;
    const key = generateNodeKey(nodeType);
    const position = { x: 120 + Math.random() * 80, y: 80 + flowNodesRaw.length * 40 };
    try {
      const created = await addFlowNode(token, flowVersion.id, {
        key,
        name: nodeType === "automation" ? "Nova automação" : nodeType === "condition" ? "Nova condição" : "Novo join",
        node_type: nodeType,
        position_metadata: position,
      });
      setFlowNodesRaw((prev) => [...prev, created]);
      setSelectedNodeId(created.id);
    } catch (err) {
      toast({ title: "Falha ao adicionar nó", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function handleNodeSave(patch: NodeConfigPatch) {
    if (!token || !selectedNode) return;
    try {
      const updated = await updateFlowNode(token, selectedNode.id, patch);
      setFlowNodesRaw((prev) => prev.map((n) => (n.id === updated.id ? updated : n)));
      toast({ title: "Nó atualizado", kind: "success" });
      setSelectedNodeId(null);
      void runValidation();
    } catch (err) {
      toast({ title: "Falha ao salvar nó", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function handleNodeDelete() {
    if (!token || !selectedNode) return;
    if (!window.confirm(`Remover o nó "${selectedNode.data.flowNode.name}"? As conexões ligadas a ele também serão removidas.`)) return;
    try {
      await removeFlowNode(token, selectedNode.id);
      setFlowNodesRaw((prev) => prev.filter((n) => n.id !== selectedNode.id));
      setFlowEdgesRaw((prev) => prev.filter((e) => e.source_node_id !== selectedNode.id && e.target_node_id !== selectedNode.id));
      setSelectedNodeId(null);
      void runValidation();
    } catch (err) {
      toast({ title: "Falha ao remover nó", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function handleNodeDuplicate() {
    if (!token || !selectedNode) return;
    const fn = selectedNode.data.flowNode;
    try {
      const created = await addFlowNode(token, flowVersion.id, {
        key: generateNodeKey(fn.node_type),
        name: `${fn.name} (cópia)`,
        node_type: fn.node_type,
        automation_version_id: fn.automation_version_id,
        configuration: fn.configuration,
        input_mapping: fn.input_mapping,
        output_mapping: fn.output_mapping,
        condition: fn.condition,
        retry_policy: fn.retry_policy,
        timeout_policy: fn.timeout_policy,
        failure_policy: fn.failure_policy,
        execution_policy: fn.execution_policy,
        position_metadata: { x: Number(fn.position_metadata?.x ?? 0) + 60, y: Number(fn.position_metadata?.y ?? 0) + 60 },
      });
      setFlowNodesRaw((prev) => [...prev, created]);
      toast({ title: "Nó duplicado", kind: "success" });
    } catch (err) {
      toast({ title: "Falha ao duplicar nó", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function handleEdgeSave(patch: { edge_type: FlowEdge["edge_type"]; condition: Record<string, unknown> | null }) {
    if (!token || !selectedEdge) return;
    try {
      await removeFlowEdge(token, selectedEdge.id);
      const created = await addFlowEdge(token, flowVersion.id, {
        source_node_id: selectedEdge.source,
        target_node_id: selectedEdge.target,
        edge_type: patch.edge_type,
        condition: patch.condition,
      });
      setFlowEdgesRaw((prev) => [...prev.filter((e) => e.id !== selectedEdge.id), created]);
      toast({ title: "Conexão atualizada", kind: "success" });
      setSelectedEdgeId(null);
      void runValidation();
    } catch (err) {
      toast({ title: "Falha ao salvar conexão", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function handleEdgeDelete() {
    if (!token || !selectedEdge) return;
    try {
      await removeFlowEdge(token, selectedEdge.id);
      setFlowEdgesRaw((prev) => prev.filter((e) => e.id !== selectedEdge.id));
      setSelectedEdgeId(null);
      void runValidation();
    } catch (err) {
      toast({ title: "Falha ao remover conexão", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!token || readOnly || !connection.source || !connection.target) return;
      addFlowEdge(token, flowVersion.id, { source_node_id: connection.source, target_node_id: connection.target, edge_type: "success" })
        .then((created) => {
          setFlowEdgesRaw((prev) => [...prev, created]);
          void runValidation();
        })
        .catch((err) => toast({ title: "Falha ao conectar", description: err instanceof Error ? err.message : undefined, kind: "error" }));
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [token, readOnly, flowVersion.id],
  );

  const onNodeDragStop = useCallback(
    (_event: unknown, node: FlowCanvasNode) => {
      if (!token || readOnly) return;
      const fn = flowNodesRaw.find((n) => n.id === node.id);
      if (!fn) return;
      positionHistory.current.push({ nodeId: node.id, previous: { x: Number(fn.position_metadata?.x ?? 0), y: Number(fn.position_metadata?.y ?? 0) } });
      updateFlowNode(token, node.id, { position_metadata: { x: node.position.x, y: node.position.y } })
        .then((updated) => setFlowNodesRaw((prev) => prev.map((n) => (n.id === updated.id ? updated : n))))
        .catch(() => toast({ title: "Falha ao salvar posição", kind: "error" }));
    },
    [token, readOnly, flowNodesRaw, toast],
  );

  function undoLastMove() {
    const last = positionHistory.current.pop();
    if (!last || !token) return;
    updateFlowNode(token, last.nodeId, { position_metadata: last.previous })
      .then((updated) => setFlowNodesRaw((prev) => prev.map((n) => (n.id === updated.id ? updated : n))))
      .catch(() => toast({ title: "Falha ao desfazer", kind: "error" }));
  }

  async function autoLayout() {
    if (!token) return;
    const order = validation?.topological_order?.length ? validation.topological_order : flowNodesRaw.map((n) => n.id);
    const depth = new Map<string, number>();
    order.forEach((nodeId) => {
      const incoming = flowEdgesRaw.filter((e) => e.target_node_id === nodeId);
      const maxParentDepth = incoming.reduce((max, e) => Math.max(max, depth.get(e.source_node_id) ?? 0), -1);
      depth.set(nodeId, maxParentDepth + 1);
    });
    const columnCounts = new Map<number, number>();
    const updates: { id: string; x: number; y: number }[] = [];
    order.forEach((nodeId) => {
      const d = depth.get(nodeId) ?? 0;
      const column = columnCounts.get(d) ?? 0;
      columnCounts.set(d, column + 1);
      updates.push({ id: nodeId, x: d * 280 + 40, y: column * 160 + 40 });
    });
    try {
      await Promise.all(updates.map((u) => updateFlowNode(token, u.id, { position_metadata: { x: u.x, y: u.y } })));
      setFlowNodesRaw((prev) => prev.map((n) => {
        const u = updates.find((item) => item.id === n.id);
        return u ? { ...n, position_metadata: { x: u.x, y: u.y } } : n;
      }));
      toast({ title: "Layout organizado", kind: "success" });
    } catch (err) {
      toast({ title: "Falha ao organizar layout", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  const handleNodeClick: NodeMouseHandler<FlowCanvasNode> = useCallback((_event, node) => {
    setSelectedEdgeId(null);
    setSelectedNodeId(node.id);
  }, []);

  const handleEdgeClick: EdgeMouseHandler<FlowCanvasEdge> = useCallback((_event, edge) => {
    setSelectedNodeId(null);
    setSelectedEdgeId(edge.id);
  }, []);

  function focusNode(nodeId: string) {
    setSelectedEdgeId(null);
    setSelectedNodeId(nodeId);
  }

  function loadAutomationVersionsFor(automationId: number) {
    if (!token || loadedAutomationIds.current.has(automationId)) return;
    loadedAutomationIds.current.add(automationId);
    apiRequest<AutomationVersion[]>(`/automations/${automationId}/versions`, { token })
      .then((versions) => setAutomationVersions((prev) => [...prev.filter((v) => v.automation_id !== automationId), ...versions]))
      .catch(() => undefined);
  }

  const nameForNode = useMemo(() => {
    const map = new Map<string, string>();
    flowNodesRaw.forEach((n) => map.set(n.id, n.name || n.key));
    return map;
  }, [flowNodesRaw]);

  if (loading) {
    return (
      <div className="flex h-[520px] items-center justify-center rounded-lg border border-border bg-card">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <ReactFlowProvider>
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={readOnly ? "outline" : "primary"}>{readOnly ? "Somente leitura" : "Rascunho editável"}</Badge>
          {!readOnly && (
            <>
              <Button size="sm" variant="outline" onClick={() => handleAddNode("automation")}>
                <Plus className="h-3.5 w-3.5" /> Automação
              </Button>
              <Button size="sm" variant="outline" onClick={() => handleAddNode("condition")}>
                <Plus className="h-3.5 w-3.5" /> Condição
              </Button>
              <Button size="sm" variant="outline" onClick={() => handleAddNode("join")}>
                <Plus className="h-3.5 w-3.5" /> Join
              </Button>
              <Button size="sm" variant="outline" onClick={autoLayout}>
                <Wand2 className="h-3.5 w-3.5" /> Organizar
              </Button>
              <Button size="sm" variant="outline" onClick={undoLastMove} disabled={positionHistory.current.length === 0}>
                Desfazer posição
              </Button>
            </>
          )}
          <Button size="sm" variant="outline" onClick={runValidation} disabled={validating}>
            <ShieldCheck className="h-3.5 w-3.5" /> {validating ? "Validando..." : "Validar"}
          </Button>
          {!readOnly && (
            <Button
              size="sm"
              variant={validation && !validation.valid ? "outline" : "primary"}
              onClick={handlePublish}
              disabled={publishing || Boolean(validation && !validation.valid)}
              title={validation && !validation.valid ? "Corrija os problemas de validação listados acima antes de publicar" : undefined}
              className="ml-auto"
            >
              <Rocket className="h-3.5 w-3.5" /> {publishing ? "Publicando..." : "Publicar versão"}
            </Button>
          )}
          {!readOnly && <span className="text-xs text-muted-foreground">Alterações são salvas automaticamente.</span>}
        </div>

        {validation && <ValidationSummary issues={validation.issues} onFocusNode={focusNode} />}

        <div className="h-[600px] overflow-hidden rounded-lg border border-border bg-muted/20">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeDragStop={onNodeDragStop}
            onNodeClick={handleNodeClick}
            onEdgeClick={handleEdgeClick}
            onPaneClick={() => {
              setSelectedNodeId(null);
              setSelectedEdgeId(null);
            }}
            nodeTypes={flowNodeTypes}
            nodesDraggable={!readOnly}
            nodesConnectable={!readOnly}
            elementsSelectable
            fitView
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={20} />
            <Controls showInteractive={false} />
            <MiniMap pannable zoomable className="!bg-card" />
            <Panel position="top-right" className="rounded-md border border-border bg-card px-2 py-1 text-[11px] text-muted-foreground shadow-sm">
              {nodes.length} nó(s) · {edges.length} conexão(ões) · shift+arrastar para selecionar vários
            </Panel>
          </ReactFlow>
        </div>
      </div>

      <NodePanel
        node={selectedNode}
        upstreamNodes={upstreamNodesFor(selectedNodeId)}
        automations={automations.data ?? []}
        automationVersions={automationVersions}
        onLoadAutomationVersions={loadAutomationVersionsFor}
        readOnly={readOnly}
        onClose={() => setSelectedNodeId(null)}
        onSave={handleNodeSave}
        onDelete={handleNodeDelete}
        onDuplicate={handleNodeDuplicate}
      />

      <EdgePanel
        edge={selectedEdge}
        sourceName={selectedEdge ? nameForNode.get(selectedEdge.source) ?? selectedEdge.source : ""}
        targetName={selectedEdge ? nameForNode.get(selectedEdge.target) ?? selectedEdge.target : ""}
        upstreamNodes={edgeUpstreamNodesFor(selectedEdge?.source ?? null)}
        readOnly={readOnly}
        onClose={() => setSelectedEdgeId(null)}
        onSave={handleEdgeSave}
        onDelete={handleEdgeDelete}
      />
    </ReactFlowProvider>
  );
}
