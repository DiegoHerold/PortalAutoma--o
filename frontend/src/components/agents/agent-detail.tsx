"use client";

import { useState } from "react";
import { Activity, Ban, Pause, Play, RefreshCw, Stethoscope, Wrench } from "lucide-react";

import { AgentConfigurationPanel } from "@/components/agents/agent-configuration-panel";
import { AgentCredentialsPanel } from "@/components/agents/agent-credentials-panel";
import { AdministrativeStatusBadge, ConnectivityBadge, HealthStatusBadge, OccupancyStatusBadge } from "@/components/agents/agent-status-badges";
import { DetailJson } from "@/components/shared/detail-json";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { SectionCard } from "@/components/shared/section-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import {
  disableAgent,
  drainAgent,
  enableAgent,
  requestAgentCapabilitiesRefresh,
  requestAgentDiagnostics,
  requestAgentUpdate,
  resumeAgent,
  setAgentMaintenance,
} from "@/lib/agent-api";
import { agentPoolLabel } from "@/lib/agent-policies";
import { formatDateTime, relativeFromNow } from "@/lib/utils";
import type { Agent, AgentCapability, AgentCapacity, AgentHistory } from "@/types/agent";

const TABS = [
  { value: "overview", label: "Visão geral" },
  { value: "capacity", label: "Capacidade" },
  { value: "capabilities", label: "Capacidades" },
  { value: "history", label: "Histórico" },
  { value: "config", label: "Configuração" },
  { value: "credentials", label: "Credenciais" },
];

type ActionKey = "enable" | "disable" | "drain" | "resume" | "maintenance" | "diagnostics" | "capabilities_refresh" | "update";

