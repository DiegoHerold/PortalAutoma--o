"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
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
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Ban, RotateCw, Wifi, WifiOff } from "lucide-react";

import { Breadcrumbs } from "@/components/shared/breadcrumbs";
import { PageTitle } from "@/components/shared/page-title";
import { ErrorState } from "@/components/shared/error-state";
import { DetailJson } from "@/components/shared/detail-json";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { API_BASE_URL } from "@/lib/constants";
import { jobStatusMeta } from "@/lib/status";
import { formatDateTime, formatDuration } from "@/lib/utils";
import { flowNodeTypes } from "@/components/flows/editor/nodes";
import { NodeDetailPanel } from "@/components/flows/execution/node-detail-panel";
import { TimelineTab } from "@/components/flows/execution/timeline-tab";
import { MetricsTab } from "@/components/flows/execution/metrics-tab";
import { ArtifactsTab } from "@/components/flows/execution/artifacts-tab";
import { AttemptsTab } from "@/components/flows/execution/attempts-tab";
import { ExecutionLogViewer } from "@/components/executions/execution-log-viewer";
import { agentLabelFor, attemptsFor, edgeRuntimeState, flowProgress, nodeExecutionFor, taskFor } from "@/components/flows/execution/node-runtime";
import { cancelFlowExecution } from "@/lib/flow-api";
import type { FlowCanvasEdge, FlowCanvasNode } from "@/components/flows/editor/types";
import type { Automation } from "@/types/automation";
import type { AutomationVersionResponse as AutomationVersion } from "@/types/catalog";
import type { ExecutionArtifact, ExecutionEventsPage, ExecutionMetric } from "@/types/execution";
import type { ExecutionAttempt, Flow, FlowExecutionDetails, TaskExecution } from "@/types/flow";
import type { Worker } from "@/types/worker";

const ACTIVE_FLOW_EXECUTION_STATUSES = new Set(["created", "pending", "running", "cancelling"]);

const EDGE_RUNTIME_COLOR: Record<string, string> = {
  waiting: "hsl(var(--muted-foreground) / 0.5)",
  released: "hsl(var(--info))",
  running: "hsl(var(--info))",
  done: "hsl(var(--success))",
  skipped: "hsl(var(--muted-foreground) / 0.4)",
  failed: "hsl(var(--destructive))",
};

