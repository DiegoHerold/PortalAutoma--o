"use client";

import { useMemo, useState } from "react";
import { Webhook, Plus, Copy, Check, Eye, EyeOff } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Select, Label, Field } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type { Trigger } from "@/types/trigger";
import type { Automation } from "@/types/automation";

export function TriggersManager() {
  const { token } = useAuth();
  const { toast } = useToast();
  const triggers = useApi<Trigger[]>("/triggers");
  const automations = useApi<Automation[]>("/automations");
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({ automation_id: "", trigger_type: "https", route_path: "", secret_token: "" });

  const nameOf = useMemo(() => {
    const map = new Map<number, string>();
    automations.data?.forEach((a) => map.set(a.id, a.name));
    return map;
  }, [automations.data]);

  async function create() {
    if (!token || !form.automation_id) return;
    setSubmitting(true);
    try {
      await apiRequest<Trigger>("/triggers", {
        method: "POST",
        token,
        body: JSON.stringify({ ...form, automation_id: Number(form.automation_id) }),
      });
      toast({ title: "Gatilho criado", kind: "success" });
      setForm({ automation_id: "", trigger_type: "https", route_path: "", secret_token: "" });
      setOpen(false);
      await triggers.refetch();
    } catch (err) {
      toast({ title: "Falha ao criar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <Button onClick={() => setOpen(true)}>
          <Plus className="h-4 w-4" /> Novo gatilho
        </Button>
      </div>

      {triggers.error ? (
        <ErrorState message={triggers.error} onRetry={triggers.refetch} />
      ) : triggers.loading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-36 rounded-lg" />
          ))}
        </div>
      ) : (triggers.data ?? []).length === 0 ? (
        <EmptyState icon={Webhook} title="Sem gatilhos" description="Crie um gatilho para disparar automações externamente." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {triggers.data!.map((t) => (
            <TriggerCard key={t.id} trigger={t} automationName={nameOf.get(t.automation_id)} />
          ))}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Novo gatilho"
        description="Gatilho HTTP para disparo externo (ex.: POST vindo do n8n)."
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={create} disabled={submitting || !form.automation_id || !form.route_path}>
              {submitting && <Spinner />} Criar
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field>
            <Label htmlFor="t-automation">Automação</Label>
            <Select id="t-automation" value={form.automation_id} onChange={(e) => setForm({ ...form, automation_id: e.target.value })}>
              <option value="">Selecione…</option>
              {automations.data?.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field>
            <Label htmlFor="t-type">Tipo</Label>
            <Select id="t-type" value={form.trigger_type} onChange={(e) => setForm({ ...form, trigger_type: e.target.value })}>
              <option value="https">HTTPS (webhook)</option>
              <option value="n8n">n8n</option>
            </Select>
          </Field>
          <Field>
            <Label htmlFor="t-route">Rota</Label>
            <Input id="t-route" className="tabular" placeholder="/webhooks/minha-automacao" value={form.route_path} onChange={(e) => setForm({ ...form, route_path: e.target.value })} />
          </Field>
          <Field>
            <Label htmlFor="t-secret">Token secreto</Label>
            <Input id="t-secret" className="tabular" value={form.secret_token} onChange={(e) => setForm({ ...form, secret_token: e.target.value })} />
          </Field>
        </div>
      </Modal>
    </div>
  );
}

function TriggerCard({ trigger, automationName }: { trigger: Trigger; automationName?: string }) {
  const [copied, setCopied] = useState(false);
  const [reveal, setReveal] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(trigger.route_path);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }

  const masked = trigger.secret_token ? `${trigger.secret_token.slice(0, 3)}••••••••` : "—";

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between gap-2">
        <Badge tone="info">{trigger.trigger_type}</Badge>
        <Badge tone={trigger.is_active ? "success" : "neutral"}>{trigger.is_active ? "Ativo" : "Inativo"}</Badge>
      </div>
      <p className="mt-3 text-sm font-medium">{automationName ?? `Automação #${trigger.automation_id}`}</p>
      <div className="mt-2 flex items-center gap-2 rounded-md border border-border bg-muted/40 px-2.5 py-1.5">
        <code className="tabular flex-1 truncate text-xs">{trigger.route_path}</code>
        <button onClick={copy} className="text-muted-foreground hover:text-foreground" title="Copiar rota">
          {copied ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}
        </button>
      </div>
      <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
        <span className="tabular">Token: {reveal ? trigger.secret_token : masked}</span>
        <button onClick={() => setReveal((r) => !r)} className="hover:text-foreground">
          {reveal ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
        </button>
      </div>
    </Card>
  );
}
