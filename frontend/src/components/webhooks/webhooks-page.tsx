"use client";

import { useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Plus, Search, Webhook } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LegacyChainedTriggers } from "@/components/webhooks/legacy-chained-triggers";
import { WebhookDetailsSheet } from "@/components/webhooks/webhook-details-sheet";
import { WebhookForm } from "@/components/webhooks/webhook-form";
import { WebhookSecretDialog } from "@/components/webhooks/webhook-secret-dialog";
import { WebhookTestPanel } from "@/components/webhooks/webhook-test-panel";
import { WebhooksTable } from "@/components/webhooks/webhooks-table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { hasAnyPermission, hasPermission } from "@/lib/permissions";
import type { Automation } from "@/types/automation";
import type { Trigger, TriggerConfig, TriggerCreateResult, TriggerRotateSecretResult } from "@/types/trigger";

import { automationName, triggerToPayload, webhookStatus, type WebhookPayload } from "./webhook-utils";

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

  const query = searchParams.get("q") ?? "";
  const statusFilter = searchParams.get("status") ?? "";
  const automationFilter = searchParams.get("automation") ?? "";
  const ownerFilter = searchParams.get("owner") ?? "";
  const invokedFilter = searchParams.get("invoked") ?? "";
  const resultFilter = searchParams.get("result") ?? "";
  const createdFilter = searchParams.get("created") ?? "";

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

  const httpsTriggers = (triggers.data ?? []).filter((trigger) => trigger.trigger_type === "https");
  const legacyTriggers = (triggers.data ?? []).filter((trigger) => trigger.trigger_type === "chained");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return httpsTriggers.filter((trigger) => {
      if (statusFilter && webhookStatus(trigger) !== statusFilter) return false;
      if (automationFilter && String(trigger.automation_id) !== automationFilter) return false;
      if (ownerFilter === "known") return false;
      if (invokedFilter === "yes" && !trigger.last_invoked_at) return false;
      if (invokedFilter === "no" && trigger.last_invoked_at) return false;
      if (resultFilter && trigger.last_execution_status !== resultFilter) return false;
      if (createdFilter && !String(trigger.created_at || "").startsWith(createdFilter)) return false;
      if (!q) return true;
      return (
        (trigger.name || "").toLowerCase().includes(q) ||
        trigger.route_path.toLowerCase().includes(q) ||
        automationName(automations.data, trigger.automation_id).toLowerCase().includes(q)
      );
    });
  }, [automationFilter, automations.data, createdFilter, httpsTriggers, invokedFilter, ownerFilter, query, resultFilter, statusFilter]);

  const lastStatuses = Array.from(new Set(httpsTriggers.map((trigger) => trigger.last_execution_status).filter(Boolean))) as string[];

  function openCreate() {
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(trigger: Trigger) {
    if (!canEdit) {
      toast({ title: "Sem permissao para editar", kind: "warning" });
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
        toast({ title: "Webhook criado", kind: "success" });
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
    if (!window.confirm(`Rotacionar o secret de "${trigger.name || trigger.route_path}"? O secret atual sera invalidado.`)) return;
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
    const related = trigger.last_execution_id ? "Ha historico de Execution relacionado; ele sera preservado." : "Nao ha ultima Execution registrada neste retorno.";
    if (!window.confirm(`Excluir "${label}"?\nDestino: ${target}\nRoute path: ${trigger.route_path}\n${related}`)) return;
    try {
      await apiRequest<void>(`/triggers/${trigger.id}`, { method: "DELETE", token });
      toast({ title: "Registro excluido", kind: "success" });
      if (details?.id === trigger.id) setDetails(null);
      await triggers.refetch();
    } catch (err) {
      toast({ title: "Falha ao excluir", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  if (!canRead) {
    return <ErrorState message="Seu usuario nao possui permissao para visualizar Webhooks." />;
  }

  if (triggers.error) return <ErrorState message={triggers.error} onRetry={triggers.refetch} />;

  return (
    <div className="space-y-5">
      <Card className="p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <h2 className="font-display text-base font-semibold">Webhooks HTTP de entrada</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Chamadas externas fazem POST na URL publica, autenticam por secret e criam Execucoes oficiais.
            </p>
          </div>
          <Button onClick={openCreate} disabled={!canCreate || automations.loading}>
            <Plus className="h-4 w-4" /> Novo Webhook
          </Button>
        </div>
      </Card>

      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card p-3">
        <div className="relative min-w-[220px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" placeholder="Buscar por nome, route path ou automacao" value={query} onChange={(event) => setQuery({ q: event.target.value })} />
        </div>
        <Select value={statusFilter} onChange={(event) => setQuery({ status: event.target.value || null })} className="w-36">
          <option value="">Todo status</option>
          <option value="active">Ativo</option>
          <option value="inactive">Inativo</option>
          <option value="invalid">Invalido</option>
        </Select>
        <Select value={automationFilter} onChange={(event) => setQuery({ automation: event.target.value || null })} className="w-56">
          <option value="">Toda automacao</option>
          {automations.data?.map((automation) => (
            <option key={automation.id} value={automation.id}>
              {automation.name}
            </option>
          ))}
        </Select>
        <Select value={ownerFilter} onChange={(event) => setQuery({ owner: event.target.value || null })} className="w-44">
          <option value="">Todo responsavel</option>
          <option value="unknown">Sem dado</option>
          <option value="known">Com dado</option>
        </Select>
        <Select value={invokedFilter} onChange={(event) => setQuery({ invoked: event.target.value || null })} className="w-44">
          <option value="">Com ou sem uso</option>
          <option value="yes">Possui invocacao</option>
          <option value="no">Sem invocacao</option>
        </Select>
        <Select value={resultFilter} onChange={(event) => setQuery({ result: event.target.value || null })} className="w-44">
          <option value="">Qualquer resultado</option>
          {lastStatuses.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </Select>
        <Input type="date" value={createdFilter} onChange={(event) => setQuery({ created: event.target.value || null })} className="w-40" />
      </div>

      {triggers.loading || automations.loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-20 rounded-lg" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Webhook}
          title={httpsTriggers.length === 0 ? "Nenhum Webhook HTTP" : "Nenhum Webhook nos filtros"}
          description={httpsTriggers.length === 0 ? "Crie um Webhook para receber chamadas externas e iniciar automacoes." : "Ajuste busca e filtros."}
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
          onTest={(trigger) => (canTest ? setTesting(trigger) : toast({ title: "Sem permissao para testar", kind: "warning" }))}
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
        onSubmit={save}
      />
      <WebhookDetailsSheet
        trigger={details}
        automations={automations.data ?? []}
        invokeBaseUrl={config.data?.invoke_base_url}
        onClose={() => setDetails(null)}
        onEdit={openEdit}
        onRotate={rotate}
      />
      <WebhookTestPanel trigger={testing} open={!!testing} onClose={() => setTesting(null)} />
      {secretDialog && <WebhookSecretDialog title={secretDialog.title} secret={secretDialog.secret} onClose={() => setSecretDialog(null)} />}
    </div>
  );
}