export function AgentDetail({ id }: { id: string }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [tab, setTab] = useState("overview");
  const [busy, setBusy] = useState<ActionKey | null>(null);
  const [desiredVersion, setDesiredVersion] = useState("");

  const agent = useApi<Agent>(`/agents/${id}`, { pollMs: 5000 });
  const capacity = useApi<AgentCapacity>(`/agents/${id}/capacity`, { pollMs: tab === "capacity" ? 5000 : undefined, enabled: tab === "capacity" || tab === "overview" });
  const capabilities = useApi<AgentCapability[]>(`/agents/${id}/capabilities`, { enabled: tab === "capabilities" });
  const history = useApi<AgentHistory>(`/agents/${id}/history`, { enabled: tab === "history" });

  if (agent.error) return <ErrorState message={agent.error} onRetry={agent.refetch} />;
  if (agent.loading || !agent.data) return <Skeleton className="h-64 rounded-lg" />;

  const a = agent.data;

  async function run(action: ActionKey, fn: () => Promise<unknown>, successTitle: string) {
    setBusy(action);
    try {
      await fn();
      toast({ title: successTitle, kind: "success" });
      await agent.refetch();
    } catch (err) {
      toast({ title: "Falha na ação", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setBusy(null);
    }
  }

  function requireToken(): string | null {
    if (!token) {
      toast({ title: "Sessão expirada", kind: "error" });
      return null;
    }
    return token;
  }

  async function handleDisable() {
    const t = requireToken();
    if (!t) return;
    if (!window.confirm(`Desabilitar o Agent "${a.name}"? Ele para de receber trabalho e é desconectado.`)) return;
    const reason = window.prompt("Motivo (opcional):") ?? undefined;
    await run("disable", () => disableAgent(t, id, reason || undefined), "Agent desabilitado");
  }

  async function handleDrain() {
    const t = requireToken();
    if (!t) return;
    if (!window.confirm(`Drenar o Agent "${a.name}"? Ele para de receber NOVO trabalho, mas continua as execuções em andamento.`)) return;
    await run("drain", () => drainAgent(t, id), "Agent em drenagem");
  }

  async function handleMaintenance(enable: boolean) {
    const t = requireToken();
    if (!t) return;
    const msg = enable
      ? `Colocar "${a.name}" em manutenção? Ele para de receber trabalho até sair da manutenção.`
      : `Tirar "${a.name}" de manutenção e voltar a habilitado?`;
    if (!window.confirm(msg)) return;
    await run("maintenance", () => setAgentMaintenance(t, id, enable), enable ? "Agent em manutenção" : "Manutenção encerrada");
  }

  async function handleUpdate() {
    const t = requireToken();
    if (!t || !desiredVersion.trim()) return;
    if (!window.confirm(`Pedir para "${a.name}" atualizar para a versão ${desiredVersion.trim()}? A atualização é um comando assíncrono — o Agent aplica quando processar.`)) return;
    await run("update", () => requestAgentUpdate(t, id, desiredVersion.trim()), "Atualização solicitada");
    setDesiredVersion("");
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <ConnectivityBadge status={a.connectivity_status} />
          <AdministrativeStatusBadge status={a.administrative_status} />
          {a.health_status !== "healthy" && <HealthStatusBadge status={a.health_status} />}
          <OccupancyStatusBadge status={a.occupancy_status} />
          {a.alerts.length > 0 && <Badge tone="warning">{a.alerts.join(", ")}</Badge>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {a.administrative_status === "disabled" ? (
            <Button size="sm" variant="secondary" disabled={!!busy} onClick={() => run("enable", () => enableAgent(token!, id), "Agent habilitado")}>
              {busy === "enable" ? <Spinner /> : <Play className="h-3.5 w-3.5" />} Habilitar
            </Button>
          ) : (
            <Button size="sm" variant="destructive" disabled={!!busy} onClick={handleDisable}>
              {busy === "disable" ? <Spinner /> : <Ban className="h-3.5 w-3.5" />} Desabilitar
            </Button>
          )}
          {a.administrative_status === "enabled" && (
            <Button size="sm" variant="outline" disabled={!!busy} onClick={handleDrain}>
              {busy === "drain" ? <Spinner /> : <Pause className="h-3.5 w-3.5" />} Drenar
            </Button>
          )}
          {(a.administrative_status === "draining" || a.administrative_status === "maintenance") && (
            <Button size="sm" variant="secondary" disabled={!!busy} onClick={() => run("resume", () => resumeAgent(token!, id), "Agent retomado")}>
              {busy === "resume" ? <Spinner /> : <Play className="h-3.5 w-3.5" />} Retomar
            </Button>
          )}
          {a.administrative_status === "maintenance" ? (
            <Button size="sm" variant="outline" disabled={!!busy} onClick={() => handleMaintenance(false)}>
              {busy === "maintenance" ? <Spinner /> : <Wrench className="h-3.5 w-3.5" />} Sair da manutenção
            </Button>
          ) : (
            a.administrative_status !== "disabled" && (
              <Button size="sm" variant="outline" disabled={!!busy} onClick={() => handleMaintenance(true)}>
                {busy === "maintenance" ? <Spinner /> : <Wrench className="h-3.5 w-3.5" />} Manutenção
              </Button>
            )
          )}
          <Button
            size="sm"
            variant="outline"
            disabled={!!busy}
            onClick={() => run("diagnostics", () => requestAgentDiagnostics(token!, id), "Diagnóstico solicitado")}
          >
            {busy === "diagnostics" ? <Spinner /> : <Stethoscope className="h-3.5 w-3.5" />} Diagnóstico
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!!busy}
            onClick={() => run("capabilities_refresh", () => requestAgentCapabilitiesRefresh(token!, id), "Atualização de capacidades solicitada")}
          >
            {busy === "capabilities_refresh" ? <Spinner /> : <RefreshCw className="h-3.5 w-3.5" />} Recarregar capacidades
          </Button>
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab} items={TABS} />

      {tab === "overview" && <OverviewTab agent={a} />}

      {tab === "capacity" && <CapacityTab capacity={capacity} />}

      {tab === "capabilities" && <CapabilitiesTab capabilities={capabilities} />}

      {tab === "history" && <HistoryTab history={history} />}

      {tab === "config" && <SectionCard title="Configuração"><AgentConfigurationPanel agentId={id} onSaved={agent.refetch} /></SectionCard>}

      {tab === "credentials" && <SectionCard title="Credenciais"><AgentCredentialsPanel agentId={id} /></SectionCard>}

      <SectionCard
        title="Solicitar atualização de versão"
        description={`Versão atual: ${a.current_version ?? "desconhecida"}${a.desired_version ? ` · desejada: ${a.desired_version}` : ""}`}
      >
        <div className="flex gap-2">
          <Input value={desiredVersion} onChange={(e) => setDesiredVersion(e.target.value)} placeholder="ex.: 1.4.2" className="tabular max-w-xs" />
          <Button variant="outline" disabled={!desiredVersion.trim() || !!busy} onClick={handleUpdate}>
            {busy === "update" ? <Spinner /> : <Activity className="h-3.5 w-3.5" />} Solicitar atualização
          </Button>
        </div>
      </SectionCard>
    </div>
  );
}

function OverviewTab({ agent }: { agent: Agent }) {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <SectionCard title="Informações">
          <div className="grid gap-4 sm:grid-cols-2">
            <Meta label="Hostname" value={<span className="tabular">{agent.hostname}</span>} />
            <Meta label="Agent ID" value={<span className="tabular text-xs">{agent.id}</span>} />
            <Meta label="Identidade local" value={<span className="tabular text-xs">{agent.local_identity ?? "—"}</span>} />
            <Meta label="Fingerprint" value={<span className="tabular text-xs">{agent.machine_fingerprint ?? "—"}</span>} />
            <Meta label="Versão atual" value={<span className="tabular">{agent.current_version ?? "—"}</span>} />
            <Meta label="Versão desejada" value={<span className="tabular">{agent.desired_version ?? "—"}</span>} />
            <Meta label="Protocolo" value={<span className="tabular">{agent.protocol_version ?? "—"}</span>} />
            <Meta label="Último heartbeat" value={<span className="tabular">{formatDateTime(agent.last_seen_at)}</span>} />
            <Meta label="Criado em" value={<span className="tabular">{formatDateTime(agent.created_at)}</span>} />
            <Meta label="Atualizado em" value={<span className="tabular">{formatDateTime(agent.updated_at)}</span>} />
          </div>
        </SectionCard>

        {agent.interactive_session && (
          <SectionCard title="Sessão interativa">
            <div className="grid gap-4 sm:grid-cols-2">
              <Meta label="Estado" value={agent.interactive_session.state} />
              <Meta label="Disponível" value={agent.interactive_session.available === null ? "—" : agent.interactive_session.available ? "Sim" : "Não"} />
              <Meta label="Bloqueada" value={agent.interactive_session.locked === null ? "—" : agent.interactive_session.locked ? "Sim" : "Não"} />
              <Meta label="Usuário" value={agent.interactive_session.user ?? "—"} />
            </div>
          </SectionCard>
        )}

        <SectionCard title="Dados brutos">
          <DetailJson data={agent} />
        </SectionCard>
      </div>

      <div className="space-y-6">
        <SectionCard title="Recursos">
          <div className="space-y-3 text-sm">
            <InfoRow label="CPU" value={agent.cpu_percentage != null ? `${agent.cpu_percentage.toFixed(1)}%` : "—"} />
            <InfoRow label="Memória" value={agent.memory_percentage != null ? `${agent.memory_percentage.toFixed(1)}%` : "—"} />
            <InfoRow label="Disco livre" value={agent.disk_free_mb != null ? `${(agent.disk_free_mb / 1024).toFixed(1)} GB` : "—"} />
          </div>
          <p className="mt-3 text-xs text-muted-foreground">Visto {relativeFromNow(agent.last_seen_at)}</p>
        </SectionCard>
      </div>
    </div>
  );
}

