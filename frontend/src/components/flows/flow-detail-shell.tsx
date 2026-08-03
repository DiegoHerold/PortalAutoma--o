"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { Archive, ExternalLink, Pencil, Play } from "lucide-react";

import { PageTitle } from "@/components/shared/page-title";
import { Breadcrumbs } from "@/components/shared/breadcrumbs";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { flowStatusMeta, flowVersionStatusMeta, jobStatusMeta } from "@/lib/status";
import { FlowEditor } from "@/components/flows/editor/flow-editor";
import { FlowForm, flowToForm, parseTags, type FlowFormState } from "@/components/flows/flow-form";
import { RunFlowDialog } from "@/components/flows/run-flow-dialog";
import { archiveFlow, cloneFlowVersionInto, createFlowVersion, listFlowEdges, listFlowNodes, nextSemver, updateFlow } from "@/lib/flow-api";
import type { Category } from "@/types/category";
import type { Flow, FlowExecution, FlowVersion } from "@/types/flow";

export function FlowDetailShell({ flowId }: { flowId: string }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const flow = useApi<Flow>(`/flows/${flowId}`);
  const versions = useApi<FlowVersion[]>(`/flows/${flowId}/versions`);
  const categories = useApi<Category[]>("/categories");
  const executions = useApi<FlowExecution[]>("/flow-executions?limit=300", { pollMs: 15000 });

  const tab = searchParams.get("tab") === "executions" ? "executions" : "editor";
  const versionParam = searchParams.get("version");

  const [formOpen, setFormOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [runOpen, setRunOpen] = useState(false);
  const [preparingEditor, setPreparingEditor] = useState(false);
  const [editorPrepared, setEditorPrepared] = useState(false);
  const [creatingEditableDraft, setCreatingEditableDraft] = useState(false);

  function setQuery(patch: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(patch).forEach(([key, value]) => {
      if (value === null) params.delete(key);
      else params.set(key, value);
    });
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  function setTab(next: string) {
    setQuery({ tab: next === "editor" ? null : next, version: next === "editor" ? versionParam : null });
  }

  const sortedVersions = useMemo(
    () => [...(versions.data ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [versions.data],
  );

  const draftVersion = sortedVersions.find((v) => v.status === "draft") ?? null;
  const headlineVersion = sortedVersions.find((v) => v.status === "published") ?? sortedVersions[0] ?? null;

  const activeVersion = useMemo(() => {
    if (versionParam) return sortedVersions.find((v) => v.id === versionParam) ?? null;
    return draftVersion ?? headlineVersion;
  }, [versionParam, sortedVersions, draftVersion, headlineVersion]);

  useEffect(() => {
    if (!token || !flow.data || versions.loading || versions.data?.length || editorPrepared) return;
    setEditorPrepared(true);
    setPreparingEditor(true);
    createFlowVersion(token, flowId, { version: "0.1.0" })
      .then(async (created) => {
        await versions.refetch();
        setQuery({ version: created.id });
      })
      .catch((err) => toast({ title: "Não foi possível preparar o editor", description: err instanceof Error ? err.message : undefined, kind: "error" }))
      .finally(() => setPreparingEditor(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, flow.data?.id, versions.loading, versions.data?.length, editorPrepared]);

  async function handleEditSubmit(form: FlowFormState) {
    if (!token || !flow.data) return;
    setSubmitting(true);
    try {
      await updateFlow(token, flow.data.id, {
        name: form.name,
        description: form.description || null,
        category_id: form.category_id ? Number(form.category_id) : null,
        tags: parseTags(form.tags),
      });
      toast({ title: "Fluxo atualizado", kind: "success" });
      setFormOpen(false);
      await flow.refetch();
    } catch (err) {
      toast({ title: "Falha ao salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleArchive() {
    if (!token || !flow.data) return;
    if (!window.confirm(`Arquivar o Fluxo "${flow.data.name}"? Ele deixa de poder ser executado.`)) return;
    try {
      await archiveFlow(token, flow.data.id);
      toast({ title: "Fluxo arquivado", kind: "success" });
      await flow.refetch();
    } catch (err) {
      toast({ title: "Falha ao arquivar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function handleCreateEditableDraft() {
    if (!token || !activeVersion) return;
    setCreatingEditableDraft(true);
    try {
      const [nodes, edges] = await Promise.all([listFlowNodes(token, activeVersion.id), listFlowEdges(token, activeVersion.id)]);
      const draft = await cloneFlowVersionInto(token, flowId, activeVersion, nodes, edges, nextSemver(sortedVersions));
      await versions.refetch();
      setQuery({ version: draft.id });
      toast({ title: "Edição preparada", description: "Você está alterando um novo rascunho; a publicação anterior permanece preservada.", kind: "success" });
    } catch (err) {
      toast({ title: "Falha ao preparar edição", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setCreatingEditableDraft(false);
    }
  }

  const flowExecutionsForThisFlow = useMemo(() => {
    const versionIds = new Set(sortedVersions.map((v) => v.id));
    return (executions.data ?? [])
      .filter((e) => versionIds.has(e.flow_version_id))
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  }, [executions.data, sortedVersions]);

  if (flow.loading || versions.loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-[500px] rounded-lg" />
      </div>
    );
  }

  if (flow.error || !flow.data) {
    return <ErrorState message={flow.error} onRetry={flow.refetch} />;
  }

  const statusMeta = flowStatusMeta(flow.data.status);
  const StatusIcon = statusMeta.icon;

  return (
    <div className="space-y-5">
      <Breadcrumbs items={[{ label: "Fluxos", href: "/flows" }, { label: flow.data.name }]} />

      <PageTitle
        eyebrow="Fluxo"
        title={flow.data.name}
        description={flow.data.description ?? undefined}
        actions={
          <>
            <Badge tone={statusMeta.tone}>
              <StatusIcon className="h-3.5 w-3.5" /> {statusMeta.label}
            </Badge>
            <Button variant="outline" size="sm" onClick={() => setFormOpen(true)}>
              <Pencil className="h-3.5 w-3.5" /> Editar
            </Button>
            <Button
              size="sm"
              onClick={() => setRunOpen(true)}
              disabled={flow.data.status === "archived" || !sortedVersions.some((v) => v.status === "published")}
              title={!sortedVersions.some((v) => v.status === "published") ? "Publique uma versão no Editor antes de executar" : undefined}
            >
              <Play className="h-3.5 w-3.5" /> Executar
            </Button>
            {flow.data.status !== "archived" && (
              <Button variant="outline" size="sm" onClick={handleArchive}>
                <Archive className="h-3.5 w-3.5" /> Arquivar
              </Button>
            )}
          </>
        }
      />

      <Tabs
        value={tab}
        onValueChange={setTab}
        items={[
          { value: "editor", label: "Editor" },
          { value: "executions", label: "Execuções", count: flowExecutionsForThisFlow.length },
        ]}
      />

      {tab === "editor" &&
        (sortedVersions.length === 0 ? (
          <div className="flex h-[420px] items-center justify-center rounded-lg border border-border bg-card">
            <div className="text-center">
              <p className="text-sm font-semibold">Preparando o editor</p>
              <p className="mt-1 text-sm text-muted-foreground">O primeiro rascunho é criado automaticamente.</p>
              {preparingEditor && <Skeleton className="mx-auto mt-4 h-2 w-32" />}
            </div>
          </div>
        ) : activeVersion ? (
          <div className="space-y-3">
            {sortedVersions.length > 1 && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-muted-foreground">Versão exibida:</span>
                <Select className="w-52" value={activeVersion.id} onChange={(e) => setQuery({ version: e.target.value })}>
                  {sortedVersions.map((v) => (
                    <option key={v.id} value={v.id}>
                      v{v.version} · {flowVersionStatusMeta(v.status).label}
                    </option>
                  ))}
                </Select>
                {activeVersion.status !== "draft" && (
                  <span className="text-xs text-muted-foreground">
                    Somente leitura — crie um novo rascunho na aba Versões para editar.
                  </span>
                )}
              </div>
            )}
            <FlowEditor
              key={activeVersion.id}
              flowVersion={activeVersion}
              suggestedPublishVersion={nextSemver(sortedVersions.filter((version) => version.status === "published"))}
              onCreateEditableDraft={creatingEditableDraft ? undefined : handleCreateEditableDraft}
              onVersionChange={(updated) => {
                versions.mutate((prev) => (prev ?? []).map((v) => (v.id === updated.id ? updated : v)));
              }}
            />
          </div>
        ) : null)}

      {tab === "executions" && (
        <FlowExecutionsTab
          executions={flowExecutionsForThisFlow}
          versions={sortedVersions}
          loading={executions.loading}
          error={executions.error}
          onRetry={executions.refetch}
        />
      )}

      <Modal open={formOpen} onClose={() => setFormOpen(false)} title="Editar fluxo" className="max-w-lg">
        <FlowForm
          categories={categories.data ?? []}
          initial={flowToForm(flow.data)}
          lockKey
          submitting={submitting}
          submitLabel="Salvar"
          onSubmit={handleEditSubmit}
        />
      </Modal>

      <RunFlowDialog flow={flow.data} versions={sortedVersions} open={runOpen} onClose={() => setRunOpen(false)} />
    </div>
  );
}

function FlowExecutionsTab({
  executions,
  versions,
  loading,
  error,
  onRetry,
}: {
  executions: FlowExecution[];
  versions: FlowVersion[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  const [versionFilter, setVersionFilter] = useState("");

  const filtered = versionFilter ? executions.filter((e) => e.flow_version_id === versionFilter) : executions;
  const versionLabel = new Map(versions.map((v) => [v.id, `v${v.version}`]));

  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-12 rounded-lg" />
        ))}
      </div>
    );
  }

  if (executions.length === 0) {
    return <EmptyState title="Nenhuma execução" description="Este Fluxo ainda não foi executado." />;
  }

  return (
    <div className="space-y-3">
      {versions.length > 1 && (
        <Select className="w-52" value={versionFilter} onChange={(e) => setVersionFilter(e.target.value)}>
          <option value="">Todas as versões</option>
          {versions.map((v) => (
            <option key={v.id} value={v.id}>
              v{v.version}
            </option>
          ))}
        </Select>
      )}
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <Table>
          <THead>
            <TR>
              <TH>Execução</TH>
              <TH>Versão</TH>
              <TH>Status</TH>
              <TH>Origem</TH>
              <TH>Iniciada em</TH>
              <TH>Duração</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {filtered.map((exec) => {
              const meta = jobStatusMeta(exec.status);
              const duration =
                exec.started_at && exec.completed_at
                  ? formatDuration((new Date(exec.completed_at).getTime() - new Date(exec.started_at).getTime()) / 1000)
                  : exec.started_at
                    ? "em andamento"
                    : "—";
              return (
                <TR key={exec.id}>
                  <TD className="font-mono text-xs">{exec.id.slice(0, 8)}</TD>
                  <TD className="text-sm">{versionLabel.get(exec.flow_version_id) ?? "—"}</TD>
                  <TD>
                    <Badge tone={meta.tone}>{meta.label}</Badge>
                  </TD>
                  <TD className="text-sm text-muted-foreground">{exec.origin}</TD>
                  <TD className="text-sm text-muted-foreground">{exec.started_at ? formatDateTime(exec.started_at) : "—"}</TD>
                  <TD className="tabular text-sm text-muted-foreground">{duration}</TD>
                  <TD>
                    <div className="flex justify-end">
                      <Button size="icon" variant="ghost" title="Ver execução" asChild>
                        <Link href={`/flow-executions/${exec.id}`}>
                          <ExternalLink className="h-4 w-4" />
                        </Link>
                      </Button>
                    </div>
                  </TD>
                </TR>
              );
            })}
          </TBody>
        </Table>
      </div>
    </div>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}min`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}
