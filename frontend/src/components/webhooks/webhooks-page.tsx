"use client";

import { useEffect, useMemo, useState, type ComponentType } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock3,
  Copy,
  Filter,
  Globe2,
  KeyRound,
  PlugZap,
  Plus,
  Power,
  RotateCw,
  Search,
  ShieldCheck,
  Terminal,
  Webhook,
} from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LegacyChainedTriggers } from "@/components/webhooks/legacy-chained-triggers";
import { WebhookDetailsSheet } from "@/components/webhooks/webhook-details-sheet";
import { WebhookForm } from "@/components/webhooks/webhook-form";
import { WebhookSecretDialog } from "@/components/webhooks/webhook-secret-dialog";
import { WebhookTestPanel } from "@/components/webhooks/webhook-test-panel";
import { WebhooksTable } from "@/components/webhooks/webhooks-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { hasAnyPermission, hasPermission } from "@/lib/permissions";
import { webhookStatusMeta } from "@/lib/status";
import { cn, relativeFromNow } from "@/lib/utils";
import type { Automation } from "@/types/automation";
import type { Trigger, TriggerConfig, TriggerCreateResult, TriggerRotateSecretResult } from "@/types/trigger";

import { automationName, triggerToPayload, webhookStatus, type WebhookPayload } from "./webhook-utils";

type StatFilter = Record<string, string | null>;

const RESULT_FILTERS = ["", "success_like", "failed_like", "running_like", "no_execution"] as const;

