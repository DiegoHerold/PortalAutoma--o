"use client";

import { useMemo, useState } from "react";
import {
  Check,
  Copy,
  Eye,
  EyeOff,
  FlaskConical,
  GitBranch,
  Pencil,
  Plus,
  Trash2,
  Webhook,
} from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Select, Label, Field, Textarea } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { API_BASE_URL } from "@/lib/constants";
import type { Automation } from "@/types/automation";
import type { Trigger, TriggerCondition, TriggerDryRunResult } from "@/types/trigger";

type TriggerType = "https" | "chained";
type MappingRow = { key: string; path: string };

type TriggerFormState = {
  automation_id: string;
  trigger_type: TriggerType;
  route_path: string;
  secret_token: string;
  is_active: boolean;
  mapping: MappingRow[];
  source_automation_id: string;
  condition: TriggerCondition;
};

function generateSecret(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID().replace(/-/g, "");
  return Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
}

function mappingToRows(mapping: Record<string, string> | null): MappingRow[] {
  if (!mapping) return [];
  return Object.entries(mapping).map(([key, path]) => ({ key, path }));
}

function rowsToMapping(rows: MappingRow[]): Record<string, string> | null {
  const entries = rows.filter((r) => r.key.trim() && r.path.trim()).map((r) => [r.key.trim(), r.path.trim()]);
  return entries.length ? Object.fromEntries(entries) : null;
}

function emptyForm(automationId?: string): TriggerFormState {
  return {
    automation_id: automationId ?? "",
    trigger_type: "https",
    route_path: "",
    secret_token: generateSecret(),
    is_active: true,
    mapping: [],
    source_automation_id: "",
    condition: "success",
  };
}

function triggerToForm(trigger: Trigger): TriggerFormState {
  return {
    automation_id: String(trigger.automation_id),
    trigger_type: trigger.trigger_type === "chained" ? "chained" : "https",
    route_path: trigger.route_path,
    secret_token: trigger.secret_token,
    is_active: trigger.is_active,
    mapping: mappingToRows(trigger.parameter_mapping_json),
    source_automation_id: trigger.source_automation_id ? String(trigger.source_automation_id) : "",
    condition: trigger.condition ?? "success",
  };
}

const CONDITION_LABELS: Record<TriggerCondition, string> = {
  success: "Quando terminar com sucesso",
  failed: "Quando falhar",
  always: "Sempre (sucesso, falha ou cancelado)",
};

