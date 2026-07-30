"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { CalendarClock, Check, Copy, GitBranch, RotateCw, Server, Webhook } from "lucide-react";

import { AutomationVersionsPanel } from "@/components/automations/automation-versions-panel";
import { WorkerPreferences } from "@/components/automations/worker-preferences";
import { DetailJson } from "@/components/shared/detail-json";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { SectionCard } from "@/components/shared/section-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PriorityBadge } from "@/components/ui/status-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { describeRecurrence } from "@/lib/cron";
import { executorLabel } from "@/lib/status";
import { formatDuration } from "@/lib/utils";
import type { Automation } from "@/types/automation";
import type { AutomationSource } from "@/types/automation-import";
import type { Schedule } from "@/types/schedule";
import type { Trigger } from "@/types/trigger";
import type { Worker } from "@/types/worker";

export function AutomationDetail({ id }: { id: string }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const automation = useApi<Automation>(`/automations/${id}`);
  const workers = useApi<Worker[]>("/workers");
  const triggers = useApi<Trigger[]>("/triggers");
  const schedules = useApi<Schedule[]>("/schedules");
  const sources = useApi<AutomationSource[]>(`/automations/${id}/sources`);

  async function checkForUpdate() {
    if (!token) return;
    try {
      const result = await apiRequest<{ update_available?: boolean }>(`/automations/${id}:sync`, { method: "POST", token });
      toast({
        title: result.update_available ? "Atualizacao disponivel" : "Ja esta atualizado",
        kind: result.update_available ? "info" : "success",
      });
      await sources.refetch();
    } catch (err) {
      toast({ title: "Falha ao verificar atualizacao", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  if (automation.error) return <ErrorState message={automation.error} onRetry={automation.refetch} />;
  if (automation.loading || !automation.data) return <Skeleton className="h-64 rounded-lg" />;

  const item = automation.data;
  const automationTriggers = (triggers.data ?? []).filter((trigger) => trigger.automation_id === item.id);
  const automationSchedules = (schedules.data ?? []).filter((schedule) => schedule.automation_id === item.id);

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <SectionCard title="Visao geral">
          <div className="grid gap-4 sm:grid-cols-2">
            {item.key && <Meta label="Chave" value={<span className="tabular">{item.key}</span>} />}
            <Meta label="Slug" value={<span className="tabular">{item.slug}</span>} />
            <Meta label="Executor" value={executorLabel(item.executor_type)} />
            <Meta label="Prioridade padrao" value={<PriorityBadge priority={item.default_priority} />} />
            <Meta label="Situacao" value={<Badge tone={item.is_active ? "success" : "neutral"}>{item.is_active ? "Ativa" : "Inativa"}</Badge>} />
            <Meta label="Timeout" value={formatDuration(item.timeout_seconds)} />
            <Meta label="Max. retries" value={<span className="tabular">{item.max_retries}</span>} />
          </div>
          {item.description && <p className="mt-4 border-t border-border pt-4 text-sm text-muted-foreground">{item.description}</p>}
        </SectionCard>

        <SectionCard title="Preferencia de workers" description="Ordem de tentativa no despacho">
          <WorkerPreferences automationId={item.id} workers={workers.data ?? []} />
        </SectionCard>

        <div className="space-y-3">
          {(sources.data ?? []).some((source) => source.type === "github") && (
            <div className="flex justify-end">
              <Button variant="outline" size="sm" onClick={checkForUpdate}>
                <RotateCw className="h-3.5 w-3.5" /> Verificar atualizacao
              </Button>
            </div>
          )}
          <AutomationVersionsPanel automation={item} />
        </div>

        <SectionCard title="Origem" description="De onde vem o pacote desta automacao" bodyClassName="p-0">
          {sources.loading ? (
            <div className="p-5">
              <Skeleton className="h-16 rounded-lg" />
            </div>
          ) : (sources.data ?? []).length === 0 ? (
            <div className="p-5">
              <EmptyState icon={GitBranch} title="Sem origem registrada" description="Automacao cadastrada manualmente, sem importacao vinculada." />
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {sources.data!.map((source) => (
                <li key={source.id} className="px-5 py-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <Badge tone={source.type === "github" ? "info" : "neutral"}>{source.type === "github" ? "GitHub" : "Upload manual"}</Badge>
                    {source.sync_status === "update_available" && <Badge tone="warning">Atualizacao disponivel</Badge>}
                  </div>
                  {source.type === "github" ? (
                    <p className="tabular mt-1.5 truncate text-xs text-muted-foreground">
                      {source.owner}/{source.repository} @ {source.branch} - {source.automation_path}
                    </p>
                  ) : (
                    <p className="tabular mt-1.5 truncate text-xs text-muted-foreground">{source.original_filename}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </SectionCard>

        <SectionCard title="Dados brutos">
          <DetailJson data={item} />
        </SectionCard>
      </div>

      <div className="space-y-6">
        <SectionCard title="Gatilhos" bodyClassName="p-0">
          {automationTriggers.length === 0 ? (
            <div className="p-5">
              <EmptyState icon={Webhook} title="Sem gatilhos" description="Nenhum gatilho vinculado." />
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {automationTriggers.map((trigger) => (
                <TriggerRow key={trigger.id} trigger={trigger} />
              ))}
            </ul>
          )}
        </SectionCard>

        <SectionCard title="Agendamentos" bodyClassName="p-0">
          {automationSchedules.length === 0 ? (
            <div className="p-5">
              <EmptyState icon={CalendarClock} title="Sem agendamentos" description="Nenhum schedule vinculado." />
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {automationSchedules.map((schedule) => (
                <li key={schedule.id} className="flex items-center justify-between gap-2 px-5 py-3">
                  <span className="text-sm">{describeRecurrence(schedule)}</span>
                  <Badge tone={schedule.is_active ? "success" : "neutral"}>{schedule.timezone}</Badge>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>

        <SectionCard title="Workers disponiveis" bodyClassName="p-0">
          {(workers.data ?? []).length === 0 ? (
            <div className="p-5">
              <EmptyState icon={Server} title="Sem workers" />
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {(workers.data ?? []).slice(0, 5).map((worker) => (
                <li key={worker.id} className="px-5 py-3">
                  <Link href={`/workers/${worker.id}`} className="text-sm font-medium hover:text-primary">
                    {worker.name}
                  </Link>
                  <p className="tabular text-xs text-muted-foreground">{worker.hostname}</p>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
      </div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="mt-1 text-sm font-medium">{value}</div>
    </div>
  );
}

function TriggerRow({ trigger }: { trigger: Trigger }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(trigger.route_path);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard is best effort only.
    }
  }

  if (trigger.trigger_type === "chained") {
    return (
      <li className="px-5 py-3">
        <Badge tone="primary">disparo em cadeia</Badge>
        <p className="mt-1.5 truncate text-xs text-muted-foreground">
          Disparado quando a automacao de origem terminar ({trigger.condition ?? "success"}). Para orquestrar varias etapas com dependencias, use um Fluxo.
        </p>
      </li>
    );
  }

  return (
    <li className="px-5 py-3">
      <div className="flex items-center justify-between gap-2">
        <Badge tone="info">{trigger.trigger_type}</Badge>
        <button type="button" onClick={copy} className="text-muted-foreground hover:text-foreground">
          {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
        </button>
      </div>
      <p className="tabular mt-1.5 truncate text-xs text-muted-foreground">{trigger.route_path}</p>
    </li>
  );
}