export function WebhooksPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { token, user } = useAuth();
  const { toast } = useToast();

  const triggers = useApi<Trigger[]>("/triggers", { pollMs: 8000 });
  const automations = useApi<Automation[]>("/automations");
  const config = useApi<TriggerConfig>("/triggers/config");

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Trigger | null>(null);
  const [details, setDetails] = useState<Trigger | null>(null);
  const [testing, setTesting] = useState<Trigger | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [secretDialog, setSecretDialog] = useState<{ title: string; secret: string | null } | null>(null);
  const [copied, setCopied] = useState<"base" | "curl" | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);

  const query = searchParams.get("q") ?? "";
  const statusFilter = searchParams.get("status") ?? "";
  const automationFilter = searchParams.get("automation") ?? "";
  const usageFilter = searchParams.get("usage") ?? "";
  const resultFilter = searchParams.get("result") ?? "";
  const createdFilter = searchParams.get("created") ?? "";
  const securityFilter = searchParams.get("security") ?? "";
  const [queryDraft, setQueryDraft] = useState(query);

  const canRead = hasAnyPermission(user, ["webhook.read", "flow.read"]);
  const canCreate = hasAnyPermission(user, ["webhook.create", "automation.create"]) || (user?.permissions ?? []).some((permission) => permission.can_create);
  const canEdit = hasAnyPermission(user, ["webhook.update", "automation.update"]) || (user?.permissions ?? []).some((permission) => permission.can_edit);
  const canDelete = hasAnyPermission(user, ["webhook.delete", "automation.delete"]) || (user?.permissions ?? []).some((permission) => permission.can_delete);
  const canRotate = hasAnyPermission(user, ["webhook.rotate_secret", "webhook.update", "automation.update"]) || canEdit;
  const canTest = hasAnyPermission(user, ["webhook.test", "automation.execute", "automation.update"]) || hasPermission(user, "flow.read") || canEdit;

  function setQuery(patch: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(patch).forEach(([key, value]) => {
      if (!value) params.delete(key);
      else params.set(key, value);
    });
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  useEffect(() => {
    setQueryDraft(query);
  }, [query]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      if (queryDraft !== query) setQuery({ q: queryDraft.trim() || null });
    }, 300);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryDraft, query]);

  useEffect(() => {
    if (triggers.data || config.data) setLastUpdatedAt(Date.now());
  }, [triggers.data, config.data]);

  const httpsTriggers = (triggers.data ?? []).filter((trigger) => trigger.trigger_type === "https");
  const legacyTriggers = (triggers.data ?? []).filter((trigger) => trigger.trigger_type === "chained");

  const summary = useMemo(() => {
    const now = Date.now();
    return {
      total: httpsTriggers.length,
      active: httpsTriggers.filter((trigger) => webhookStatus(trigger) === "active").length,
      inactive: httpsTriggers.filter((trigger) => webhookStatus(trigger) === "inactive").length,
      noSecret: httpsTriggers.filter((trigger) => !trigger.secret_configured).length,
      invoked24h: httpsTriggers.filter((trigger) => trigger.last_invoked_at && now - new Date(trigger.last_invoked_at).getTime() <= 24 * 60 * 60 * 1000).length,
      neverUsed: httpsTriggers.filter((trigger) => !trigger.last_invoked_at).length,
      failed: httpsTriggers.filter((trigger) => isFailureResult(trigger.last_execution_status)).length,
    };
  }, [httpsTriggers]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return httpsTriggers.filter((trigger) => {
      if (statusFilter && webhookStatus(trigger) !== statusFilter) return false;
      if (automationFilter && String(trigger.automation_id) !== automationFilter) return false;
      if (usageFilter === "used" && !trigger.last_invoked_at) return false;
      if (usageFilter === "unused" && trigger.last_invoked_at) return false;
      if (securityFilter === "no_secret" && trigger.secret_configured) return false;
      if (securityFilter === "with_secret" && !trigger.secret_configured) return false;
      if (resultFilter && !matchesResultFilter(trigger, resultFilter)) return false;
      if (createdFilter && !String(trigger.created_at || "").startsWith(createdFilter)) return false;
      if (!q) return true;
      return (
        (trigger.name || "").toLowerCase().includes(q) ||
        trigger.route_path.toLowerCase().includes(q) ||
        automationName(automations.data, trigger.automation_id).toLowerCase().includes(q)
      );
    });
  }, [automationFilter, automations.data, createdFilter, httpsTriggers, query, resultFilter, securityFilter, statusFilter, usageFilter]);

  const activeChips = filterChips({
    query,
    statusFilter,
    automationFilter,
    usageFilter,
    resultFilter,
    createdFilter,
    securityFilter,
    automations: automations.data ?? [],
  });

  function openCreate() {
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(trigger: Trigger) {
    if (!canEdit) {
      toast({ title: "Sem permissão para editar", kind: "warning" });
      return;
    }
    setEditing(trigger);
    setFormOpen(true);
  }

  async function save(payload: WebhookPayload, current: Trigger | null) {
    if (!token) return;
    setSubmitting(true);
    try {
      if (current) {
        await apiRequest<Trigger>(`/triggers/${current.id}`, { method: "PUT", token, body: JSON.stringify(payload) });
        toast({ title: "Webhook atualizado", kind: "success" });
      } else {
        const created = await apiRequest<TriggerCreateResult>("/triggers", { method: "POST", token, body: JSON.stringify(payload) });
        setSecretDialog({ title: "Secret do novo Webhook", secret: created.secret_token });
        toast({ title: "Webhook criado", description: "Copie o secret antes de fechar a janela.", kind: "success" });
      }
      setFormOpen(false);
      setEditing(null);
      await triggers.refetch();
    } catch (err) {
      toast({ title: "Falha ao salvar Webhook", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  async function rotate(trigger: Trigger) {
    if (!token || !canRotate) return;
    if (!window.confirm(`Rotacionar o secret de "${trigger.name || trigger.route_path}"? O secret atual será invalidado.`)) return;
    try {
      const result = await apiRequest<TriggerRotateSecretResult>(`/triggers/${trigger.id}/rotate-secret`, { method: "POST", token });
      setSecretDialog({ title: "Novo secret gerado", secret: result.secret_token });
      toast({ title: "Secret rotacionado", kind: "success" });
      await triggers.refetch();
    } catch (err) {
      toast({ title: "Falha ao rotacionar secret", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function toggle(trigger: Trigger) {
    if (!token || !canEdit) return;
    try {
      await apiRequest<Trigger>(`/triggers/${trigger.id}`, {
        method: "PUT",
        token,
        body: JSON.stringify(triggerToPayload(trigger, { is_active: !trigger.is_active })),
      });
      toast({ title: trigger.is_active ? "Webhook desativado" : "Webhook ativado", kind: "success" });
      await triggers.refetch();
    } catch (err) {
      toast({ title: "Falha ao alterar status", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function disableLegacy(trigger: Trigger) {
    if (!token || !canEdit) return;
    try {
      await apiRequest<Trigger>(`/triggers/${trigger.id}`, {
        method: "PUT",
        token,
        body: JSON.stringify({
          name: trigger.name,
          automation_id: trigger.automation_id,
          trigger_type: "chained",
          route_path: trigger.route_path,
          is_active: false,
          parameter_mapping_json: trigger.parameter_mapping_json,
          template: trigger.template,
          source_automation_id: trigger.source_automation_id,
          condition: trigger.condition,
        }),
      });
      toast({ title: "Gatilho legado desativado", kind: "success" });
      await triggers.refetch();
    } catch (err) {
      toast({ title: "Falha ao desativar legado", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function remove(trigger: Trigger) {
    if (!token || !canDelete) return;
    const target = automationName(automations.data, trigger.automation_id);
    const label = trigger.name || trigger.route_path;
    const related = trigger.last_execution_id ? "Há histórico de execução relacionado; ele será preservado." : "Não há última execução registrada neste retorno.";
    if (!window.confirm(`Excluir "${label}"?\nDestino: ${target}\nRoute path: ${trigger.route_path}\n${related}`)) return;
    try {
      await apiRequest<void>(`/triggers/${trigger.id}`, { method: "DELETE", token });
      toast({ title: "Registro excluído", kind: "success" });
      if (details?.id === trigger.id) setDetails(null);
      await triggers.refetch();
    } catch (err) {
      toast({ title: "Falha ao excluir", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function copy(value: string, kind: "base" | "curl") {
    if (!value) return;
    await navigator.clipboard.writeText(value);
    setCopied(kind);
    toast({ title: kind === "base" ? "Base copiada" : "Exemplo copiado", kind: "success" });
    setTimeout(() => setCopied(null), 1400);
  }

  if (!canRead) {
    return <ErrorState message="Seu usuário não possui permissão para visualizar Webhooks." />;
  }

  if (triggers.error) return <ErrorState message={triggers.error} onRetry={triggers.refetch} />;

  const baseUrl = config.data?.invoke_base_url ?? "";
  const exampleUrl = baseUrl ? `${baseUrl}/clientes/novo` : "{invoke_base_url}/clientes/novo";
  const exampleCurl = [
    `curl -X POST "${exampleUrl}"`,
    '  -H "Content-Type: application/json"',
    `  -H "${config.data?.required_header || "X-Trigger-Secret"}: SEU_SECRET"`,
    '  -H "Idempotency-Key: cliente-123-evento-456"',
    '  -H "X-Correlation-ID: crm-123"',
    "  -d '{\"company_id\":123,\"event\":\"created\"}'",
  ].join(" \\\n");

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-1.5">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Entrada externa</p>
          <h1 className="font-display text-2xl font-semibold tracking-tight sm:text-3xl">Webhooks</h1>
          <p className="max-w-3xl text-sm text-muted-foreground">
            Publique endpoints HTTP autenticados para CRMs, ERPs, formulários, n8n, Zapier e outros sistemas iniciarem execuções oficiais no Portal.
          </p>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Badge tone="outline">
              <Globe2 className="h-3.5 w-3.5" /> {config.data?.method || "POST"} JSON
            </Badge>
            <Badge tone="outline">
              <KeyRound className="h-3.5 w-3.5" /> {config.data?.required_header || "X-Trigger-Secret"}
            </Badge>
            <span>{lastUpdatedAt ? `Atualizado ${relativeFromNow(new Date(lastUpdatedAt).toISOString())}` : "Aguardando dados"}</span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" onClick={() => void Promise.all([triggers.refetch(), config.refetch()])} disabled={triggers.loading || config.loading}>
            <RotateCw className={cn("h-4 w-4", (triggers.loading || config.loading) && "animate-spin")} /> Atualizar
          </Button>
          <Button onClick={openCreate} disabled={!canCreate || automations.loading}>
            <Plus className="h-4 w-4" /> Novo Webhook
          </Button>
        </div>
      </header>

      <div className="grid gap-3 md:grid-cols-3 2xl:grid-cols-6">
        <MetricButton icon={PlugZap} label="Ativos" value={summary.active} hint={`${summary.total} HTTP`} onClick={() => setQuery({ status: "active" })} />
        <MetricButton icon={Clock3} label="Sem uso" value={summary.neverUsed} hint="Nunca invocados" onClick={() => setQuery({ usage: "unused" })} />
        <MetricButton icon={CheckCircle2} label="Chamaram 24h" value={summary.invoked24h} hint="Recebidos recentemente" onClick={() => setQuery({ usage: "used" })} />
        <MetricButton icon={AlertTriangle} label="Falhas" value={summary.failed} hint="Último resultado falhou" onClick={() => setQuery({ result: "failed_like" })} />
        <MetricButton icon={ShieldCheck} label="Sem secret" value={summary.noSecret} hint="Exige atenção" onClick={() => setQuery({ security: "no_secret" })} />
        <MetricButton icon={Power} label="Inativos" value={summary.inactive} hint="Bloqueados para chamada" onClick={() => setQuery({ status: "inactive" })} />
      </div>

      <section className="grid gap-4 rounded-lg border border-border bg-card p-4 lg:grid-cols-[minmax(0,1fr)_minmax(360px,0.8fr)]">
        <div className="space-y-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-primary">Como conectar</p>
            <h2 className="mt-1 font-display text-lg font-semibold tracking-tight">Endpoint público, secret por header e idempotência</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Cada webhook tem um route path próprio. Sistemas externos devem enviar JSON, o secret no header e uma chave idempotente quando o evento puder ser repetido.
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            <Step number="1" title="Crie o route path" text="Escolha a automação destino e um caminho legível." />
            <Step number="2" title="Copie o secret" text="O token aparece uma única vez ao criar ou rotacionar." />
            <Step number="3" title="Teste o mapping" text="Valide payload, headers e query sem criar execução." />
          </div>
        </div>
        <div className="min-w-0 rounded-md border border-border bg-background">
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <Terminal className="h-3.5 w-3.5" /> Exemplo de chamada
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline disabled:cursor-not-allowed disabled:text-muted-foreground"
                onClick={() => copy(baseUrl, "base")}
                disabled={!baseUrl}
              >
                {copied === "base" ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                {copied === "base" ? "Base copiada" : "Copiar base"}
              </button>
              <button type="button" className="inline-flex items-center gap-1 text-xs text-primary hover:underline" onClick={() => copy(exampleCurl, "curl")}>
                {copied === "curl" ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                {copied === "curl" ? "cURL copiado" : "Copiar cURL"}
              </button>
            </div>
          </div>
          <pre className="tabular max-h-52 overflow-auto whitespace-pre-wrap p-3 text-xs">{exampleCurl}</pre>
          <div className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
            Aceita <code className="rounded bg-muted px-1">application/json</code>, limite de payload de 1 MB e rate limit por IP.{" "}
            <code className="rounded bg-muted px-1">X-Correlation-ID</code> ajuda a rastrear a execução.
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <div className="grid gap-2 rounded-lg border border-border bg-card p-3 lg:grid-cols-[minmax(220px,1.2fr)_160px_220px_145px_165px_150px_150px]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="pl-9" placeholder="Buscar nome, route path ou automação" value={queryDraft} onChange={(event) => setQueryDraft(event.target.value)} />
          </div>
          <Select value={statusFilter} onChange={(event) => setQuery({ status: event.target.value || null })}>
            <option value="">Todo status</option>
            <option value="active">Ativo</option>
            <option value="inactive">Inativo</option>
            <option value="invalid">Inválido</option>
          </Select>
          <Select value={automationFilter} onChange={(event) => setQuery({ automation: event.target.value || null })}>
            <option value="">Toda automação</option>
            {automations.data?.map((automation) => (
              <option key={automation.id} value={automation.id}>
                {automation.name}
              </option>
            ))}
          </Select>
          <Select value={usageFilter} onChange={(event) => setQuery({ usage: event.target.value || null })}>
            <option value="">Uso</option>
            <option value="used">Com chamadas</option>
            <option value="unused">Sem chamadas</option>
          </Select>
          <Select value={resultFilter} onChange={(event) => setQuery({ result: event.target.value || null })}>
            <option value="">Resultado</option>
            <option value="success_like">Sucesso</option>
            <option value="failed_like">Falha</option>
            <option value="running_like">Em andamento</option>
            <option value="no_execution">Sem execução</option>
          </Select>
          <Select value={securityFilter} onChange={(event) => setQuery({ security: event.target.value || null })}>
            <option value="">Segurança</option>
            <option value="with_secret">Com secret</option>
            <option value="no_secret">Sem secret</option>
          </Select>
          <Input type="date" value={createdFilter} onChange={(event) => setQuery({ created: event.target.value || null })} aria-label="Criado em" />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {activeChips.map((chip) => (
            <button
              key={chip.label}
              type="button"
              onClick={() => setQuery(chip.patch)}
              className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground"
            >
              {chip.label}
              <span aria-hidden>×</span>
            </button>
          ))}
          {activeChips.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setQueryDraft("");
                setQuery({ q: null, status: null, automation: null, usage: null, result: null, created: null, security: null });
              }}
            >
              Limpar filtros
            </Button>
          )}
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Filter className="h-3.5 w-3.5" /> {filtered.length} de {httpsTriggers.length} webhooks HTTP
          </span>
        </div>
      </section>

      {triggers.loading || automations.loading ? (
        <div className="grid gap-3 xl:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-64 rounded-lg" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Webhook}
          title={httpsTriggers.length === 0 ? "Nenhum Webhook HTTP" : "Nenhum Webhook nos filtros"}
          description={httpsTriggers.length === 0 ? "Crie um endpoint autenticado para receber chamadas externas e iniciar automações." : "Ajuste busca e filtros para encontrar o endpoint."}
          action={
            httpsTriggers.length === 0 && canCreate ? (
              <Button onClick={openCreate}>
                <Plus className="h-4 w-4" /> Novo Webhook
              </Button>
            ) : undefined
          }
        />
      ) : (
        <WebhooksTable
          triggers={filtered}
          automations={automations.data ?? []}
          invokeBaseUrl={config.data?.invoke_base_url}
          onOpen={setDetails}
          onEdit={openEdit}
          onTest={(trigger) => (canTest ? setTesting(trigger) : toast({ title: "Sem permissão para testar", kind: "warning" }))}
          onRotate={rotate}
          onToggle={toggle}
          onDelete={remove}
        />
      )}

      <LegacyChainedTriggers triggers={legacyTriggers} automations={automations.data ?? []} onDisable={disableLegacy} onDelete={remove} />

      <WebhookForm
        open={formOpen}
        onClose={() => setFormOpen(false)}
        automations={automations.data ?? []}
        existing={triggers.data ?? []}
        editing={editing}
        submitting={submitting}
        invokeBaseUrl={config.data?.invoke_base_url}
        onSubmit={save}
      />
      <WebhookDetailsSheet
        trigger={details}
        automations={automations.data ?? []}
        invokeBaseUrl={config.data?.invoke_base_url}
        onClose={() => setDetails(null)}
        onEdit={openEdit}
        onRotate={rotate}
        onTest={(trigger) => (canTest ? setTesting(trigger) : toast({ title: "Sem permissão para testar", kind: "warning" }))}
      />
      <WebhookTestPanel trigger={testing} open={!!testing} onClose={() => setTesting(null)} />
      {secretDialog && <WebhookSecretDialog title={secretDialog.title} secret={secretDialog.secret} onClose={() => setSecretDialog(null)} />}
    </div>
  );
}

function MetricButton({
  icon: Icon,
  label,
  value,
  hint,
  onClick,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: number;
  hint: string;
  onClick: () => void;
}) {
  return (
    <button type="button" onClick={onClick} className="rounded-lg border border-border bg-card p-4 text-left shadow-sm transition-colors hover:bg-muted/50">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <p className="tabular mt-2 text-2xl font-semibold">{value}</p>
      <p className="mt-1 truncate text-xs text-muted-foreground">{hint}</p>
    </button>
  );
}

function Step({ number, title, text }: { number: string; title: string; text: string }) {
  return (
    <div className="rounded-md border border-border bg-muted/25 p-3">
      <div className="flex items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">{number}</span>
        <p className="text-sm font-medium">{title}</p>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">{text}</p>
    </div>
  );
}

function filterChips({
  query,
  statusFilter,
  automationFilter,
  usageFilter,
  resultFilter,
  createdFilter,
  securityFilter,
  automations,
}: {
  query: string;
  statusFilter: string;
  automationFilter: string;
  usageFilter: string;
  resultFilter: string;
  createdFilter: string;
  securityFilter: string;
  automations: Automation[];
}): Array<{ label: string; patch: StatFilter }> {
  const chips: Array<{ label: string; patch: StatFilter }> = [];
  if (query) chips.push({ label: `Busca: ${query}`, patch: { q: null } });
  if (statusFilter) chips.push({ label: `Status: ${webhookStatusMeta(statusFilter).label}`, patch: { status: null } });
  if (automationFilter) {
    const automationId = Number(automationFilter);
    const label = Number.isFinite(automationId) ? automationName(automations, automationId) : automationFilter;
    chips.push({ label: `Automação: ${label}`, patch: { automation: null } });
  }
  if (usageFilter) chips.push({ label: usageFilter === "used" ? "Com chamadas" : "Sem chamadas", patch: { usage: null } });
  if (resultFilter) chips.push({ label: `Resultado: ${resultLabel(resultFilter)}`, patch: { result: null } });
  if (securityFilter) chips.push({ label: securityFilter === "no_secret" ? "Sem secret" : "Com secret", patch: { security: null } });
  if (createdFilter) chips.push({ label: `Criado: ${createdFilter}`, patch: { created: null } });
  return chips;
}

function matchesResultFilter(trigger: Trigger, value: string): boolean {
  if (!RESULT_FILTERS.includes(value as (typeof RESULT_FILTERS)[number])) return false;
  if (value === "no_execution") return !trigger.last_execution_status;
  if (value === "success_like") return isSuccessResult(trigger.last_execution_status);
  if (value === "failed_like") return isFailureResult(trigger.last_execution_status);
  if (value === "running_like") return ["running", "preparing", "queued", "pending", "created", "ready"].includes(trigger.last_execution_status ?? "");
  return true;
}

function resultLabel(value: string): string {
  if (value === "success_like") return "Sucesso";
  if (value === "failed_like") return "Falha";
  if (value === "running_like") return "Em andamento";
  if (value === "no_execution") return "Sem execução";
  return value;
}

function isSuccessResult(status?: string | null): boolean {
  return ["success", "succeeded", "completed"].includes(status ?? "");
}

function isFailureResult(status?: string | null): boolean {
  return ["failed", "timed_out", "lost", "expired", "rejected"].includes(status ?? "");
}
