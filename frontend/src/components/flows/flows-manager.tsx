"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Search, Plus, GitBranch, Copy, Archive, Play, History, Pencil, ArrowUpDown } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { hasPermission } from "@/lib/permissions";
import { flowStatusMeta, flowVersionStatusMeta, jobStatusMeta } from "@/lib/status";
import { FlowForm, emptyFlowForm, flowToForm, parseTags, type FlowFormState } from "@/components/flows/flow-form";
import { RunFlowDialog } from "@/components/flows/run-flow-dialog";
import {
  archiveFlow,
  cloneFlowVersionInto,
  createFlow,
  createFlowVersion,
  listFlowEdges,
  listFlowNodes,
  listFlowVersions,
  pickHeadlineVersion,
  updateFlow,
} from "@/lib/flow-api";
import type { Category } from "@/types/category";
import type { User } from "@/types/user";
import type { Schedule } from "@/types/schedule";
import type { Flow, FlowExecution, FlowVersion } from "@/types/flow";

type SortField = "name" | "status" | "last_execution" | "updated_at";

export function FlowsManager() {
  const { token, user } = useAuth();
  const { toast } = useToast();
  const router = useRouter();

  const flows = useApi<Flow[]>("/flows");
  const categories = useApi<Category[]>("/categories");
  const executions = useApi<FlowExecution[]>("/flow-executions?limit=300", { pollMs: 15000 });
  const schedules = useApi<Schedule[]>("/schedules");
  const users = useApi<User[]>(hasPermission(user, "admin.users") ? "/users" : null);

  const [versionsByFlow, setVersionsByFlow] = useState<Record<string, FlowVersion[]>>({});
  const [nodeCountByFlow, setNodeCountByFlow] = useState<Record<string, number>>({});
  const [versionsLoaded, setVersionsLoaded] = useState(false);

  // Busca a última versão de cada Flow (uma vez, após a lista carregar) para exibir
  // "versão publicada" e permitir duplicar/criar nova versão sem re-abrir o editor.
  // Em seguida busca a contagem de nós apenas da versão "manchete" de cada Flow.
  const flowIdsKey = (flows.data ?? []).map((f) => f.id).join(",");
  useEffect(() => {
    if (!token || !flows.data || flows.data.length === 0) {
      setVersionsLoaded(true);
      return;
    }
    let cancelled = false;
    setVersionsLoaded(false);
    Promise.all(
      flows.data.map(async (flow) => {
        try {
          const versions = await listFlowVersions(token, flow.id);
          return [flow.id, versions] as [string, FlowVersion[]];
        } catch {
          return [flow.id, []] as [string, FlowVersion[]];
        }
      }),
    ).then(async (entries) => {
      if (cancelled) return;
      const versionsMap = Object.fromEntries(entries);
      setVersionsByFlow(versionsMap);
      setVersionsLoaded(true);

      const counts = await Promise.all(
        entries.map(async ([flowId, versions]) => {
          const headline = pickHeadlineVersion(versions);
          if (!headline) return [flowId, 0] as const;
          try {
            const nodes = await listFlowNodes(token, headline.id);
            return [flowId, nodes.length] as const;
          } catch {
            return [flowId, 0] as const;
          }
        }),
      );
      if (!cancelled) setNodeCountByFlow(Object.fromEntries(counts));
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, flowIdsKey]);

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [ownerFilter, setOwnerFilter] = useState("");
  const [scheduledFilter, setScheduledFilter] = useState("");
  const [lastResultFilter, setLastResultFilter] = useState("");
  const [sort, setSort] = useState<{ field: SortField; dir: "asc" | "desc" }>({ field: "updated_at", dir: "desc" });

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Flow | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [runTarget, setRunTarget] = useState<Flow | null>(null);

  const categoryName = useMemo(() => {
    const map = new Map<number, string>();
    categories.data?.forEach((c) => map.set(c.id, c.name));
    return map;
  }, [categories.data]);

  const userName = useMemo(() => {
    const map = new Map<string, string>();
    users.data?.forEach((u) => map.set(String(u.id), u.name));
    return map;
  }, [users.data]);

  const allTags = useMemo(() => {
    const set = new Set<string>();
    flows.data?.forEach((f) => f.tags.forEach((t) => set.add(t)));
    return Array.from(set).sort();
  }, [flows.data]);

  const nextScheduleByFlow = useMemo(() => {
    const map = new Map<string, string>();
    (schedules.data ?? [])
      .filter((s) => s.target_type === "flow" && s.flow_id && s.is_active && s.next_run_at)
      .forEach((s) => {
        const flowId = s.flow_id as string;
        const current = map.get(flowId);
        if (!current || (s.next_run_at as string) < current) map.set(flowId, s.next_run_at as string);
      });
    return map;
  }, [schedules.data]);

  const executionStatsByVersion = useMemo(() => {
    const byVersion = new Map<string, FlowExecution[]>();
    (executions.data ?? []).forEach((exec) => {
      const list = byVersion.get(exec.flow_version_id) ?? [];
      list.push(exec);
      byVersion.set(exec.flow_version_id, list);
    });
    return byVersion;
  }, [executions.data]);

  function statsForFlow(flow: Flow) {
    const versions = versionsByFlow[flow.id] ?? [];
    const versionIds = new Set(versions.map((v) => v.id));
    const allExecs = versions.flatMap((v) => executionStatsByVersion.get(v.id) ?? []);
    const sorted = allExecs.sort((a, b) => b.created_at.localeCompare(a.created_at));
    const last = sorted[0];
    const recent = sorted.slice(0, 20);
    const finished = recent.filter((e) => ["succeeded", "failed", "partially_succeeded", "cancelled", "timed_out"].includes(e.status));
    const successRate = finished.length > 0 ? Math.round((finished.filter((e) => e.status === "succeeded").length / finished.length) * 100) : null;
    const lastDurationSeconds =
      last?.started_at && last?.completed_at
        ? Math.max(0, (new Date(last.completed_at).getTime() - new Date(last.started_at).getTime()) / 1000)
        : null;
    const headline = pickHeadlineVersion(versions);
    return { last, successRate, lastDurationSeconds, headline, versions, versionIds };
  }

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = (flows.data ?? []).map((flow) => ({ flow, stats: statsForFlow(flow) }));

    list = list.filter(({ flow, stats }) => {
      const matchesQuery = !q || flow.name.toLowerCase().includes(q) || flow.key.toLowerCase().includes(q);
      const matchesStatus = !statusFilter || flow.status === statusFilter;
      const matchesTag = !tagFilter || flow.tags.includes(tagFilter);
      const matchesOwner = !ownerFilter || flow.created_by === ownerFilter;
      const matchesScheduled =
        !scheduledFilter || (scheduledFilter === "yes" ? nextScheduleByFlow.has(flow.id) : !nextScheduleByFlow.has(flow.id));
      const matchesLastResult = !lastResultFilter || stats.last?.status === lastResultFilter;
      return matchesQuery && matchesStatus && matchesTag && matchesOwner && matchesScheduled && matchesLastResult;
    });

    list.sort((a, b) => {
      const dir = sort.dir === "asc" ? 1 : -1;
      if (sort.field === "name") return a.flow.name.localeCompare(b.flow.name) * dir;
      if (sort.field === "status") return a.flow.status.localeCompare(b.flow.status) * dir;
      if (sort.field === "last_execution") {
        const av = a.stats.last?.created_at ?? "";
        const bv = b.stats.last?.created_at ?? "";
        return av.localeCompare(bv) * dir;
      }
      return (a.flow.updated_at ?? a.flow.created_at).localeCompare(b.flow.updated_at ?? b.flow.created_at) * dir;
    });

    return list;
  }, [flows.data, query, statusFilter, tagFilter, ownerFilter, scheduledFilter, lastResultFilter, sort, versionsByFlow, executionStatsByVersion, nextScheduleByFlow]);

  function toggleSort(field: SortField) {
    setSort((prev) => (prev.field === field ? { field, dir: prev.dir === "asc" ? "desc" : "asc" } : { field, dir: "asc" }));
  }

  function openCreate() {
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(flow: Flow) {
    setEditing(flow);
    setFormOpen(true);
  }

  async function handleSubmit(form: FlowFormState) {
    if (!token) return;
    setSubmitting(true);
    try {
      const body = {
        name: form.name,
        description: form.description || null,
        category_id: form.category_id ? Number(form.category_id) : null,
        tags: parseTags(form.tags),
      };
      if (editing) {
        await updateFlow(token, editing.id, body);
        toast({ title: "Fluxo atualizado", kind: "success" });
        setFormOpen(false);
        await flows.refetch();
      } else {
        const created = await createFlow(token, { key: form.key, ...body });
        let draft: FlowVersion | null = null;
        try {
          draft = await createFlowVersion(token, created.id, { version: "0.1.0" });
        } catch (versionError) {
          toast({
            title: "Fluxo criado, mas o rascunho não pôde ser preparado",
            description: versionError instanceof Error ? versionError.message : "Abra o fluxo e crie a primeira versão.",
            kind: "warning",
          });
        }
        if (draft) toast({ title: "Fluxo e rascunho criados", description: "Escolha a primeira automação para começar a montar.", kind: "success" });
        setFormOpen(false);
        router.push(draft ? `/flows/${created.id}?version=${draft.id}` : `/flows/${created.id}`);
      }
    } catch (err) {
      toast({ title: "Falha ao salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleArchive(flow: Flow) {
    if (!token) return;
    if (!window.confirm(`Arquivar o Fluxo "${flow.name}"? Ele deixa de poder ser executado.`)) return;
    try {
      await archiveFlow(token, flow.id);
      toast({ title: "Fluxo arquivado", kind: "success" });
      await flows.refetch();
    } catch (err) {
      toast({ title: "Falha ao arquivar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function handleDuplicate(flow: Flow) {
    if (!token) return;
    const stats = statsForFlow(flow);
    const suggestion = `${flow.key}_copia`;
    const key = window.prompt("Key do novo Fluxo (cópia):", suggestion);
    if (!key) return;
    try {
      const created = await createFlow(token, {
        key,
        name: `${flow.name} (cópia)`,
        description: flow.description,
        category_id: flow.category_id,
        tags: flow.tags,
      });
      if (stats.headline) {
        const [nodes, edges] = await Promise.all([listFlowNodes(token, stats.headline.id), listFlowEdges(token, stats.headline.id)]);
        await cloneFlowVersionInto(token, created.id, stats.headline, nodes, edges, "1.0.0");
        toast({ title: "Fluxo duplicado", description: "Versão, nós e conexões copiados como rascunho 1.0.0.", kind: "success" });
      } else {
        toast({ title: "Fluxo duplicado", description: "Metadados copiados — o fluxo original não tinha versões para copiar.", kind: "success" });
      }
      await flows.refetch();
      router.push(`/flows/${created.id}`);
    } catch (err) {
      toast({ title: "Falha ao duplicar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  const loading = flows.loading || categories.loading;
  const error = flows.error || categories.error;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:flex-wrap">
        <div className="relative flex-1 lg:min-w-[220px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" placeholder="Buscar por nome ou key..." value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="lg:w-40">
          <option value="">Todo status</option>
          <option value="draft">Rascunho</option>
          <option value="active">Ativo</option>
          <option value="disabled">Desativado</option>
          <option value="archived">Arquivado</option>
        </Select>
        <Select value={tagFilter} onChange={(e) => setTagFilter(e.target.value)} className="lg:w-40">
          <option value="">Todas as tags</option>
          {allTags.map((tag) => (
            <option key={tag} value={tag}>
              {tag}
            </option>
          ))}
        </Select>
        {users.data && users.data.length > 0 && (
          <Select value={ownerFilter} onChange={(e) => setOwnerFilter(e.target.value)} className="lg:w-44">
            <option value="">Todo responsável</option>
            {users.data.map((u) => (
              <option key={u.id} value={String(u.id)}>
                {u.name}
              </option>
            ))}
          </Select>
        )}
        <Select value={scheduledFilter} onChange={(e) => setScheduledFilter(e.target.value)} className="lg:w-44">
          <option value="">Agendamento (todos)</option>
          <option value="yes">Com agendamento</option>
          <option value="no">Sem agendamento</option>
        </Select>
        <Select value={lastResultFilter} onChange={(e) => setLastResultFilter(e.target.value)} className="lg:w-44">
          <option value="">Último resultado (todos)</option>
          <option value="succeeded">Sucesso</option>
          <option value="failed">Falha</option>
          <option value="partially_succeeded">Parcial</option>
          <option value="cancelled">Cancelado</option>
          <option value="running">Em execução</option>
        </Select>
        <Button onClick={openCreate} className="lg:ml-auto">
          <Plus className="h-4 w-4" /> Novo fluxo
        </Button>
      </div>

      {error ? (
        <ErrorState message={error} onRetry={flows.refetch} />
      ) : loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-14 rounded-lg" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={GitBranch}
          title="Nenhum fluxo"
          description={
            query || statusFilter || tagFilter
              ? "Nenhum resultado para os filtros atuais."
              : "Crie o primeiro Fluxo para orquestrar automações com dependências, condições e acompanhamento visual."
          }
          action={
            !query && !statusFilter ? (
              <Button onClick={openCreate}>
                <Plus className="h-4 w-4" /> Novo fluxo
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <Table>
            <THead>
              <TR>
                <TH className="cursor-pointer select-none" onClick={() => toggleSort("name")}>
                  <span className="inline-flex items-center gap-1">Fluxo <ArrowUpDown className="h-3 w-3" /></span>
                </TH>
                <TH className="cursor-pointer select-none" onClick={() => toggleSort("status")}>Status</TH>
                <TH>Versão</TH>
                <TH>Nós</TH>
                <TH className="cursor-pointer select-none" onClick={() => toggleSort("last_execution")}>Última execução</TH>
                <TH>Duração</TH>
                <TH>Sucesso (20)</TH>
                <TH>Próx. agendamento</TH>
                <TH>Tags</TH>
                <TH className="text-right">Ações</TH>
              </TR>
            </THead>
            <TBody>
              {rows.map(({ flow, stats }) => {
                const statusMeta = flowStatusMeta(flow.status);
                const StatusIcon = statusMeta.icon;
                const versionMeta = stats.headline ? flowVersionStatusMeta(stats.headline.status) : null;
                const lastMeta = stats.last ? jobStatusMeta(stats.last.status) : null;
                const nextRun = nextScheduleByFlow.get(flow.id);
                return (
                  <TR key={flow.id}>
                    <TD>
                      <Link href={`/flows/${flow.id}`} className="font-medium text-foreground hover:text-primary">
                        {flow.name}
                      </Link>
                      <p className="text-xs text-muted-foreground">{flow.key}</p>
                      {categoryName.get(flow.category_id ?? -1) && (
                        <p className="text-xs text-muted-foreground">{categoryName.get(flow.category_id!)}</p>
                      )}
                    </TD>
                    <TD>
                      <Badge tone={statusMeta.tone}>
                        <StatusIcon className="h-3.5 w-3.5" /> {statusMeta.label}
                      </Badge>
                    </TD>
                    <TD>
                      {stats.headline ? (
                        <Badge tone={versionMeta!.tone}>v{stats.headline.version} · {versionMeta!.label}</Badge>
                      ) : (
                        <span className="text-xs text-muted-foreground">sem versão</span>
                      )}
                    </TD>
                    <TD className="tabular text-sm text-muted-foreground">
                      {versionsLoaded ? (nodeCountByFlow[flow.id] ?? 0) : <Skeleton className="h-4 w-6" />}
                    </TD>
                    <TD>
                      {stats.last ? (
                        <Badge tone={lastMeta!.tone}>{lastMeta!.label}</Badge>
                      ) : (
                        <span className="text-xs text-muted-foreground">nunca executado</span>
                      )}
                    </TD>
                    <TD className="tabular text-sm text-muted-foreground">
                      {stats.lastDurationSeconds != null ? formatDuration(stats.lastDurationSeconds) : "—"}
                    </TD>
                    <TD className="tabular text-sm text-muted-foreground">{stats.successRate != null ? `${stats.successRate}%` : "—"}</TD>
                    <TD className="text-sm text-muted-foreground">{nextRun ? formatDateTime(nextRun) : "—"}</TD>
                    <TD>
                      <div className="flex max-w-[160px] flex-wrap gap-1">
                        {flow.tags.slice(0, 3).map((tag) => (
                          <Badge key={tag} tone="outline" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                        {flow.tags.length > 3 && <span className="text-xs text-muted-foreground">+{flow.tags.length - 3}</span>}
                      </div>
                    </TD>
                    <TD>
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          size="icon"
                          variant="ghost"
                          title={stats.headline?.status === "published" ? "Executar" : "Publique uma versão antes de executar"}
                          onClick={() => setRunTarget(flow)}
                          disabled={flow.status === "archived" || stats.headline?.status !== "published"}
                        >
                          <Play className="h-4 w-4" />
                        </Button>
                        <Button size="icon" variant="ghost" title="Histórico" asChild>
                          <Link href={`/flows/${flow.id}?tab=executions`}>
                            <History className="h-4 w-4" />
                          </Link>
                        </Button>
                        <Button size="icon" variant="ghost" title="Editar metadados" onClick={() => openEdit(flow)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button size="icon" variant="ghost" title="Duplicar" onClick={() => handleDuplicate(flow)}>
                          <Copy className="h-4 w-4" />
                        </Button>
                        {flow.status !== "archived" && (
                          <Button size="icon" variant="ghost" title="Arquivar" onClick={() => handleArchive(flow)}>
                            <Archive className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        </div>
      )}

      <Modal open={formOpen} onClose={() => setFormOpen(false)} title={editing ? "Editar fluxo" : "Novo fluxo"} className="max-w-2xl">
        <FlowForm
          key={editing?.id ?? "new"}
          categories={categories.data ?? []}
          initial={editing ? flowToForm(editing) : emptyFlowForm()}
          lockKey={Boolean(editing)}
          submitting={submitting}
          submitLabel={editing ? "Salvar" : "Criar fluxo"}
          onSubmit={handleSubmit}
        />
      </Modal>

      <RunFlowDialog flow={runTarget} versions={runTarget ? versionsByFlow[runTarget.id] ?? [] : []} open={Boolean(runTarget)} onClose={() => setRunTarget(null)} />
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
