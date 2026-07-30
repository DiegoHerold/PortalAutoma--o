"use client";

import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, GitCompareArrows, ScrollText, Search, X } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { JsonDiff } from "@/components/shared/json-diff";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Label, Select } from "@/components/ui/input";
import { Sheet } from "@/components/ui/sheet";
import { Tabs } from "@/components/ui/tabs";
import { useApi } from "@/hooks/use-api";
import { auditActionLabel, auditActorLabel, auditResourceLabel, redactSensitiveData } from "@/lib/governance-utils";
import { formatDateTime } from "@/lib/utils";
import type { AuditEventFacets, AuditEventFilters, AuditEventResponse } from "@/types/governance";

const PAGE_SIZE = 50;
const EMPTY_FILTERS: AuditEventFilters = {
  query: "",
  actor_type: "",
  resource_type: "",
  action: "",
  date_from: "",
  date_to: "",
  limit: PAGE_SIZE,
  offset: 0,
};

type Period = "all" | "today" | "7" | "30" | "90" | "custom";

export function AuditView() {
  const [draft, setDraft] = useState(EMPTY_FILTERS);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [period, setPeriod] = useState<Period>("all");
  const [correlationFilter, setCorrelationFilter] = useState<string | null>(null);
  const [selected, setSelected] = useState<AuditEventResponse | null>(null);
  const [tab, setTab] = useState("summary");
  const facets = useApi<AuditEventFacets>("/governance/audit-events/facets");

  const path = useMemo(() => `/governance/audit-events?${query(filters)}`, [filters]);
  const audit = useApi<AuditEventResponse[]>(path);
  const visible = (audit.data ?? []).filter((event) => !correlationFilter || event.correlation_id === correlationFilter);
  const nextAvailable = (audit.data?.length ?? 0) === filters.limit;
  const hasFilters = Boolean(filters.query || filters.actor_type || filters.resource_type || filters.action || filters.date_from || filters.date_to);

  function apply() {
    setFilters({ ...draft, offset: 0 });
    setCorrelationFilter(null);
  }

  function clear() {
    setDraft(EMPTY_FILTERS);
    setFilters(EMPTY_FILTERS);
    setPeriod("all");
    setCorrelationFilter(null);
  }

  function choosePeriod(value: Period) {
    setPeriod(value);
    if (value === "custom") return;
    if (value === "all") {
      setDraft((current) => ({ ...current, date_from: "", date_to: "" }));
      return;
    }
    const today = new Date();
    const from = new Date(today);
    from.setDate(today.getDate() - (value === "today" ? 0 : Number(value) - 1));
    setDraft((current) => ({ ...current, date_from: toDateInput(from), date_to: toDateInput(today) }));
  }

  if (audit.error) return <ErrorState message={audit.error.includes("403") ? "Voce nao tem permissao para consultar a auditoria." : audit.error} onRetry={audit.refetch} />;

  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-border bg-card p-4">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div><h2 className="text-base font-semibold">Consultar eventos</h2><p className="mt-1 text-sm text-muted-foreground">Combine periodo, tipo de evento e recurso. A busca geral procura IDs, acao, recurso e correlacao.</p></div>
          {hasFilters && <Button variant="ghost" size="sm" onClick={clear}><X className="h-4 w-4" /> Limpar filtros</Button>}
        </div>
        <div className="grid gap-3 lg:grid-cols-4">
          <Field className="lg:col-span-2"><Label htmlFor="audit-query">Pesquisa geral</Label><Input id="audit-query" value={draft.query} onChange={(event) => setDraft({ ...draft, query: event.target.value })} onKeyDown={(event) => event.key === "Enter" && apply()} placeholder="ID, acao, recurso ou correlacao" /></Field>
          <Field><Label htmlFor="audit-period">Periodo</Label><Select id="audit-period" value={period} onChange={(event) => choosePeriod(event.target.value as Period)}><option value="all">Todo o periodo</option><option value="today">Hoje</option><option value="7">Ultimos 7 dias</option><option value="30">Ultimos 30 dias</option><option value="90">Ultimos 90 dias</option><option value="custom">Intervalo personalizado</option></Select></Field>
          <div className="flex items-end"><Button className="w-full" onClick={apply}><Search className="h-4 w-4" /> Pesquisar</Button></div>
          {period === "custom" && <><Field><Label htmlFor="audit-from">Data inicial</Label><Input id="audit-from" type="date" value={draft.date_from} onChange={(event) => setDraft({ ...draft, date_from: event.target.value })} /></Field><Field><Label htmlFor="audit-to">Data final</Label><Input id="audit-to" type="date" value={draft.date_to} onChange={(event) => setDraft({ ...draft, date_to: event.target.value })} /></Field></>}
          <Field><Label htmlFor="audit-action">Tipo de evento</Label><Select id="audit-action" value={draft.action} onChange={(event) => setDraft({ ...draft, action: event.target.value })}><option value="">Todos os eventos</option>{(facets.data?.actions ?? []).map((item) => <option key={item} value={item}>{auditActionLabel(item)}</option>)}</Select></Field>
          <Field><Label htmlFor="audit-resource">Recurso</Label><Select id="audit-resource" value={draft.resource_type} onChange={(event) => setDraft({ ...draft, resource_type: event.target.value })}><option value="">Todos os recursos</option>{(facets.data?.resource_types ?? []).map((item) => <option key={item} value={item}>{auditResourceLabel(item)}</option>)}</Select></Field>
          <Field><Label htmlFor="audit-actor-type">Origem</Label><Select id="audit-actor-type" value={draft.actor_type} onChange={(event) => setDraft({ ...draft, actor_type: event.target.value })}><option value="">Todos os atores</option>{(facets.data?.actor_types ?? []).map((item) => <option key={item} value={item}>{auditActorLabel(item)}</option>)}</Select></Field>
        </div>
      </section>
      {correlationFilter && <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-info/30 bg-info/5 px-3 py-2 text-sm"><span>Mostrando a correlacao <span className="tabular font-medium">{correlationFilter}</span> nesta pagina.</span><Button size="sm" variant="ghost" onClick={() => setCorrelationFilter(null)}>Limpar</Button></div>}
      {audit.loading ? <div className="h-64 animate-pulse rounded-lg bg-muted" /> : visible.length === 0 ? <EmptyState icon={ScrollText} title="Sem eventos" description={hasFilters ? "Nenhum evento corresponde aos filtros selecionados." : "Ainda nao existem eventos para este escopo."} /> : <div className="overflow-hidden rounded-lg border border-border bg-card"><div className="divide-y divide-border">{visible.map((event) => <EventRow key={event.id} event={event} onOpen={() => { setSelected(event); setTab("summary"); }} onCorrelation={() => event.correlation_id && setCorrelationFilter(event.correlation_id)} />)}</div></div>}
      <div className="flex items-center justify-between gap-3"><p className="text-xs text-muted-foreground">Exibindo {filters.offset + 1}-{filters.offset + (audit.data?.length ?? 0)}. A API nao informa o total.</p><div className="flex gap-2"><Button size="sm" variant="outline" disabled={filters.offset === 0} onClick={() => setFilters((value) => ({ ...value, offset: Math.max(0, value.offset - value.limit) }))}><ChevronLeft className="h-4 w-4" /> Anterior</Button><Button size="sm" variant="outline" disabled={!nextAvailable} onClick={() => setFilters((value) => ({ ...value, offset: value.offset + value.limit }))}>Proxima <ChevronRight className="h-4 w-4" /></Button></div></div>
      <AuditDetails event={selected} tab={tab} onTab={setTab} onClose={() => setSelected(null)} onCorrelation={setCorrelationFilter} />
    </div>
  );
}