export function FlowExecutionMonitor({ flowExecutionId }: { flowExecutionId: string }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [terminal, setTerminal] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [sseConnected, setSseConnected] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<number | null>(null);

  const details = useApi<FlowExecutionDetails>(`/flow-executions/${flowExecutionId}`, { pollMs: terminal ? undefined : 3000 });

  useEffect(() => {
    if (details.data) {
      setTerminal(!ACTIVE_FLOW_EXECUTION_STATUSES.has(details.data.flow_execution.status));
      setLastRefreshedAt(Date.now());
    }
  }, [details.data]);

  const executionId = details.data?.flow_execution.execution_id ?? null;
  const flowId = details.data?.flow_version?.flow_id ?? null;

  const flow = useApi<Flow>(flowId ? `/flows/${flowId}` : null);
  const automations = useApi<Automation[]>("/automations");
  const workers = useApi<Worker[]>("/workers");

  const tasks = useApi<TaskExecution[]>(executionId ? `/executions/${executionId}/tasks` : null, { pollMs: terminal ? undefined : 4000, enabled: !!executionId });
  const attempts = useApi<ExecutionAttempt[]>(executionId ? `/executions/${executionId}/attempts` : null, { pollMs: terminal ? undefined : 4000, enabled: !!executionId });
  const events = useApi<ExecutionEventsPage>(executionId ? `/executions/${executionId}/events?limit=500` : null, { pollMs: terminal ? undefined : 5000, enabled: !!executionId });
  const metrics = useApi<ExecutionMetric[]>(executionId ? `/executions/${executionId}/metrics?limit=500` : null, { pollMs: terminal ? undefined : 8000, enabled: !!executionId });
  const artifacts = useApi<ExecutionArtifact[]>(executionId ? `/executions/${executionId}/artifacts` : null, { pollMs: terminal ? undefined : 8000, enabled: !!executionId });

  const [automationVersions, setAutomationVersions] = useState<AutomationVersion[]>([]);
  const loadedAutomationVersionIds = useRef(new Set<number>());
  useEffect(() => {
    if (!token || !details.data) return;
    const ids = Array.from(new Set(details.data.nodes.map((n) => n.automation_version_id).filter(Boolean))) as number[];
    const toLoad = ids.filter((id) => !loadedAutomationVersionIds.current.has(id));
    if (toLoad.length === 0) return;
    toLoad.forEach((id) => loadedAutomationVersionIds.current.add(id));
    Promise.all(
      toLoad.map(async (id) => {
        try {
          return await apiRequest<AutomationVersion>(`/automation-versions/${id}`, { token });
        } catch {
          return null;
        }
      }),
    ).then((results) => {
      const found = results.filter((v): v is AutomationVersion => v !== null);
      if (found.length > 0) setAutomationVersions((prev) => [...prev, ...found]);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, details.data?.nodes.length]);

  // SSE best-effort: infraestrutura de push ainda não publica eventos de negócio no backend
  // (ver observação no relatório) — mantemos a conexão como canal suplementar honesto,
  // com o polling acima como fonte de verdade.
  useEffect(() => {
    if (!token || !executionId) return;
    const source = new EventSource(`${API_BASE_URL}/executions/${executionId}/stream?token=${encodeURIComponent(token)}`);
    const refetchAll = () => {
      void details.refetch();
      void tasks.refetch();
      void attempts.refetch();
      void events.refetch();
    };
    source.addEventListener("open", () => setSseConnected(true));
    source.addEventListener("execution.event", refetchAll);
    source.addEventListener("execution.summary", refetchAll);
    source.addEventListener("execution.progress", refetchAll);
    source.onerror = () => setSseConnected(false);
    return () => {
      source.close();
      setSseConnected(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, executionId]);

  const tab = searchParams.get("tab") ?? "resumo";
  const nodeParam = searchParams.get("node");
  const levelParam = searchParams.get("level") ?? "";

  function setQuery(patch: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(patch).forEach(([key, value]) => {
      if (value === null) params.delete(key);
      else params.set(key, value);
    });
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  const agentLabelById = useMemo(() => {
    const map = new Map<string, string>();
    (workers.data ?? []).forEach((w) => {
      if (w.agent_id) map.set(w.agent_id, w.name);
    });
    return map;
  }, [workers.data]);

  const nodeLabelByTask = useMemo(() => {
    const map = new Map<string, string>();
    if (!details.data) return map;
    details.data.node_executions.forEach((ne) => {
      if (!ne.task_execution_id) return;
      const node = details.data!.nodes.find((n) => n.id === ne.flow_node_id);
      if (node) map.set(ne.task_execution_id, node.name || node.key);
    });
    return map;
  }, [details.data]);

  const automationLabelFor = useCallback(
    (versionId: number | null): { name?: string; version?: string } => {
      if (!versionId) return {};
      const version = automationVersions.find((v) => v.id === versionId);
      if (!version) return {};
      const automation = automations.data?.find((a) => a.id === version.automation_id);
      return { name: automation?.name, version: `v${version.version}` };
    },
    [automationVersions, automations.data],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState<FlowCanvasNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowCanvasEdge>([]);

  useEffect(() => {
    if (!details.data) return;
    const d = details.data;
    const rfNodes: FlowCanvasNode[] = d.nodes.map((fn) => {
      const nodeExecution = nodeExecutionFor(d.node_executions, fn.id);
      const task = taskFor(tasks.data ?? [], nodeExecution?.task_execution_id);
      const nodeAttempts = attemptsFor(attempts.data ?? [], nodeExecution?.task_execution_id);
      const currentAttempt = nodeAttempts[nodeAttempts.length - 1];
      const nodeEvents = (events.data?.items ?? []).filter((e) => e.task_execution_id === nodeExecution?.task_execution_id);
      const lastEvent = [...nodeEvents].sort((a, b) => (b.occurred_at || "").localeCompare(a.occurred_at || ""))[0];
      const automationLabel = automationLabelFor(fn.automation_version_id);
      return {
        id: fn.id,
        type: fn.node_type,
        position: { x: Number(fn.position_metadata?.x ?? 0), y: Number(fn.position_metadata?.y ?? 0) },
        deletable: false,
        draggable: false,
        data: {
          flowNode: fn,
          issues: [],
          readOnly: true,
          automationName: automationLabel.name,
          automationVersionLabel: automationLabel.version,
          runtimeStatus: nodeExecution?.status ?? "pending",
          runtimeMeta: {
            attemptNumber: task?.current_attempt_number ?? null,
            agentLabel: agentLabelFor(currentAttempt?.agent_id, agentLabelById),
            startedAt: nodeExecution?.started_at ?? null,
            completedAt: nodeExecution?.completed_at ?? null,
            lastMessage: lastEvent?.message ?? null,
            logCount: nodeEvents.filter((e) => e.level).length,
            artifactCount: (artifacts.data ?? []).filter((a) => a.task_execution_id === nodeExecution?.task_execution_id).length,
          },
        },
      };
    });

    const rfEdges: FlowCanvasEdge[] = d.edges.map((fe) => {
      const sourceExec = nodeExecutionFor(d.node_executions, fe.source_node_id);
      const targetExec = nodeExecutionFor(d.node_executions, fe.target_node_id);
      const runtimeState = edgeRuntimeState(fe, sourceExec, targetExec);
      const color = EDGE_RUNTIME_COLOR[runtimeState ?? "waiting"];
      return {
        id: fe.id,
        source: fe.source_node_id,
        target: fe.target_node_id,
        deletable: false,
        animated: runtimeState === "running",
        style: { stroke: color, strokeWidth: runtimeState === "failed" ? 3 : 2, strokeDasharray: runtimeState === "waiting" || runtimeState === "skipped" ? "4 3" : undefined },
        markerEnd: { type: MarkerType.ArrowClosed, color },
        data: { edgeType: fe.edge_type, condition: fe.condition, hasMapping: false, issues: [], readOnly: true, runtimeState },
      };
    });

    setNodes(rfNodes);
    setEdges(rfEdges);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [details.data, tasks.data, attempts.data, events.data, artifacts.data, automationVersions, automations.data, agentLabelById]);

  const selectedNode = nodes.find((n) => n.id === nodeParam) ?? null;
  const selectedNodeExecution = details.data && nodeParam ? nodeExecutionFor(details.data.node_executions, nodeParam) : undefined;
  const selectedTask = taskFor(tasks.data ?? [], selectedNodeExecution?.task_execution_id);
  const selectedAttempts = attemptsFor(attempts.data ?? [], selectedNodeExecution?.task_execution_id);
  const selectedNodeEvents = (events.data?.items ?? []).filter((e) => e.task_execution_id === selectedNodeExecution?.task_execution_id);
  const selectedLastMessage = [...selectedNodeEvents].sort((a, b) => (b.occurred_at || "").localeCompare(a.occurred_at || ""))[0]?.message ?? null;

  const handleNodeClick: NodeMouseHandler<FlowCanvasNode> = useCallback(
    (_event, node) => {
      setQuery({ node: node.id });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [searchParams],
  );

  async function handleCancel() {
    if (!token || !details.data) return;
    if (!window.confirm("Cancelar esta execução de Fluxo? Os nós em andamento serão interrompidos.")) return;
    setCancelling(true);
    try {
      await cancelFlowExecution(token, flowExecutionId);
      toast({ title: "Cancelamento solicitado", kind: "success" });
      await details.refetch();
    } catch (err) {
      toast({ title: "Falha ao cancelar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setCancelling(false);
    }
  }

  if (details.error) return <ErrorState message={details.error} onRetry={details.refetch} />;
  if (details.loading || !details.data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-[500px] rounded-lg" />
      </div>
    );
  }

  const fe = details.data.flow_execution;
  const statusMeta = jobStatusMeta(fe.status);
  const progress = flowProgress(details.data.node_executions);
  const started = fe.started_at ? new Date(fe.started_at).getTime() : null;
  const completed = fe.completed_at ? new Date(fe.completed_at).getTime() : null;
  const duration = started ? ((completed ?? Date.now()) - started) / 1000 : null;
  const canCancel = ACTIVE_FLOW_EXECUTION_STATUSES.has(fe.status);

  const logs = (events.data?.items ?? [])
    .filter((e) => Boolean(e.level))
    .filter((e) => !levelParam || (e.level ?? "").toUpperCase() === levelParam.toUpperCase())
    .filter((e) => !nodeParam || e.task_execution_id === selectedNodeExecution?.task_execution_id)
    .map((e) => ({ id: e.id, level: e.level ?? "INFO", message: e.message ?? "", created_at: e.occurred_at }))
    .sort((a, b) => a.created_at.localeCompare(b.created_at));

  return (
    <ReactFlowProvider>
      <div className="space-y-5">
        <Breadcrumbs
          items={[
            { label: "Fluxos", href: "/flows" },
            { label: flow.data?.name ?? "Fluxo", href: flowId ? `/flows/${flowId}` : undefined },
            { label: "Execução" },
          ]}
        />

        <PageTitle
          eyebrow="Execução de Fluxo"
          title={flow.data?.name ?? "Fluxo"}
          description={details.data.flow_version ? `v${details.data.flow_version.version} · origem: ${fe.origin}` : fe.origin}
          actions={
            <>
              <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>
              <span className="flex items-center gap-1 text-xs text-muted-foreground" title="Conexão SSE (canal suplementar; polling é a fonte principal)">
                {sseConnected ? <Wifi className="h-3.5 w-3.5 text-success" /> : <WifiOff className="h-3.5 w-3.5" />}
                {terminal ? "encerrada" : "ao vivo"}
              </span>
              <Button size="sm" variant="outline" onClick={details.refetch}>
                <RotateCw className="h-3.5 w-3.5" /> Atualizar
              </Button>
              {canCancel && (
                <Button size="sm" variant="destructive" onClick={handleCancel} disabled={cancelling}>
                  <Ban className="h-3.5 w-3.5" /> {cancelling ? "Cancelando..." : "Cancelar"}
                </Button>
              )}
            </>
          }
        />

        <div className="flex flex-wrap items-center gap-4 rounded-lg border border-border bg-card px-4 py-3 text-sm">
          <Row label="Progresso" value={`${progress.done}/${progress.total} nós (${progress.percentage}%)`} />
          <Row label="Início" value={formatDateTime(fe.started_at)} />
          <Row label="Duração" value={formatDuration(duration)} />
          <Row label="Última atualização" value={lastRefreshedAt ? formatDateTime(new Date(lastRefreshedAt).toISOString()) : "—"} />
          {fe.failure_summary && <span className="text-destructive">{fe.failure_summary}</span>}
        </div>

        <div className="h-[520px] overflow-hidden rounded-lg border border-border bg-muted/20">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={handleNodeClick}
            onPaneClick={() => setQuery({ node: null })}
            nodeTypes={flowNodeTypes}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable
            fitView
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={20} />
            <Controls showInteractive={false} />
            <MiniMap pannable zoomable className="!bg-card" />
            <Panel position="top-right" className="rounded-md border border-border bg-card px-2 py-1 text-[11px] text-muted-foreground shadow-sm">
              {nodes.length} nó(s) · clique em um nó para detalhar
            </Panel>
          </ReactFlow>
        </div>

        <Tabs
          value={tab}
          onValueChange={(next) => setQuery({ tab: next === "resumo" ? null : next })}
          items={[
            { value: "resumo", label: "Resumo" },
            { value: "timeline", label: "Timeline" },
            { value: "logs", label: "Logs", count: logs.length || undefined },
            { value: "metricas", label: "Métricas" },
            { value: "artefatos", label: "Artefatos" },
            { value: "tentativas", label: "Tentativas" },
          ]}
        />

        {tab === "resumo" && (
          <div className="grid gap-4 lg:grid-cols-2">
            {Object.keys(fe.input || {}).length > 0 && (
              <div>
                <p className="mb-1.5 text-xs font-medium text-muted-foreground">Entrada</p>
                <DetailJson data={fe.input} />
              </div>
            )}
            {fe.output && Object.keys(fe.output).length > 0 && (
              <div>
                <p className="mb-1.5 text-xs font-medium text-muted-foreground">Saída</p>
                <DetailJson data={fe.output} />
              </div>
            )}
          </div>
        )}

        {tab === "timeline" && (
          <TimelineTab
            events={events.data?.items ?? []}
            loading={events.loading}
            error={events.error}
            onRetry={events.refetch}
            nodeLabelByTask={nodeLabelByTask}
            agentLabelById={agentLabelById}
            nodeFilter={selectedNodeExecution?.task_execution_id ?? null}
            onNodeFilterChange={(taskId) => {
              if (!taskId) {
                setQuery({ node: null });
                return;
              }
              const node = details.data!.node_executions.find((ne) => ne.task_execution_id === taskId);
              if (node) setQuery({ node: node.flow_node_id });
            }}
          />
        )}

        {tab === "logs" && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Select className="w-40" value={levelParam} onChange={(e) => setQuery({ level: e.target.value || null })}>
                <option value="">Todos os níveis</option>
                <option value="DEBUG">Debug</option>
                <option value="INFO">Info</option>
                <option value="WARNING">Warning</option>
                <option value="ERROR">Error</option>
                <option value="CRITICAL">Critical</option>
              </Select>
              {nodeParam && (
                <Badge tone="primary" className="cursor-pointer" onClick={() => setQuery({ node: null })}>
                  Filtrado por nó · limpar ✕
                </Badge>
              )}
            </div>
            {events.error ? (
              <ErrorState message={events.error} onRetry={events.refetch} />
            ) : events.loading ? (
              <Skeleton className="h-64 rounded-lg" />
            ) : (
              <ExecutionLogViewer logs={logs} />
            )}
          </div>
        )}

        {tab === "metricas" && (
          <MetricsTab metrics={metrics.data ?? []} loading={metrics.loading} error={metrics.error} onRetry={metrics.refetch} nodeLabelByTask={nodeLabelByTask} />
        )}

        {tab === "artefatos" && (
          <ArtifactsTab artifacts={artifacts.data ?? []} loading={artifacts.loading} error={artifacts.error} onRetry={artifacts.refetch} nodeLabelByTask={nodeLabelByTask} />
        )}

        {tab === "tentativas" && (
          <AttemptsTab
            tasks={tasks.data ?? []}
            attempts={attempts.data ?? []}
            loading={tasks.loading}
            error={tasks.error}
            onRetry={tasks.refetch}
            nodeLabelByTask={nodeLabelByTask}
            agentLabelById={agentLabelById}
          />
        )}
      </div>

      <NodeDetailPanel
        node={selectedNode?.data.flowNode ?? null}
        nodeExecution={selectedNodeExecution}
        task={selectedTask}
        attempts={selectedAttempts}
        agentLabel={agentLabelFor(selectedAttempts[selectedAttempts.length - 1]?.agent_id, agentLabelById)}
        logCount={selectedNodeEvents.filter((e) => e.level).length}
        artifactCount={(artifacts.data ?? []).filter((a) => a.task_execution_id === selectedNodeExecution?.task_execution_id).length}
        lastMessage={selectedLastMessage}
        onClose={() => setQuery({ node: null })}
        onViewLogs={() => setQuery({ tab: "logs" })}
      />
    </ReactFlowProvider>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="text-muted-foreground">{label}:</span>
      <span className="tabular font-medium">{value}</span>
    </span>
  );
}
