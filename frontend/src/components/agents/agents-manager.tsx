"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, Copy, Cpu, KeyRound, Search, Server } from "lucide-react";

import { AgentStatusRow } from "@/components/agents/agent-status-badges";
import { RegistrationTokensSheet } from "@/components/agents/registration-tokens-sheet";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { agentPoolLabel } from "@/lib/agent-policies";
import { relativeFromNow } from "@/lib/utils";
import type { Agent } from "@/types/agent";

type InstallerConfig = { central_api_url: string; central_websocket_url: string };

const POLL = 5000;

export function AgentsManager() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { toast } = useToast();

  const agents = useApi<Agent[]>("/agents", { pollMs: POLL });
  const installer = useApi<InstallerConfig>("/workers/installer-config");
  const [tokensOpen, setTokensOpen] = useState(false);

  const query = searchParams.get("q") ?? "";
  const connectivity = searchParams.get("connectivity") ?? "";
  const adminStatus = searchParams.get("admin") ?? "";

  function setQuery(patch: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(patch).forEach(([key, value]) => {
      if (!value) params.delete(key);
      else params.set(key, value);
    });
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (agents.data ?? []).filter((agent) => {
      if (connectivity && agent.connectivity_status !== connectivity) return false;
      if (adminStatus && agent.administrative_status !== adminStatus) return false;
      if (!q) return true;
      return agent.name.toLowerCase().includes(q) || agent.hostname.toLowerCase().includes(q) || agent.id.toLowerCase().includes(q);
    });
  }, [agents.data, query, connectivity, adminStatus]);

  if (agents.error) return <ErrorState message={agents.error} onRetry={agents.refetch} />;

  const centralApiUrl = installer.data?.central_api_url ?? "";
  const centralWebSocketUrl = installer.data?.central_websocket_url ?? "";
  const installerConfig = JSON.stringify(
    {
      agent_name: "",
      central_api_url: centralApiUrl,
      central_websocket_url: centralWebSocketUrl,
      console_port: 8765,
      heartbeat_seconds: 30,
      interactive_slots: 1,
      background_slots: 2,
      update_channel: "stable",
    },
    null,
    2,
  );

  async function copyInstallerConfig() {
    await navigator.clipboard.writeText(installerConfig);
    toast({ title: "Configuração copiada", kind: "success" });
  }

  return (
    <div className="space-y-5">
      <Card className="p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <h2 className="font-display text-base font-semibold">Configuração do instalador</h2>
            <div className="mt-2 grid gap-1 text-xs text-muted-foreground">
              {installer.loading ? (
                <span>Carregando...</span>
              ) : (
                <>
                  <span className="tabular truncate">central_api_url: {centralApiUrl}</span>
                  <span className="tabular truncate">central_websocket_url: {centralWebSocketUrl}</span>
                </>
              )}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={copyInstallerConfig} disabled={installer.loading}>
              <Copy className="h-4 w-4" /> Copiar JSON
            </Button>
            <Button onClick={() => setTokensOpen(true)}>
              <KeyRound className="h-4 w-4" /> Tokens de registro
            </Button>
          </div>
        </div>
      </Card>

      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card p-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" placeholder="Buscar por nome, hostname ou id" value={query} onChange={(e) => setQuery({ q: e.target.value })} />
        </div>
        <Select value={connectivity} onChange={(e) => setQuery({ connectivity: e.target.value || null })} className="w-44">
          <option value="">Toda conectividade</option>
          <option value="online">online</option>
          <option value="connecting">connecting</option>
          <option value="stale">stale</option>
          <option value="disconnected">disconnected</option>
          <option value="offline">offline</option>
        </Select>
        <Select value={adminStatus} onChange={(e) => setQuery({ admin: e.target.value || null })} className="w-48">
          <option value="">Todo status administrativo</option>
          <option value="enabled">enabled</option>
          <option value="draining">draining</option>
          <option value="maintenance">maintenance</option>
          <option value="updating">updating</option>
          <option value="disabled">disabled</option>
          <option value="pending_registration">pending_registration</option>
        </Select>
      </div>

      {agents.loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-48 rounded-lg" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Server}
          title="Nenhum Agent encontrado"
          description={(agents.data ?? []).length === 0 ? "Nenhum Agent registrado ainda — gere um token de registro para conectar um novo Agent." : "Ajuste os filtros de busca."}
          action={
            (agents.data ?? []).length === 0 ? (
              <Button onClick={() => setTokensOpen(true)}>
                <KeyRound className="h-4 w-4" /> Gerar token de registro
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((agent) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      )}

      <RegistrationTokensSheet open={tokensOpen} onClose={() => setTokensOpen(false)} />
    </div>
  );
}

function AgentCard({ agent }: { agent: Agent }) {
  const poolEntries = Object.entries(agent.pools);
  return (
    <Card className="h-full p-5 transition-colors hover:border-primary/40">
      <div className="flex items-start justify-between gap-3">
        <Link href={`/workers/${agent.id}`} className="min-w-0">
          <h3 className="truncate font-display text-base font-semibold hover:text-primary">{agent.name}</h3>
          <p className="tabular mt-0.5 truncate text-xs text-muted-foreground">{agent.hostname}</p>
          <p className="tabular mt-0.5 truncate text-xs text-muted-foreground">{agent.id}</p>
        </Link>
      </div>

      <AgentStatusRow agent={agent} className="mt-3" />

      {agent.alerts.length > 0 && (
        <div className="mt-3 flex items-start gap-1.5 rounded-md bg-warning/10 px-2 py-1.5 text-xs text-warning">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span className="truncate">{agent.alerts.join(", ")}</span>
        </div>
      )}

      {poolEntries.length > 0 && (
        <div className="mt-4 space-y-2">
          {poolEntries.map(([poolType, pool]) => {
            const pct = pool.effective_total > 0 ? Math.min(100, ((pool.used + pool.reserved) / pool.effective_total) * 100) : 0;
            return (
              <div key={poolType} className="space-y-1">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5">
                    <Cpu className="h-3.5 w-3.5" /> {agentPoolLabel(poolType)}
                  </span>
                  <span className="tabular font-medium text-foreground">
                    {pool.used + pool.reserved}/{pool.effective_total}
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <div className={pct >= 100 ? "h-full rounded-full bg-destructive" : "h-full rounded-full bg-primary"} style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="mt-4 text-xs text-muted-foreground">Visto {relativeFromNow(agent.last_seen_at)}</div>
      {agent.current_version && (
        <div className="tabular mt-1 text-xs text-muted-foreground">
          Agent {agent.current_version}
          {agent.desired_version && agent.desired_version !== agent.current_version ? ` → ${agent.desired_version}` : ""}
        </div>
      )}
    </Card>
  );
}
