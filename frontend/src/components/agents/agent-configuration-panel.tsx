"use client";

import { useState } from "react";
import { Info, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Field, Input, Label, Textarea } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { AGENT_CONFIG_FIELD_HELP, DEFAULT_AGENT_POOL_TYPES, agentPoolLabel } from "@/lib/agent-policies";
import { updateAgentConfiguration } from "@/lib/agent-api";
import { cn } from "@/lib/utils";
import type { AgentConfigurationPatch } from "@/types/agent";

type TimersState = { heartbeat_interval_seconds: number; stale_after_seconds: number; offline_after_seconds: number };
type PoolsState = { enabled_pools: string[]; administrator_pool_limits: Record<string, string> };
type RestrictionsState = { allowlist_capabilities: string; restrictions: string };

const DEFAULT_TIMERS: TimersState = { heartbeat_interval_seconds: 30, stale_after_seconds: 90, offline_after_seconds: 180 };
const DEFAULT_POOLS: PoolsState = {
  enabled_pools: [...DEFAULT_AGENT_POOL_TYPES],
  administrator_pool_limits: { interactive: "", background: "", browser: "" },
};
const DEFAULT_RESTRICTIONS: RestrictionsState = { allowlist_capabilities: "", restrictions: "{}" };

export function AgentConfigurationPanel({ agentId, onSaved }: { agentId: string; onSaved?: () => void | Promise<void> }) {
  const { token } = useAuth();
  const { toast } = useToast();

  const [timersTouched, setTimersTouched] = useState(false);
  const [timers, setTimers] = useState<TimersState>(DEFAULT_TIMERS);
  const [poolsTouched, setPoolsTouched] = useState(false);
  const [pools, setPools] = useState<PoolsState>(DEFAULT_POOLS);
  const [restrictionsTouched, setRestrictionsTouched] = useState(false);
  const [restrictionsForm, setRestrictionsForm] = useState<RestrictionsState>(DEFAULT_RESTRICTIONS);
  const [restrictionsError, setRestrictionsError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const timerError = timersTouched && timers.stale_after_seconds <= timers.heartbeat_interval_seconds
    ? "stale_after_seconds deve ser maior que heartbeat_interval_seconds."
    : timersTouched && timers.offline_after_seconds <= timers.stale_after_seconds
      ? "offline_after_seconds deve ser maior que stale_after_seconds."
      : null;

  function toggleEnabledPool(poolType: string) {
    setPoolsTouched(true);
    setPools((p) => ({
      ...p,
      enabled_pools: p.enabled_pools.includes(poolType) ? p.enabled_pools.filter((v) => v !== poolType) : [...p.enabled_pools, poolType],
    }));
  }

  async function save() {
    if (!token) return;
    if (!timersTouched && !poolsTouched && !restrictionsTouched) {
      toast({ title: "Nada para salvar", description: "Altere ao menos uma seção antes de salvar.", kind: "info" });
      return;
    }
    if (timerError) return;

    let restrictionsPayload: Record<string, unknown> | undefined;
    if (restrictionsTouched) {
      try {
        restrictionsPayload = restrictionsForm.restrictions.trim() ? JSON.parse(restrictionsForm.restrictions) : {};
        setRestrictionsError(null);
      } catch {
        setRestrictionsError("JSON inválido em restrictions.");
        return;
      }
    }

    const patch: AgentConfigurationPatch = {};
    if (timersTouched) {
      patch.heartbeat_interval_seconds = timers.heartbeat_interval_seconds;
      patch.stale_after_seconds = timers.stale_after_seconds;
      patch.offline_after_seconds = timers.offline_after_seconds;
    }
    if (poolsTouched) {
      patch.enabled_pools = pools.enabled_pools;
      patch.administrator_pool_limits = Object.fromEntries(
        Object.entries(pools.administrator_pool_limits).map(([pool, value]) => [pool, value.trim() ? Number(value) : null]),
      );
    }
    if (restrictionsTouched) {
      patch.allowlist_capabilities = restrictionsForm.allowlist_capabilities
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean);
      patch.restrictions = restrictionsPayload;
    }

    setSaving(true);
    try {
      await updateAgentConfiguration(token, agentId, patch);
      toast({ title: "Configuração enviada", description: "O Agent recebe a nova configuração no próximo comando/heartbeat.", kind: "success" });
      setTimersTouched(false);
      setPoolsTouched(false);
      setRestrictionsTouched(false);
      await onSaved?.();
    } catch (err) {
      toast({ title: "Falha ao salvar configuração", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-2 rounded-md border border-info/30 bg-info/5 p-3 text-xs text-muted-foreground">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-info" />
        <span>
          O backend não expõe uma leitura da configuração atual deste Agent (só há PATCH, sem GET) — os campos abaixo começam com os valores padrão do
          sistema. Só as seções marcadas como alteradas são enviadas; o resto continua com o que já está salvo no Agent.
        </span>
      </div>

      <ConfigSection title="Timers de presença" touched={timersTouched}>
        <div className="grid gap-4 sm:grid-cols-3">
          <TimerField
            id="cfg-heartbeat"
            label="Heartbeat (s)"
            help={AGENT_CONFIG_FIELD_HELP.heartbeat_interval_seconds}
            value={timers.heartbeat_interval_seconds}
            onChange={(v) => {
              setTimersTouched(true);
              setTimers((t) => ({ ...t, heartbeat_interval_seconds: v }));
            }}
          />
          <TimerField
            id="cfg-stale"
            label="Instável após (s)"
            help={AGENT_CONFIG_FIELD_HELP.stale_after_seconds}
            value={timers.stale_after_seconds}
            onChange={(v) => {
              setTimersTouched(true);
              setTimers((t) => ({ ...t, stale_after_seconds: v }));
            }}
          />
          <TimerField
            id="cfg-offline"
            label="Offline após (s)"
            help={AGENT_CONFIG_FIELD_HELP.offline_after_seconds}
            value={timers.offline_after_seconds}
            onChange={(v) => {
              setTimersTouched(true);
              setTimers((t) => ({ ...t, offline_after_seconds: v }));
            }}
          />
        </div>
        {timerError && <p className="text-xs text-destructive">{timerError}</p>}
      </ConfigSection>

      <ConfigSection title="Pools de capacidade" touched={poolsTouched}>
        <div className="space-y-3">
          <div>
            <Label>Pools habilitados</Label>
            <p className="mb-1.5 text-xs text-muted-foreground">{AGENT_CONFIG_FIELD_HELP.enabled_pools}</p>
            <div className="flex flex-wrap gap-1.5">
              {DEFAULT_AGENT_POOL_TYPES.map((poolType) => (
                <button
                  key={poolType}
                  type="button"
                  onClick={() => toggleEnabledPool(poolType)}
                  className={cn(
                    "rounded-md border px-3 py-1.5 text-xs font-medium transition-colors",
                    pools.enabled_pools.includes(poolType) ? "border-primary bg-primary/5 text-primary" : "border-input text-muted-foreground hover:border-primary/50",
                  )}
                >
                  {agentPoolLabel(poolType)}
                </button>
              ))}
            </div>
          </div>
          <div>
            <Label>Limite máximo por pool (em branco = sem teto do administrador)</Label>
            <p className="mb-1.5 text-xs text-muted-foreground">{AGENT_CONFIG_FIELD_HELP.administrator_pool_limits}</p>
            <div className="grid gap-3 sm:grid-cols-3">
              {DEFAULT_AGENT_POOL_TYPES.map((poolType) => (
                <Field key={poolType}>
                  <Label htmlFor={`cfg-limit-${poolType}`}>{agentPoolLabel(poolType)}</Label>
                  <Input
                    id={`cfg-limit-${poolType}`}
                    type="number"
                    min={0}
                    className="tabular"
                    value={pools.administrator_pool_limits[poolType] ?? ""}
                    onChange={(e) => {
                      setPoolsTouched(true);
                      setPools((p) => ({ ...p, administrator_pool_limits: { ...p.administrator_pool_limits, [poolType]: e.target.value } }));
                    }}
                  />
                </Field>
              ))}
            </div>
          </div>
        </div>
      </ConfigSection>

      <ConfigSection title="Restrições" touched={restrictionsTouched}>
        <Field>
          <Label htmlFor="cfg-allowlist">Capacidades permitidas (allowlist, separadas por vírgula)</Label>
          <p className="mb-1.5 text-xs text-muted-foreground">{AGENT_CONFIG_FIELD_HELP.allowlist_capabilities}</p>
          <Input
            id="cfg-allowlist"
            value={restrictionsForm.allowlist_capabilities}
            onChange={(e) => {
              setRestrictionsTouched(true);
              setRestrictionsForm((r) => ({ ...r, allowlist_capabilities: e.target.value }));
            }}
            placeholder="browser.chrome, python.selenium"
          />
        </Field>
        <Field>
          <Label htmlFor="cfg-restrictions">Restrições adicionais (JSON)</Label>
          <p className="mb-1.5 text-xs text-muted-foreground">{AGENT_CONFIG_FIELD_HELP.restrictions}</p>
          <Textarea
            id="cfg-restrictions"
            className="tabular font-mono"
            rows={4}
            value={restrictionsForm.restrictions}
            onChange={(e) => {
              setRestrictionsTouched(true);
              setRestrictionsForm((r) => ({ ...r, restrictions: e.target.value }));
            }}
          />
          {restrictionsError && <p className="text-xs text-destructive">{restrictionsError}</p>}
        </Field>
      </ConfigSection>

      <Button onClick={save} disabled={saving || !!timerError}>
        {saving ? <Spinner /> : <Save className="h-4 w-4" />} Salvar configuração
      </Button>
    </div>
  );
}

function ConfigSection({ title, touched, children }: { title: string; touched: boolean; children: React.ReactNode }) {
  return (
    <section className={cn("space-y-3 rounded-lg border p-4", touched ? "border-primary/40 bg-primary/5" : "border-border")}>
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
        {touched && <span className="text-xs font-medium text-primary">Será alterado</span>}
      </div>
      {children}
    </section>
  );
}

function TimerField({ id, label, help, value, onChange }: { id: string; label: string; help: string; value: number; onChange: (value: number) => void }) {
  return (
    <Field>
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type="number" min={1} className="tabular" value={value} onChange={(e) => onChange(Number(e.target.value))} />
      <p className="text-xs text-muted-foreground">{help}</p>
    </Field>
  );
}