function CapacityTab({ capacity }: { capacity: ReturnType<typeof useApi<AgentCapacity>> }) {
  if (capacity.error) return <ErrorState message={capacity.error} onRetry={capacity.refetch} />;
  if (capacity.loading || !capacity.data) return <Skeleton className="h-48 rounded-lg" />;
  const { pools, latest_resource_snapshot } = capacity.data;
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        {pools.length === 0 ? (
          <EmptyState title="Sem pools reportados" description="O Agent ainda não enviou capacidade via heartbeat." />
        ) : (
          pools.map((pool) => {
            const pct = pool.effective_total > 0 ? Math.min(100, ((pool.used + pool.reserved) / pool.effective_total) * 100) : 0;
            return (
              <SectionCard key={pool.pool_type} title={agentPoolLabel(pool.pool_type)}>
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Uso</span>
                    <span className="tabular font-medium">
                      {pool.used + pool.reserved}/{pool.effective_total} ({pool.available} livres)
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div className={pct >= 100 ? "h-full rounded-full bg-destructive" : "h-full rounded-full bg-primary"} style={{ width: `${pct}%` }} />
                  </div>
                  <div className="grid gap-2 pt-2 text-xs text-muted-foreground sm:grid-cols-3">
                    <span>Recomendado pelo Agent: {pool.recommended_total ?? "—"}</span>
                    <span>Teto do administrador: {pool.administrator_total ?? "sem teto"}</span>
                    <span>Observado {relativeFromNow(pool.observed_at)}</span>
                  </div>
                </div>
              </SectionCard>
            );
          })
        )}
      </div>
      <div className="space-y-6">
        <SectionCard title="Último snapshot de recursos">
          {latest_resource_snapshot ? (
            <div className="space-y-3 text-sm">
              <InfoRow label="CPU" value={latest_resource_snapshot.cpu_usage_percentage != null ? `${latest_resource_snapshot.cpu_usage_percentage.toFixed(1)}%` : "—"} />
              <InfoRow
                label="Memória disponível"
                value={latest_resource_snapshot.memory_available_mb != null ? `${latest_resource_snapshot.memory_available_mb} MB` : "—"}
              />
              <InfoRow label="Disco livre" value={latest_resource_snapshot.disk_free_mb != null ? `${latest_resource_snapshot.disk_free_mb} MB` : "—"} />
              <InfoRow label="Processos" value={latest_resource_snapshot.process_count ?? "—"} />
              <InfoRow label="Observado" value={formatDateTime(latest_resource_snapshot.observed_at)} />
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Sem snapshot recente.</p>
          )}
        </SectionCard>
      </div>
    </div>
  );
}

