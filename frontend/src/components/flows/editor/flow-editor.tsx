"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  Panel,
  MarkerType,
  SelectionMode,
  useNodesState,
  useEdgesState,
  type Connection,
  type NodeMouseHandler,
  type EdgeMouseHandler,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { ArrowRight, Hand, Loader2, MousePointer2, Pencil, Plus, Rocket, ShieldCheck, Trash2, Wand2, Workflow } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Field, Input, Label, Textarea } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Sheet } from "@/components/ui/sheet";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { useApi } from "@/hooks/use-api";
import { flowNodeTypes } from "@/components/flows/editor/nodes";
import { NodePanel, type NodeConfigPatch } from "@/components/flows/editor/node-panel";
import { EdgePanel } from "@/components/flows/editor/edge-panel";
import { ValidationSummary } from "@/components/flows/editor/validation-panel";
import { CONDITION_BLOCKS, conditionBlockFor } from "@/components/flows/editor/block-catalog";
import { deriveEdgeSpecForConnection, edgeBranchLabelFor, ifElseHandleForEdge, switchHandleForEdge } from "@/components/flows/editor/branch-logic";
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
  updateFlowVersionDraft,
  updateFlowNode,
  validateFlowVersion,
} from "@/lib/flow-api";
import { apiRequest } from "@/lib/api";
import type { Automation } from "@/types/automation";
import type { AutomationVersionResponse as AutomationVersion } from "@/types/catalog";
import type { FlowEdge, FlowNode, FlowNodeType, FlowValidationIssue, FlowValidationResult, FlowVersion } from "@/types/flow";

const EDGE_COLOR: Record<string, string> = {
  success: "hsl(var(--success))",
  failure: "hsl(var(--destructive))",
  always: "hsl(var(--muted-foreground))",
  conditional: "hsl(var(--info))",
};

const FLOW_BLOCK_MIME = "application/x-portal-flow-block";

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