function EventRow({ event, onOpen, onCorrelation }: { event: AuditEventResponse; onOpen: () => void; onCorrelation: () => void }) {
  return <button type="button" onClick={onOpen} className="grid w-full gap-2 p-4 text-left hover:bg-muted/40 sm:grid-cols-[minmax(12rem,1fr)_minmax(12rem,1fr)_auto]"><div className="min-w-0"><p className="font-medium">{auditActionLabel(event.action)}</p><p className="mt-1 truncate text-xs text-muted-foreground">{auditResourceLabel(event.resource_type)} <span className="tabular">/ {event.resource_id}</span></p></div><div className="min-w-0 text-sm"><p>{auditActorLabel(event.actor_type)} <span className="tabular">/ {event.actor_id || "sistema"}</span></p><p className="mt-1 text-xs text-muted-foreground">{formatDateTime(event.occurred_at)}</p></div><div className="flex flex-wrap items-start justify-start gap-1 sm:justify-end">{(event.before || event.after) && <Badge tone="info">Alteracao</Badge>}{event.correlation_id && <Badge tone="outline" onClick={(click) => { click.stopPropagation(); onCorrelation(); }} className="tabular hover:bg-accent">{event.correlation_id}</Badge>}</div></button>;
}

function AuditDetails({ event, tab, onTab, onClose, onCorrelation }: { event: AuditEventResponse | null; tab: string; onTab: (tab: string) => void; onClose: () => void; onCorrelation: (value: string) => void }) {
  const before = useMemo(() => redactSensitiveData(event?.before ?? {}), [event]);
  const after = useMemo(() => redactSensitiveData(event?.after ?? {}), [event]);
  const metadata = useMemo(() => redactSensitiveData(event?.metadata ?? {}), [event]);
  return <Sheet open={!!event} onClose={onClose} title={event ? auditActionLabel(event.action) : ""} description={event ? `${auditResourceLabel(event.resource_type)} / ${event.resource_id}` : ""} widthClassName="w-full sm:max-w-3xl">{event && <div className="space-y-5"><Tabs items={[{ value: "summary", label: "Resumo" }, { value: "changes", label: "Alteracoes" }, { value: "metadata", label: "Metadados" }, { value: "technical", label: "Contexto tecnico" }]} value={tab} onValueChange={onTab} />{tab === "summary" && <dl className="grid gap-4 text-sm sm:grid-cols-2"><Detail label="ID" value={event.id} /><Detail label="Data" value={formatDateTime(event.occurred_at)} /><Detail label="Ator" value={`${auditActorLabel(event.actor_type)} / ${event.actor_id || "sistema"}`} /><Detail label="Organizacao" value={event.organization_id ?? "Global"} /><Detail label="Recurso" value={`${auditResourceLabel(event.resource_type)} / ${event.resource_id}`} />{event.correlation_id && <div><dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Correlacao</dt><dd><Button size="sm" variant="outline" className="mt-1 tabular" onClick={() => { onCorrelation(event.correlation_id!); onClose(); }}>{event.correlation_id}</Button></dd></div>}</dl>}{tab === "changes" && <JsonDiff before={before} after={after} />}{tab === "metadata" && <JsonDiff before={{}} after={metadata} />}{tab === "technical" && <dl className="space-y-4 text-sm"><Detail label="IP" value={event.ip || "Nao informado"} /><Detail label="User agent" value={event.user_agent || "Nao informado"} /><Detail label="Acao tecnica" value={event.action} /><Detail label="Tipo tecnico" value={event.resource_type} /></dl>}</div>}</Sheet>;
}

function Detail({ label, value }: { label: string; value: React.ReactNode }) { return <div><dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt><dd className="mt-1 break-words">{value}</dd></div>; }
function query(filters: AuditEventFilters): string { const params = new URLSearchParams({ limit: String(filters.limit), offset: String(filters.offset) }); if (filters.query) params.set("query", filters.query); if (filters.actor_type) params.set("actor_type", filters.actor_type); if (filters.resource_type) params.set("resource_type", filters.resource_type); if (filters.action) params.set("action", filters.action); if (filters.date_from) params.set("date_from", filters.date_from); if (filters.date_to) params.set("date_to", filters.date_to); return params.toString(); }
function toDateInput(value: Date): string { const month = String(value.getMonth() + 1).padStart(2, "0"); const day = String(value.getDate()).padStart(2, "0"); return `${value.getFullYear()}-${month}-${day}`; }