function CapabilitiesTab({ capabilities }: { capabilities: ReturnType<typeof useApi<AgentCapability[]>> }) {
  if (capabilities.error) return <ErrorState message={capabilities.error} onRetry={capabilities.refetch} />;
  if (capabilities.loading) return <Skeleton className="h-40 rounded-lg" />;
  const items = capabilities.data ?? [];
  if (items.length === 0) return <EmptyState title="Sem capacidades reportadas" description="Peça um recarregamento de capacidades neste Agent." />;
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((cap) => (
        <div key={cap.id ?? cap.key} className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between gap-2">
            <p className="truncate font-medium">{cap.key}</p>
            <Badge tone={cap.status === "available" ? "success" : cap.status === "degraded" ? "warning" : cap.status === "unavailable" ? "destructive" : "neutral"}>
              {cap.status}
            </Badge>
          </div>
          {cap.version && <p className="tabular mt-1 text-xs text-muted-foreground">v{cap.version}</p>}
          <p className="mt-1 text-xs text-muted-foreground">Observado {relativeFromNow(cap.observed_at)}</p>
        </div>
      ))}
    </div>
  );
}

function HistoryTab({ history }: { history: ReturnType<typeof useApi<AgentHistory>> }) {
  if (history.error) return <ErrorState message={history.error} onRetry={history.refetch} />;
  if (history.loading || !history.data) return <Skeleton className="h-48 rounded-lg" />;
  const { instances, diagnostics } = history.data;
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <SectionCard title="Instâncias do processo" bodyClassName="space-y-2">
        {instances.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhuma instância registrada.</p>
        ) : (
          instances.map((instance) => (
            <div key={instance.id} className="rounded-md border border-border p-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="tabular text-xs text-muted-foreground">{instance.id}</span>
                <Badge tone={instance.disconnected_at ? "neutral" : "success"}>{instance.disconnected_at ? "encerrada" : "ativa"}</Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {instance.agent_version ? `versão ${instance.agent_version} · ` : ""}
                iniciada {formatDateTime(instance.process_started_at)}
              </p>
              {instance.shutdown_reason && <p className="mt-1 text-xs text-muted-foreground">Motivo: {instance.shutdown_reason}</p>}
            </div>
          ))
        )}
      </SectionCard>
      <SectionCard title="Diagnósticos" bodyClassName="space-y-2">
        {diagnostics.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhum diagnóstico solicitado ainda.</p>
        ) : (
          diagnostics.map((diag) => (
            <div key={diag.id} className="rounded-md border border-border p-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="tabular text-xs text-muted-foreground">{diag.id}</span>
                <Badge tone={diag.status === "completed" ? "success" : diag.status === "failed" ? "destructive" : "warning"}>{diag.status}</Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">Solicitado {formatDateTime(diag.requested_at)}</p>
              {diag.summary && <p className="mt-1 text-sm">{diag.summary}</p>}
              {diag.error && <p className="mt-1 text-xs text-destructive">{diag.error}</p>}
            </div>
          ))
        )}
      </SectionCard>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="mt-1 text-sm font-medium">{value}</div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}