function toRFEdge(fe: FlowEdge, issues: FlowValidationIssue[], readOnly: boolean, sourceNode: FlowNode | undefined): FlowCanvasEdge {
  const edgeIssues = issuesForEdge(fe.id, issues);
  const hasIssues = edgeIssues.length > 0;
  const color = hasIssues ? "hsl(var(--destructive))" : EDGE_COLOR[fe.edge_type] ?? EDGE_COLOR.success;
  // If/Else e Switch guardam qual saída cada aresta representa na própria condição gravada
  // nela (ver branch-logic.ts) — reconstruímos o handle e o rótulo a partir disso, em vez de
  // depender de um campo extra no backend.
  let sourceHandle: string | undefined;
  if (sourceNode) {
    if (sourceNode.node_type === "if_else") sourceHandle = ifElseHandleForEdge(sourceNode, fe);
    else if (sourceNode.node_type === "switch") sourceHandle = switchHandleForEdge(sourceNode, fe);
  }
  const branchLabel = sourceHandle ? edgeBranchLabelFor(sourceNode, sourceHandle) : undefined;
  return {
    id: fe.id,
    source: fe.source_node_id,
    target: fe.target_node_id,
    sourceHandle,
    deletable: false,
    label: hasIssues ? "problema" : (branchLabel ?? (fe.edge_type !== "success" ? fe.edge_type : undefined)),
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

function isTextEditingTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

function EmptyFlowCanvas({
  readOnly,
  onAddNode,
}: {
  readOnly: boolean;
  onAddNode: (nodeType: FlowNodeType) => void;
}) {
  if (readOnly) {
    return (
      <div className="flex min-h-[520px] items-center justify-center rounded-lg border border-dashed border-border bg-muted/20 px-6 text-center">
        <div className="max-w-sm">
          <Workflow className="mx-auto h-8 w-8 text-muted-foreground" />
          <p className="mt-4 text-sm font-semibold">Esta versão não possui componentes</p>
          <p className="mt-1 text-sm text-muted-foreground">Crie um novo rascunho para montar uma nova versão do fluxo.</p>
        </div>
      </div>
    );
  }

  const ifElseBlock = conditionBlockFor("if_else")!;
  const joinBlock = conditionBlockFor("join")!;
  const choices = [
    {
      type: "automation" as const,
      icon: Workflow,
      title: "Começar com uma automação",
      description: "Escolha uma versão publicada para executar a primeira etapa.",
      accent: "text-primary",
    },
    {
      type: "if_else" as const,
      icon: ifElseBlock.style.icon,
      title: "Adicionar um If / Else",
      description: ifElseBlock.description,
      accent: ifElseBlock.style.accent,
    },
    {
      type: "join" as const,
      icon: joinBlock.style.icon,
      title: "Unir caminhos",
      description: joinBlock.description,
      accent: joinBlock.style.accent,
    },
  ];

  return (
    <div className="min-h-[520px] rounded-lg border border-dashed border-border bg-muted/20 p-5 sm:p-8">
      <div className="mx-auto flex max-w-3xl flex-col items-center text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-primary/30 bg-primary/10 text-primary">
          <Workflow className="h-6 w-6" />
        </div>
        <h2 className="mt-4 text-lg font-semibold">Monte a primeira etapa</h2>
        <p className="mt-1 max-w-xl text-sm text-muted-foreground">Todo fluxo começa escolhendo o que roda primeiro. Depois, conecte as próximas etapas arrastando do conector inferior de um nó para o superior do próximo.</p>
      </div>

      <div className="mx-auto mt-7 grid max-w-3xl gap-3 md:grid-cols-3">
        {choices.map((choice) => {
          const Icon = choice.icon;
          return (
            <button
              key={choice.type}
              type="button"
              onClick={() => onAddNode(choice.type)}
              className="group min-h-[178px] rounded-lg border border-border bg-card p-4 text-left transition-colors hover:border-primary/50 hover:bg-primary/5 focus:outline-none focus:ring-2 focus:ring-primary/40"
            >
              <Icon className={`h-5 w-5 ${choice.accent}`} />
              <p className="mt-4 text-sm font-semibold">{choice.title}</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">{choice.description}</p>
              <span className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-primary">
                <Plus className="h-3.5 w-3.5" /> Adicionar
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function FlowEditor({
  flowVersion,
  onVersionChange,
  suggestedPublishVersion,
  onCreateEditableDraft,
}: {
  flowVersion: FlowVersion;
  onVersionChange: (version: FlowVersion) => void;
  suggestedPublishVersion: string;
  onCreateEditableDraft?: () => void;
}) {
  const { token } = useAuth();
  const { toast } = useToast();
  const readOnly = flowVersion.status !== "draft";

  const [flowNodesRaw, setFlowNodesRaw] = useState<FlowNode[]>([]);
  const [flowEdgesRaw, setFlowEdgesRaw] = useState<FlowEdge[]>([]);
  const [loading, setLoading] = useState(true);
  const [validation, setValidation] = useState<FlowValidationResult | null>(null);
  const [validationStale, setValidationStale] = useState(false);
  const [validating, setValidating] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [publishDialogOpen, setPublishDialogOpen] = useState(false);
  const [publishVersion, setPublishVersion] = useState(suggestedPublishVersion);
  const [releaseNotes, setReleaseNotes] = useState(flowVersion.release_notes ?? "");

  const [nodes, setNodes, onNodesChange] = useNodesState<FlowCanvasNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowCanvasEdge>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [interactionMode, setInteractionMode] = useState<"select" | "pan">("select");
  const [blockCatalogOpen, setBlockCatalogOpen] = useState(false);
  const [blockCatalogTab, setBlockCatalogTab] = useState<"automations" | "conditions">("automations");
  const [blockCatalogQuery, setBlockCatalogQuery] = useState("");
  const [automationPickerOpen, setAutomationPickerOpen] = useState(false);
  const [automationPickerTarget, setAutomationPickerTarget] = useState<string | null>(null);
  const [automationQuery, setAutomationQuery] = useState("");
  const [selectingAutomationId, setSelectingAutomationId] = useState<number | null>(null);
  const [availableAutomationVersions, setAvailableAutomationVersions] = useState<Record<number, AutomationVersion | null>>({});
  const [loadingAvailableAutomations, setLoadingAvailableAutomations] = useState(false);

  const automations = useApi<Automation[]>("/automations");
  const [automationVersions, setAutomationVersions] = useState<AutomationVersion[]>([]);
  const positionHistory = useRef<{ nodeId: string; previous: { x: number; y: number } }[]>([]);
  const interactionBeforeSpace = useRef<"select" | "pan">("select");
  const spacePanActive = useRef(false);
  const reactFlowInstance = useRef<ReactFlowInstance<FlowCanvasNode, FlowCanvasEdge> | null>(null);

  // Um rascunho vazio é um ponto de partida válido para edição. A validação formal
  // acontece por ação explícita ou no momento de publicar.
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
      setValidation(null);
      setValidationStale(false);
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

  useEffect(() => {
    setPublishVersion(suggestedPublishVersion);
    setReleaseNotes(flowVersion.release_notes ?? "");
  }, [flowVersion.id, flowVersion.release_notes, suggestedPublishVersion]);

  useEffect(() => {
    if (!(automationPickerOpen || (blockCatalogOpen && blockCatalogTab === "automations")) || !token || !automations.data) return;
    let cancelled = false;
    setLoadingAvailableAutomations(true);
    Promise.all(
      automations.data
        .filter((automation) => automation.is_active)
        .map(async (automation) => {
          try {
            const versions = await apiRequest<AutomationVersion[]>(`/automations/${automation.id}/versions`, { token });
            const published = versions
              .filter((version) => version.status === "published")
              .sort((a, b) => (b.published_at ?? b.created_at).localeCompare(a.published_at ?? a.created_at))[0] ?? null;
            return [automation.id, published] as const;
          } catch {
            return [automation.id, null] as const;
          }
        }),
    ).then((entries) => {
      if (!cancelled) setAvailableAutomationVersions(Object.fromEntries(entries));
    }).finally(() => {
      if (!cancelled) setLoadingAvailableAutomations(false);
    });
    return () => {
      cancelled = true;
    };
  }, [automationPickerOpen, automations.data, blockCatalogOpen, blockCatalogTab, token]);

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
    const nodesById = new Map(flowNodesRaw.map((fn) => [fn.id, fn]));
    setNodes(flowNodesRaw.map((fn) => toRFNode(fn, validation?.issues ?? [], readOnly, automationLabelFor(fn.automation_version_id))));
    setEdges(flowEdgesRaw.map((fe) => toRFEdge(fe, validation?.issues ?? [], readOnly, nodesById.get(fe.source_node_id))));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flowNodesRaw, flowEdgesRaw, validation, readOnly, automationVersions, automations.data]);

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) ?? null;
  const selectedEdge = edges.find((e) => e.id === selectedEdgeId) ?? null;
  const selectedNodeIds = useMemo(() => nodes.filter((node) => node.selected).map((node) => node.id), [nodes]);
  const selectedEdgeIds = useMemo(() => edges.filter((edge) => edge.selected).map((edge) => edge.id), [edges]);

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
      setValidationStale(false);
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
      await updateFlowVersionDraft(token, flowVersion.id, {
        version: publishVersion.trim(),
        release_notes: releaseNotes.trim() || null,
      });
      const fresh = await validateFlowVersion(token, flowVersion.id);
      setValidation(fresh);
      setValidationStale(false);
      if (!fresh.valid) {
        toast({ title: "Corrija os problemas antes de publicar", kind: "error" });
        return;
      }
      const updated = await publishFlowVersion(token, flowVersion.id);
      setPublishDialogOpen(false);
      toast({ title: `Fluxo publicado como v${updated.version}`, kind: "success" });
      onVersionChange(updated);
    } catch (err) {
      toast({ title: "Falha ao publicar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setPublishing(false);
    }
  }

  function openAutomationPicker(nodeId?: string) {
    if (readOnly) return;
    setAutomationPickerTarget(nodeId ?? null);
    setAutomationQuery("");
    setAutomationPickerOpen(true);
  }

  async function handleAddNode(nodeType: FlowNodeType, position?: { x: number; y: number }) {
    if (!token) return;
    if (nodeType === "automation") {
      openAutomationPicker();
      return;
    }
    const block = conditionBlockFor(nodeType);
    const key = generateNodeKey(nodeType);
    const nodePosition = position ?? { x: 120 + Math.random() * 80, y: 80 + flowNodesRaw.length * 40 };
    try {
      const created = await addFlowNode(token, flowVersion.id, {
        key,
        name: block?.name ?? nodeType,
        node_type: nodeType,
        position_metadata: nodePosition,
      });
      setFlowNodesRaw((prev) => [...prev, created]);
      setSelectedNodeId(created.id);
      setValidation(null);
      setValidationStale(true);
    } catch (err) {
      toast({ title: "Falha ao adicionar nó", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function handleAutomationPicked(automation: Automation, position?: { x: number; y: number }) {
    if (!token) return;
    setSelectingAutomationId(automation.id);
    try {
      const versions = await apiRequest<AutomationVersion[]>(`/automations/${automation.id}/versions`, { token });
      const published = availableAutomationVersions[automation.id] ?? versions
        .filter((version) => version.status === "published")
        .sort((a, b) => (b.published_at ?? b.created_at).localeCompare(a.published_at ?? a.created_at))[0];
      if (!published) {
        toast({ title: "Esta automação ainda não está pronta para uso", description: "Publique uma versão dela em Automações antes de adicioná-la ao fluxo.", kind: "warning" });
        return;
      }

      setAutomationVersions((previous) => [...previous.filter((version) => version.automation_id !== automation.id), ...versions]);
      if (automationPickerTarget) {
        const updated = await updateFlowNode(token, automationPickerTarget, {
          name: automation.name,
          automation_version_id: published.id,
        });
        setFlowNodesRaw((previous) => previous.map((node) => (node.id === updated.id ? updated : node)));
        setSelectedNodeId(updated.id);
      } else {
        const created = await addFlowNode(token, flowVersion.id, {
          key: generateNodeKey("automation"),
          name: automation.name,
          node_type: "automation",
          automation_version_id: published.id,
          position_metadata: position ?? { x: 120 + Math.random() * 80, y: 80 + flowNodesRaw.length * 40 },
        });
        setFlowNodesRaw((previous) => [...previous, created]);
        setSelectedNodeId(created.id);
      }
      setValidation(null);
      setValidationStale(true);
      setAutomationPickerOpen(false);
      setBlockCatalogOpen(false);
      toast({ title: "Automação adicionada", description: `${automation.name} foi incluída como etapa do fluxo.`, kind: "success" });
    } catch (err) {
      toast({ title: "Não foi possível adicionar a automação", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSelectingAutomationId(null);
    }
  }

  const catalogAutomations = useMemo(() => {
    const query = blockCatalogQuery.trim().toLowerCase();
    return (automations.data ?? []).filter((automation) => {
      const text = `${automation.name} ${automation.key ?? ""} ${automation.description ?? ""}`.toLowerCase();
      return !query || text.includes(query);
    });
  }, [automations.data, blockCatalogQuery]);

  const catalogConditionBlocks = useMemo(() => {
    const query = blockCatalogQuery.trim().toLowerCase();
    return CONDITION_BLOCKS.filter((block) => !query || `${block.name} ${block.description}`.toLowerCase().includes(query));
  }, [blockCatalogQuery]);

  function openBlockCatalog() {
    setBlockCatalogTab("automations");
    setBlockCatalogQuery("");
    setBlockCatalogOpen(true);
  }

  function startCatalogDrag(event: DragEvent<HTMLElement>, payload: { kind: "automation"; automationId: number } | { kind: "logic"; nodeType: FlowNodeType }) {
    event.dataTransfer.setData(FLOW_BLOCK_MIME, JSON.stringify(payload));
    event.dataTransfer.effectAllowed = "move";
  }

  function handleCanvasDragOver(event: DragEvent<HTMLDivElement>) {
    if (readOnly || !event.dataTransfer.types.includes(FLOW_BLOCK_MIME)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }

  function handleCanvasDrop(event: DragEvent<HTMLDivElement>) {
    if (readOnly) return;
    const rawPayload = event.dataTransfer.getData(FLOW_BLOCK_MIME);
    if (!rawPayload) return;
    event.preventDefault();
    try {
      const payload = JSON.parse(rawPayload) as { kind: "automation"; automationId: number } | { kind: "logic"; nodeType: FlowNodeType };
      const position = reactFlowInstance.current?.screenToFlowPosition({ x: event.clientX, y: event.clientY });
      if (!position) return;
      if (payload.kind === "automation") {
        const automation = (automations.data ?? []).find((item) => item.id === payload.automationId);
        if (automation) void handleAutomationPicked(automation, position);
        return;
      }
      void handleAddNode(payload.nodeType, position);
    } catch {
      toast({ title: "Bloco inválido", kind: "error" });
    }
  }

  async function handleNodeSave(patch: NodeConfigPatch) {
    if (!token || !selectedNode) return;
    try {
      const updated = await updateFlowNode(token, selectedNode.id, patch);
      setFlowNodesRaw((prev) => prev.map((n) => (n.id === updated.id ? updated : n)));
      toast({ title: "Nó atualizado", kind: "success" });
      setSelectedNodeId(null);
      setValidation(null);
      setValidationStale(true);
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
      setValidation(null);
      setValidationStale(true);
    } catch (err) {
      toast({ title: "Falha ao remover nó", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  const clearCanvasSelection = useCallback(() => {
    setNodes((current) => current.map((node) => ({ ...node, selected: false })));
    setEdges((current) => current.map((edge) => ({ ...edge, selected: false })));
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
  }, [setEdges, setNodes]);

  const handleDeleteSelection = useCallback(async () => {
    if (!token || readOnly) return;
    const nodeIds = nodes.filter((node) => node.selected).map((node) => node.id);
    const edgeIds = edges
      .filter((edge) => edge.selected && !nodeIds.includes(edge.source) && !nodeIds.includes(edge.target))
      .map((edge) => edge.id);
    if (nodeIds.length + edgeIds.length === 0) return;
    if (nodeIds.length + edgeIds.length > 1 && !window.confirm(`Remover ${nodeIds.length} etapa(s) e ${edgeIds.length} conexão(ões)?`)) return;

    try {
      await Promise.all([
        ...nodeIds.map((nodeId) => removeFlowNode(token, nodeId)),
        ...edgeIds.map((edgeId) => removeFlowEdge(token, edgeId)),
      ]);
      const removedNodes = new Set(nodeIds);
      const removedEdges = new Set(edgeIds);
      setFlowNodesRaw((current) => current.filter((node) => !removedNodes.has(node.id)));
      setFlowEdgesRaw((current) => current.filter((edge) => !removedEdges.has(edge.id) && !removedNodes.has(edge.source_node_id) && !removedNodes.has(edge.target_node_id)));
      clearCanvasSelection();
      setValidation(null);
      setValidationStale(true);
      toast({ title: nodeIds.length + edgeIds.length === 1 ? "Item removido" : "Itens removidos", kind: "success" });
    } catch (err) {
      toast({ title: "Falha ao remover itens selecionados", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }, [clearCanvasSelection, edges, nodes, readOnly, token, toast]);

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
      setValidation(null);
      setValidationStale(true);
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
      setValidation(null);
      setValidationStale(true);
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
      setValidation(null);
      setValidationStale(true);
    } catch (err) {
      toast({ title: "Falha ao remover conexão", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!token || readOnly || !connection.source || !connection.target) return;
      // Se a conexão sai de um handle nomeado (Verdadeiro/Falso de um If/Else, ou um caso do
      // Switch), a aresta já nasce com o edge_type/condition corretos — ver branch-logic.ts.
      const sourceNode = flowNodesRaw.find((n) => n.id === connection.source);
      const { edgeType, condition } = deriveEdgeSpecForConnection(sourceNode, connection.sourceHandle ?? null);
      addFlowEdge(token, flowVersion.id, { source_node_id: connection.source, target_node_id: connection.target, edge_type: edgeType, condition })
        .then((created) => {
          setFlowEdgesRaw((prev) => [...prev, created]);
          setValidation(null);
          setValidationStale(true);
        })
        .catch((err) => toast({ title: "Falha ao conectar", description: err instanceof Error ? err.message : undefined, kind: "error" }));
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [token, readOnly, flowVersion.id, flowNodesRaw],
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

  const persistDraggedNodes = useCallback(
    (_event: unknown, node: FlowCanvasNode) => {
      if (!token || readOnly) return;
      const movedIds = new Set(nodes.filter((item) => item.selected).map((item) => item.id));
      movedIds.add(node.id);
      const moved = nodes.filter((item) => movedIds.has(item.id));
      const previousById = new Map(flowNodesRaw.map((item) => [item.id, item]));
      moved.forEach((item) => {
        const previous = previousById.get(item.id);
        if (previous) {
          positionHistory.current.push({ nodeId: item.id, previous: { x: Number(previous.position_metadata?.x ?? 0), y: Number(previous.position_metadata?.y ?? 0) } });
        }
      });
      Promise.all(moved.map((item) => updateFlowNode(token, item.id, { position_metadata: { x: item.position.x, y: item.position.y } })))
        .then((updatedNodes) => {
          const updatedById = new Map(updatedNodes.map((item) => [item.id, item]));
          setFlowNodesRaw((current) => current.map((item) => updatedById.get(item.id) ?? item));
        })
        .catch(() => toast({ title: "Falha ao salvar posições", kind: "error" }));
    },
    [flowNodesRaw, nodes, readOnly, token, toast],
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

  const handleNodeClick: NodeMouseHandler<FlowCanvasNode> = useCallback((event, node) => {
    if (event.ctrlKey || event.metaKey || event.shiftKey) {
      setSelectedNodeId(null);
      setSelectedEdgeId(null);
      return;
    }
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

  useEffect(() => {
    if (readOnly) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (isTextEditingTarget(event.target)) return;
      if (blockCatalogOpen || publishDialogOpen || automationPickerOpen) return;
      if (event.code === "Space") {
        event.preventDefault();
        if (!spacePanActive.current) {
          interactionBeforeSpace.current = interactionMode;
          spacePanActive.current = true;
          setInteractionMode("pan");
        }
        return;
      }
      if (event.key.toLowerCase() === "v") {
        event.preventDefault();
        setInteractionMode("select");
        return;
      }
      if (event.key.toLowerCase() === "h") {
        event.preventDefault();
        setInteractionMode("pan");
        return;
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "a") {
        event.preventDefault();
        setNodes((current) => current.map((node) => ({ ...node, selected: true })));
        setSelectedNodeId(null);
        setSelectedEdgeId(null);
        return;
      }
      if (event.key === "Escape") {
        clearCanvasSelection();
        return;
      }
      if ((event.key === "Delete" || event.key === "Backspace") && !selectedNodeId && !selectedEdgeId) {
        event.preventDefault();
        void handleDeleteSelection();
      }
    };
    const onKeyUp = (event: KeyboardEvent) => {
      if (event.code !== "Space" || !spacePanActive.current) return;
      spacePanActive.current = false;
      setInteractionMode(interactionBeforeSpace.current);
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, [automationPickerOpen, blockCatalogOpen, clearCanvasSelection, handleDeleteSelection, interactionMode, publishDialogOpen, readOnly, selectedEdgeId, selectedNodeId, setNodes]);

  const nameForNode = useMemo(() => {
    const map = new Map<string, string>();
    flowNodesRaw.forEach((n) => map.set(n.id, n.name || n.key));
    return map;
  }, [flowNodesRaw]);
  const hasUnconfiguredAutomation = flowNodesRaw.some((node) => node.node_type === "automation" && !node.automation_version_id);
  const publishBlockedReason =
    flowNodesRaw.length === 0
      ? "Adicione ao menos uma etapa antes de publicar"
      : hasUnconfiguredAutomation
        ? "Escolha uma versão publicada para cada automação antes de publicar"
        : validation && !validation.valid
          ? "Corrija os problemas de validação antes de publicar"
          : undefined;

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
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card p-2.5">
          <Badge tone={readOnly ? "outline" : "primary"}>{readOnly ? "Versão publicada" : "Rascunho editável"}</Badge>
          {!readOnly && (
            <>
              <Button size="sm" variant="primary" onClick={openBlockCatalog}>
                <Plus className="h-3.5 w-3.5" /> Adicionar bloco
              </Button>
              <span className="hidden h-5 w-px bg-border md:block" />
              <div className="flex items-center rounded-md border border-border bg-muted/30 p-0.5" role="group" aria-label="Modo de interação do canvas">
                <Button size="sm" variant={interactionMode === "select" ? "subtle" : "ghost"} className="h-7 px-2" onClick={() => setInteractionMode("select")} title="Selecionar e mover etapas (V)">
                  <MousePointer2 className="h-3.5 w-3.5" /> Selecionar
                </Button>
                <Button size="sm" variant={interactionMode === "pan" ? "subtle" : "ghost"} className="h-7 px-2" onClick={() => setInteractionMode("pan")} title="Mover o canvas (H ou Espaço)">
                  <Hand className="h-3.5 w-3.5" /> Mover
                </Button>
              </div>
              <Button size="sm" variant="outline" onClick={autoLayout}>
                <Wand2 className="h-3.5 w-3.5" /> Organizar
              </Button>
              <Button size="icon" variant="ghost" title="Desfazer última posição" onClick={undoLastMove} disabled={positionHistory.current.length === 0}>
                <ArrowRight className="h-4 w-4 rotate-180" />
              </Button>
              {(selectedNodeIds.length > 0 || selectedEdgeIds.length > 0) && (
                <Button size="sm" variant="outline" className="border-destructive/40 text-destructive hover:bg-destructive/10" onClick={() => void handleDeleteSelection()}>
                  <Trash2 className="h-3.5 w-3.5" /> Remover {selectedNodeIds.length + selectedEdgeIds.length}
                </Button>
              )}
            </>
          )}
          <Button size="sm" variant="outline" onClick={runValidation} disabled={validating}>
            <ShieldCheck className="h-3.5 w-3.5" /> {validating ? "Validando..." : "Validar"}
          </Button>
          {!readOnly && (
            <Button
              size="sm"
              variant={validation && !validation.valid ? "outline" : "primary"}
              onClick={() => setPublishDialogOpen(true)}
              disabled={publishing || Boolean(publishBlockedReason)}
              title={publishBlockedReason}
              className="ml-auto"
            >
              <Rocket className="h-3.5 w-3.5" /> Publicar fluxo
            </Button>
          )}
          {readOnly && onCreateEditableDraft && (
            <Button size="sm" variant="primary" onClick={onCreateEditableDraft}>
              <Pencil className="h-3.5 w-3.5" /> Editar fluxo
            </Button>
          )}
          {!readOnly && <span className="ml-auto text-xs text-muted-foreground">{nodes.length === 0 ? "Escolha a primeira etapa para começar" : validationStale ? "Alterações pendentes de validação" : "Alterações salvas automaticamente"}</span>}
        </div>

        {validation && <ValidationSummary issues={validation.issues} onFocusNode={focusNode} />}

        {nodes.length === 0 ? (
          <EmptyFlowCanvas readOnly={readOnly} onAddNode={handleAddNode} />
        ) : (
          <div className="h-[620px] overflow-hidden rounded-lg border border-border bg-muted/20" onDragOver={handleCanvasDragOver} onDrop={handleCanvasDrop}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onInit={(instance) => {
                reactFlowInstance.current = instance;
              }}
              onNodeDragStop={persistDraggedNodes}
              onNodeClick={handleNodeClick}
              onEdgeClick={handleEdgeClick}
              onPaneClick={clearCanvasSelection}
              nodeTypes={flowNodeTypes}
              nodesDraggable={!readOnly && interactionMode === "select"}
              nodesConnectable={!readOnly && interactionMode === "select"}
              elementsSelectable
              selectionOnDrag={!readOnly && interactionMode === "select"}
              selectionMode={SelectionMode.Partial}
              multiSelectionKeyCode={["Control", "Meta"]}
              panOnDrag={interactionMode === "pan"}
              panOnScroll={interactionMode === "pan"}
              deleteKeyCode={null}
              fitView
              proOptions={{ hideAttribution: true }}
            >
              <Background gap={20} />
              <Controls showInteractive={false} />
              <MiniMap pannable zoomable className="!bg-card" />
              <Panel position="top-right" className="rounded-md border border-border bg-card px-2 py-1 text-[11px] text-muted-foreground shadow-sm">
                {nodes.length} nó(s) · {edges.length} conexão(ões) · arraste entre conectores para ligar
              </Panel>
            </ReactFlow>
          </div>
        )}
      </div>

      <NodePanel
        node={selectedNode}
        upstreamNodes={upstreamNodesFor(selectedNodeId)}
        readOnly={readOnly}
        onClose={() => setSelectedNodeId(null)}
        onChangeAutomation={() => selectedNode && openAutomationPicker(selectedNode.id)}
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

      <Sheet
        open={blockCatalogOpen}
        onClose={() => setBlockCatalogOpen(false)}
        title="Blocos do fluxo"
        description="Clique para adicionar ou arraste um bloco para a posição desejada no canvas."
        widthClassName="w-full sm:max-w-md"
        footer={<Button variant="outline" onClick={() => setBlockCatalogOpen(false)}>Fechar</Button>}
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 rounded-md border border-border bg-muted/30 p-1" role="tablist" aria-label="Categorias de blocos">
            <button
              type="button"
              role="tab"
              aria-selected={blockCatalogTab === "automations"}
              onClick={() => setBlockCatalogTab("automations")}
              className={`h-8 rounded-sm px-3 text-xs font-medium transition-colors ${blockCatalogTab === "automations" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
            >
              Automações
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={blockCatalogTab === "conditions"}
              onClick={() => setBlockCatalogTab("conditions")}
              className={`h-8 rounded-sm px-3 text-xs font-medium transition-colors ${blockCatalogTab === "conditions" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
            >
              Condições
            </button>
          </div>

          <Input
            aria-label="Buscar bloco"
            placeholder={blockCatalogTab === "automations" ? "Buscar automação..." : "Buscar condição ou controle..."}
            value={blockCatalogQuery}
            onChange={(event) => setBlockCatalogQuery(event.target.value)}
          />

          {blockCatalogTab === "automations" ? (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Automações registradas</p>
              {automations.loading || loadingAvailableAutomations ? (
                <div className="flex h-32 items-center justify-center"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
              ) : catalogAutomations.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">Nenhuma automação encontrada.</div>
              ) : (
                <div className="space-y-2">
                  {catalogAutomations.map((automation) => {
                    const published = availableAutomationVersions[automation.id];
                    const available = automation.is_active && Boolean(published);
                    return (
                      <button
                        key={automation.id}
                        type="button"
                        disabled={!available || selectingAutomationId !== null}
                        draggable={available}
                        onDragStart={(event) => startCatalogDrag(event, { kind: "automation", automationId: automation.id })}
                        onClick={() => available && void handleAutomationPicked(automation)}
                        className="w-full rounded-lg border border-border bg-card p-3 text-left transition-colors hover:border-primary/50 hover:bg-primary/5 disabled:cursor-not-allowed disabled:opacity-55"
                      >
                        <div className="flex items-start gap-3">
                          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary"><Workflow className="h-4 w-4" /></span>
                          <span className="min-w-0 flex-1">
                            <span className="flex items-center justify-between gap-2"><span className="truncate text-sm font-semibold">{automation.name}</span><Badge tone={available ? "success" : "outline"}>{available ? `v${published?.version}` : "Indisponível"}</Badge></span>
                            <span className="mt-1 block line-clamp-2 text-xs leading-5 text-muted-foreground">{available ? automation.description || automation.key || "Pronta para usar no fluxo." : automation.is_active ? "Publique uma versão para adicioná-la ao fluxo." : "Automação inativa."}</span>
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Condições e controle de fluxo</p>
              {catalogConditionBlocks.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">Nenhum bloco encontrado.</div>
              ) : (
                <div className="space-y-2">
                  {catalogConditionBlocks.map((block) => {
                    const Icon = block.style.icon;
                    const available = Boolean(block.nodeType);
                    return (
                      <button
                        key={block.id}
                        type="button"
                        disabled={!available}
                        draggable={available}
                        onDragStart={(event) => block.nodeType && startCatalogDrag(event, { kind: "logic", nodeType: block.nodeType })}
                        onClick={() => {
                          if (!block.nodeType) return;
                          setBlockCatalogOpen(false);
                          void handleAddNode(block.nodeType);
                        }}
                        title={!available ? block.unavailableReason : undefined}
                        className="w-full rounded-lg border border-border bg-card p-3 text-left transition-colors hover:border-primary/50 hover:bg-primary/5 disabled:cursor-not-allowed disabled:opacity-55"
                      >
                        <div className="flex items-start gap-3">
                          <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md ${block.style.bg} ${block.style.accent}`}>
                            <Icon className="h-4 w-4" />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="flex items-center justify-between gap-2">
                              <span className="text-sm font-semibold">{block.name}</span>
                              <Badge tone={available ? "success" : "outline"}>{available ? "Disponível" : "Em preparo"}</Badge>
                            </span>
                            <span className="mt-1 block text-xs leading-5 text-muted-foreground">{block.description}</span>
                            {!available && block.unavailableReason && (
                              <span className="mt-1 block text-[11px] leading-4 text-muted-foreground/80">{block.unavailableReason}</span>
                            )}
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </Sheet>

      <Modal
        open={publishDialogOpen}
        onClose={() => !publishing && setPublishDialogOpen(false)}
        title="Publicar fluxo"
        description="Revise a identificação desta publicação. O editor continuará disponível para novas alterações depois."
        className="max-w-xl"
        footer={
          <>
            <Button variant="outline" onClick={() => setPublishDialogOpen(false)} disabled={publishing}>
              Voltar
            </Button>
            <Button onClick={handlePublish} disabled={publishing || !publishVersion.trim()}>
              <Rocket className="h-4 w-4" /> {publishing ? "Publicando..." : "Publicar fluxo"}
            </Button>
          </>
        }
      >
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3 rounded-lg border border-border bg-muted/20 p-3 text-center">
            <div>
              <p className="text-lg font-semibold tabular">{nodes.length}</p>
              <p className="text-xs text-muted-foreground">etapas</p>
            </div>
            <div>
              <p className="text-lg font-semibold tabular">{edges.length}</p>
              <p className="text-xs text-muted-foreground">conexões</p>
            </div>
          </div>
          <Field>
            <Label htmlFor="flow-publish-version">Versão da publicação</Label>
            <Input
              id="flow-publish-version"
              value={publishVersion}
              placeholder="Ex.: 1.0.0"
              onChange={(event) => setPublishVersion(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">Use o formato principal.secundária.correção, por exemplo 1.0.0.</p>
          </Field>
          <Field>
            <Label htmlFor="flow-release-notes">O que mudou nesta publicação</Label>
            <Textarea
              id="flow-release-notes"
              rows={3}
              value={releaseNotes}
              placeholder="Ex.: Incluída conferência antes do envio ao financeiro."
              onChange={(event) => setReleaseNotes(event.target.value)}
            />
          </Field>
        </div>
      </Modal>

      <Modal
        open={automationPickerOpen}
        onClose={() => !selectingAutomationId && setAutomationPickerOpen(false)}
        title={automationPickerTarget ? "Trocar automação" : "Adicionar automação"}
        description="Escolha a automação que deve executar esta etapa. O fluxo usa automaticamente a versão publicada mais recente."
        className="max-w-2xl"
        footer={
          <Button variant="outline" onClick={() => setAutomationPickerOpen(false)} disabled={Boolean(selectingAutomationId)}>
            Cancelar
          </Button>
        }
      >
        <div className="space-y-4">
          <Input placeholder="Buscar automação..." value={automationQuery} onChange={(event) => setAutomationQuery(event.target.value)} />
          {automations.loading || loadingAvailableAutomations ? (
            <div className="flex h-36 items-center justify-center"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
          ) : (automations.data ?? []).filter((automation) => automation.is_active && availableAutomationVersions[automation.id] && `${automation.name} ${automation.key ?? ""}`.toLowerCase().includes(automationQuery.trim().toLowerCase())).length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-6 text-center">
              <p className="text-sm font-semibold">Nenhuma automação disponível</p>
              <p className="mt-1 text-sm text-muted-foreground">Cadastre e publique uma automação antes de adicioná-la a um fluxo.</p>
            </div>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2">
              {(automations.data ?? [])
                .filter((automation) => automation.is_active && availableAutomationVersions[automation.id] && `${automation.name} ${automation.key ?? ""}`.toLowerCase().includes(automationQuery.trim().toLowerCase()))
                .map((automation) => (
                  <button
                    key={automation.id}
                    type="button"
                    onClick={() => handleAutomationPicked(automation)}
                    disabled={selectingAutomationId !== null}
                    className="rounded-lg border border-border bg-card p-4 text-left transition-colors hover:border-primary/50 hover:bg-primary/5 disabled:cursor-wait disabled:opacity-60"
                  >
                    <Workflow className="h-5 w-5 text-primary" />
                    <p className="mt-3 text-sm font-semibold">{automation.name}</p>
                    <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{automation.description || automation.key || "Automação pronta para adicionar ao fluxo."}</p>
                    {selectingAutomationId === automation.id && <Loader2 className="mt-3 h-4 w-4 animate-spin text-primary" />}
                  </button>
                ))}
            </div>
          )}
        </div>
      </Modal>
    </ReactFlowProvider>
  );
}