export function TriggersManager() {
  const { token } = useAuth();
  const { toast } = useToast();
  const triggers = useApi<Trigger[]>("/triggers");
  const automations = useApi<Automation[]>("/automations");
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [editing, setEditing] = useState<Trigger | null>(null);
  const [form, setForm] = useState<TriggerFormState>(emptyForm());
  const [testTrigger, setTestTrigger] = useState<Trigger | null>(null);

  const nameOf = useMemo(() => {
    const map = new Map<number, string>();
    automations.data?.forEach((a) => map.set(a.id, a.name));
    return map;
  }, [automations.data]);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm(automations.data?.[0] ? String(automations.data[0].id) : ""));
    setOpen(true);
  }

  function openEdit(trigger: Trigger) {
    setEditing(trigger);
    setForm(triggerToForm(trigger));
    setOpen(true);
  }

  function setMappingRow(index: number, field: keyof MappingRow, value: string) {
    setForm((f) => {
      const mapping = [...f.mapping];
      mapping[index] = { ...mapping[index], [field]: value };
      return { ...f, mapping };
    });
  }

  function addMappingRow() {
    setForm((f) => ({ ...f, mapping: [...f.mapping, { key: "", path: "" }] }));
  }

  function removeMappingRow(index: number) {
    setForm((f) => ({ ...f, mapping: f.mapping.filter((_, i) => i !== index) }));
  }

  async function save() {
    if (!token || !form.automation_id) return;
    if (form.trigger_type === "chained" && !form.source_automation_id) return;
    setSubmitting(true);
    try {
      const body =
        form.trigger_type === "chained"
          ? {
              automation_id: Number(form.automation_id),
              trigger_type: "chained",
              is_active: form.is_active,
              source_automation_id: Number(form.source_automation_id),
              condition: form.condition,
              parameter_mapping_json: rowsToMapping(form.mapping),
            }
          : {
              automation_id: Number(form.automation_id),
              trigger_type: "https",
              route_path: form.route_path,
              secret_token: form.secret_token,
              is_active: form.is_active,
              parameter_mapping_json: rowsToMapping(form.mapping),
            };
      await apiRequest<Trigger>(editing ? `/triggers/${editing.id}` : "/triggers", {
        method: editing ? "PUT" : "POST",
        token,
        body: JSON.stringify(body),
      });
      toast({ title: editing ? "Gatilho atualizado" : "Gatilho criado", kind: "success" });
      setEditing(null);
      setOpen(false);
      await triggers.refetch();
    } catch (err) {
      toast({ title: "Falha ao salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(trigger: Trigger) {
    if (!token) return;
    const label = trigger.trigger_type === "chained" ? "este encadeamento" : `o gatilho "${trigger.route_path}"`;
    if (!window.confirm(`Apagar ${label}?`)) return;
    try {
      await apiRequest<void>(`/triggers/${trigger.id}`, { method: "DELETE", token });
      toast({ title: "Gatilho apagado", kind: "success" });
      await triggers.refetch();
    } catch (err) {
      toast({ title: "Falha ao apagar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  const httpsTriggers = (triggers.data ?? []).filter((t) => t.trigger_type !== "chained");
  const chainedTriggers = (triggers.data ?? []).filter((t) => t.trigger_type === "chained");

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-2 rounded-md border border-info/30 bg-info/5 p-3 text-xs text-muted-foreground">
        <Webhook className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <p>
          Use um gatilho de webhook para receber chamadas do N8N (ou qualquer sistema externo) e disparar uma automação daqui.
          Use um encadeamento para disparar uma automação automaticamente quando outra terminar -- sem precisar de N8N no meio.
        </p>
      </div>

      <div className="flex justify-end">
        <Button onClick={openCreate}>
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
        <EmptyState icon={Webhook} title="Sem gatilhos" description="Crie um gatilho de webhook ou um encadeamento entre automações." />
      ) : (
        <div className="space-y-6">
          {httpsTriggers.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Webhooks</h3>
              <div className="grid gap-4 md:grid-cols-2">
                {httpsTriggers.map((t) => (
                  <WebhookTriggerCard
                    key={t.id}
                    trigger={t}
                    automationName={nameOf.get(t.automation_id)}
                    onEdit={openEdit}
                    onDelete={remove}
                    onTest={setTestTrigger}
                  />
                ))}
              </div>
            </div>
          )}

          {chainedTriggers.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Encadeamentos</h3>
              <div className="grid gap-4 md:grid-cols-2">
                {chainedTriggers.map((t) => (
                  <ChainedTriggerCard
                    key={t.id}
                    trigger={t}
                    automationName={nameOf.get(t.automation_id)}
                    sourceName={t.source_automation_id ? nameOf.get(t.source_automation_id) : undefined}
                    onEdit={openEdit}
                    onDelete={remove}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? "Editar gatilho" : "Novo gatilho"}
        className="max-w-xl"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button
              onClick={save}
              disabled={
                submitting ||
                !form.automation_id ||
                (form.trigger_type === "https" && (!form.route_path || !form.secret_token)) ||
                (form.trigger_type === "chained" && !form.source_automation_id)
              }
            >
              {submitting && <Spinner />} {editing ? "Salvar" : "Criar"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setForm({ ...form, trigger_type: "https" })}
              className={`rounded-md border p-3 text-left text-sm transition-colors ${
                form.trigger_type === "https" ? "border-primary bg-primary/5" : "border-input hover:border-primary/50"
              }`}
            >
              <p className="flex items-center gap-1.5 font-medium">
                <Webhook className="h-4 w-4" /> Webhook
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">Disparado por um POST externo (N8N, etc).</p>
            </button>
            <button
              type="button"
              onClick={() => setForm({ ...form, trigger_type: "chained" })}
              className={`rounded-md border p-3 text-left text-sm transition-colors ${
                form.trigger_type === "chained" ? "border-primary bg-primary/5" : "border-input hover:border-primary/50"
              }`}
            >
              <p className="flex items-center gap-1.5 font-medium">
                <GitBranch className="h-4 w-4" /> Encadeamento
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">Disparado quando outra automação terminar.</p>
            </button>
          </div>

          {form.trigger_type === "chained" ? (
            <Field>
              <Label htmlFor="t-source">Automação de origem</Label>
              <Select
                id="t-source"
                value={form.source_automation_id}
                onChange={(e) => setForm({ ...form, source_automation_id: e.target.value })}
              >
                <option value="">Selecione...</option>
                {automations.data
                  ?.filter((a) => String(a.id) !== form.automation_id)
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
              </Select>
              <p className="text-xs text-muted-foreground">Quando esta automação terminar, o gatilho pode disparar a de baixo.</p>
            </Field>
          ) : null}

          <Field>
            <Label htmlFor="t-automation">{form.trigger_type === "chained" ? "Automação a disparar" : "Automação"}</Label>
            <Select id="t-automation" value={form.automation_id} onChange={(e) => setForm({ ...form, automation_id: e.target.value })}>
              <option value="">Selecione...</option>
              {automations.data
                ?.filter((a) => String(a.id) !== form.source_automation_id || form.trigger_type !== "chained")
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
            </Select>
          </Field>

          {form.trigger_type === "chained" && (
            <Field>
              <Label htmlFor="t-condition">Condição</Label>
              <Select
                id="t-condition"
                value={form.condition}
                onChange={(e) => setForm({ ...form, condition: e.target.value as TriggerCondition })}
              >
                {(Object.keys(CONDITION_LABELS) as TriggerCondition[]).map((c) => (
                  <option key={c} value={c}>
                    {CONDITION_LABELS[c]}
                  </option>
                ))}
              </Select>
            </Field>
          )}

          {form.trigger_type === "https" && (
            <>
              <Field>
                <Label htmlFor="t-route">Rota</Label>
                <Input
                  id="t-route"
                  className="tabular"
                  placeholder="minha-automacao"
                  value={form.route_path}
                  onChange={(e) => setForm({ ...form, route_path: e.target.value })}
                />
                <p className="text-xs text-muted-foreground truncate">
                  URL: {API_BASE_URL}/webhooks/trigger/{form.route_path || "..."}
                </p>
              </Field>
              <Field>
                <Label htmlFor="t-secret">Token secreto (enviar no header X-Webhook-Secret)</Label>
                <div className="flex gap-2">
                  <Input
                    id="t-secret"
                    className="tabular flex-1"
                    value={form.secret_token}
                    onChange={(e) => setForm({ ...form, secret_token: e.target.value })}
                  />
                  <Button type="button" variant="outline" onClick={() => setForm({ ...form, secret_token: generateSecret() })}>
                    Gerar
                  </Button>
                </div>
              </Field>
            </>
          )}

          <Field>
            <div className="flex items-center justify-between">
              <Label>Mapeamento de parâmetros (opcional)</Label>
              <Button type="button" size="sm" variant="outline" onClick={addMappingRow}>
                <Plus className="h-3.5 w-3.5" /> Adicionar
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Deixe vazio para a automação receber o payload bruto. Caminho ex.: <code className="tabular">body.empresa.cnpj</code>,{" "}
              <code className="tabular">headers.x-origem</code>.
            </p>
            {form.mapping.length > 0 && (
              <div className="space-y-2">
                {form.mapping.map((row, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Input
                      className="tabular flex-1"
                      placeholder="parametro"
                      value={row.key}
                      onChange={(e) => setMappingRow(i, "key", e.target.value)}
                    />
                    <span className="text-xs text-muted-foreground">=</span>
                    <Input
                      className="tabular flex-1"
                      placeholder="body.caminho.para.valor"
                      value={row.path}
                      onChange={(e) => setMappingRow(i, "path", e.target.value)}
                    />
                    <Button type="button" size="icon" variant="ghost" onClick={() => removeMappingRow(i)}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </Field>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              className="h-4 w-4 accent-primary"
            />
            Ativo
          </label>

          {editing && (
            <Button variant="destructive" size="sm" onClick={() => remove(editing)}>
              <Trash2 className="h-3.5 w-3.5" /> Apagar gatilho
            </Button>
          )}
        </div>
      </Modal>

      {testTrigger && <TestTriggerModal trigger={testTrigger} onClose={() => setTestTrigger(null)} />}
    </div>
  );
}

function WebhookTriggerCard({
  trigger,
  automationName,
  onEdit,
  onDelete,
  onTest,
}: {
  trigger: Trigger;
  automationName?: string;
  onEdit: (trigger: Trigger) => void;
  onDelete: (trigger: Trigger) => void;
  onTest: (trigger: Trigger) => void;
}) {
  const [copied, setCopied] = useState(false);
  const [reveal, setReveal] = useState(false);
  const fullUrl = `${API_BASE_URL}/webhooks/trigger/${trigger.route_path}`;
  const mappingCount = trigger.parameter_mapping_json ? Object.keys(trigger.parameter_mapping_json).length : 0;

  async function copy() {
    try {
      await navigator.clipboard.writeText(fullUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }

  const masked = trigger.secret_token ? `${trigger.secret_token.slice(0, 3)}********` : "-";

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between gap-2">
        <Badge tone="info">
          <Webhook className="h-3 w-3" /> webhook
        </Badge>
        <div className="flex items-center gap-1">
          <Badge tone={trigger.is_active ? "success" : "neutral"}>{trigger.is_active ? "Ativo" : "Inativo"}</Badge>
          <Button size="icon" variant="ghost" onClick={() => onTest(trigger)} title="Testar mapeamento">
            <FlaskConical className="h-4 w-4" />
          </Button>
          <Button size="icon" variant="ghost" onClick={() => onEdit(trigger)} title="Editar gatilho">
            <Pencil className="h-4 w-4" />
          </Button>
          <Button size="icon" variant="ghost" onClick={() => onDelete(trigger)} title="Apagar gatilho">
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <p className="mt-3 text-sm font-medium">{automationName ?? `Automacao #${trigger.automation_id}`}</p>
      <div className="mt-2 flex items-center gap-2 rounded-md border border-border bg-muted/40 px-2.5 py-1.5">
        <code className="tabular flex-1 truncate text-xs">{fullUrl}</code>
        <button onClick={copy} className="text-muted-foreground hover:text-foreground" title="Copiar URL">
          {copied ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}
        </button>
      </div>
      <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="tabular">Header X-Webhook-Secret: {reveal ? trigger.secret_token : masked}</span>
          <button onClick={() => setReveal((r) => !r)} className="hover:text-foreground">
            {reveal ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
          </button>
        </span>
        <span>{mappingCount > 0 ? `${mappingCount} parâmetro(s) mapeado(s)` : "payload bruto"}</span>
      </div>
    </Card>
  );
}

function ChainedTriggerCard({
  trigger,
  automationName,
  sourceName,
  onEdit,
  onDelete,
}: {
  trigger: Trigger;
  automationName?: string;
  sourceName?: string;
  onEdit: (trigger: Trigger) => void;
  onDelete: (trigger: Trigger) => void;
}) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between gap-2">
        <Badge tone="primary">
          <GitBranch className="h-3 w-3" /> encadeamento
        </Badge>
        <div className="flex items-center gap-1">
          <Badge tone={trigger.is_active ? "success" : "neutral"}>{trigger.is_active ? "Ativo" : "Inativo"}</Badge>
          <Button size="icon" variant="ghost" onClick={() => onEdit(trigger)} title="Editar encadeamento">
            <Pencil className="h-4 w-4" />
          </Button>
          <Button size="icon" variant="ghost" onClick={() => onDelete(trigger)} title="Apagar encadeamento">
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="mt-3 flex items-center gap-2 text-sm">
        <span className="truncate font-medium">{sourceName ?? `Automacao #${trigger.source_automation_id}`}</span>
        <span className="text-muted-foreground">→</span>
        <span className="truncate font-medium">{automationName ?? `Automacao #${trigger.automation_id}`}</span>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">{trigger.condition ? CONDITION_LABELS[trigger.condition] : "—"}</p>
    </Card>
  );
}

function TestTriggerModal({ trigger, onClose }: { trigger: Trigger; onClose: () => void }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [samplePayload, setSamplePayload] = useState('{\n  "exemplo": "valor"\n}');
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<TriggerDryRunResult | null>(null);

  async function run() {
    if (!token) return;
    let parsed: unknown;
    try {
      parsed = samplePayload.trim() ? JSON.parse(samplePayload) : {};
    } catch {
      toast({ title: "JSON inválido no payload de exemplo", kind: "error" });
      return;
    }
    setTesting(true);
    setResult(null);
    try {
      const res = await apiRequest<TriggerDryRunResult>(`/triggers/${trigger.id}/test`, {
        method: "POST",
        token,
        body: JSON.stringify({ sample_payload: parsed, sample_headers: {}, sample_query_params: {} }),
      });
      setResult(res);
    } catch (err) {
      toast({ title: "Falha no teste", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setTesting(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Testar mapeamento"
      description="Simula um payload de webhook e mostra os parâmetros que a automação receberia -- não dispara nada de verdade."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Fechar
          </Button>
          <Button onClick={run} disabled={testing}>
            {testing && <Spinner />} Testar
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field>
          <Label htmlFor="sample-payload">Payload de exemplo (JSON)</Label>
          <Textarea
            id="sample-payload"
            className="tabular min-h-[140px]"
            value={samplePayload}
            onChange={(e) => setSamplePayload(e.target.value)}
          />
        </Field>
        {result && (
          <Field>
            <Label>Parâmetros resultantes</Label>
            <pre className="tabular max-h-56 overflow-auto rounded-md border border-border bg-muted/40 p-3 text-xs">
              {JSON.stringify(result.parameters, null, 2)}
            </pre>
          </Field>
        )}
      </div>
    </Modal>
  );
}
