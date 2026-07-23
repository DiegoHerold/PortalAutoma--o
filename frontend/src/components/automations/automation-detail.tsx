"use client";

import Link from "next/link";
import { Webhook, CalendarClock, Server, Copy, Check } from "lucide-react";
import { useState } from "react";

import { SectionCard } from "@/components/shared/section-card";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Badge } from "@/components/ui/badge";
import { PriorityBadge } from "@/components/ui/status-badge";
import { DetailJson } from "@/components/shared/detail-json";
import { Skeleton } from "@/components/ui/skeleton";
import { WorkerPreferences } from "@/components/automations/worker-preferences";
import { useApi } from "@/hooks/use-api";
import { executorLabel } from "@/lib/status";
import { formatDuration } from "@/lib/utils";
import type { Automation } from "@/types/automation";
import type { Worker } from "@/types/worker";
import type { Trigger } from "@/types/trigger";
import type { Schedule } from "@/types/schedule";

export function AutomationDetail({ id }: { id: string }) {
  const automation = useApi<Automation>(`/automations/${id}`);
  const workers = useApi<Worker[]>("/workers");
  const triggers = useApi<Trigger[]>("/triggers");
  const schedules = useApi<Schedule[]>("/schedules");

  if (automation.error) return <ErrorState message={automation.error} onRetry={automation.refetch} />;
  if (automation.loading || !automation.data) return <Skeleton className="h-64 rounded-lg" />;

  const a = automation.data;
  const automationTriggers = (triggers.data ?? []).filter((t) => t.automation_id === a.id);
  const automationSchedules = (schedules.data ?? []).filter((s) => s.automation_id === a.id);

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <SectionCard title="Visão geral">
          <div className="grid gap-4 sm:grid-cols-2">
            <Meta label="Slug" value={<span className="tabular">{a.slug}</span>} />
            <Meta label="Executor" value={executorLabel(a.executor_type)} />
            <Meta label="Prioridade padrão" value={<PriorityBadge priority={a.default_priority} />} />
            <Meta label="Situação" value={<Badge tone={a.is_active ? "success" : "neutral"}>{a.is_active ? "Ativa" : "Inativa"}</Badge>} />
            <Meta label="Timeout" value={formatDuration(a.timeout_seconds)} />
            <Meta label="Máx. retries" value={<span className="tabular">{a.max_retries}</span>} />
          </div>
          {a.description && <p className="mt-4 border-t border-border pt-4 text-sm text-muted-foreground">{a.description}</p>}
        </SectionCard>

        <SectionCard title="Preferência de workers" description="Ordem de tentativa no despacho">
          <WorkerPreferences automationId={a.id} workers={workers.data ?? []} />
        </SectionCard>

        <SectionCard title="Dados brutos">
          <DetailJson data={a} />
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
              {automationTriggers.map((t) => (
                <TriggerRow key={t.id} trigger={t} />
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
              {automationSchedules.map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-2 px-5 py-3">
                  <span className="tabular text-sm">{s.cron_expression}</span>
                  <Badge tone={s.is_active ? "success" : "neutral"}>{s.timezone}</Badge>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>

        <SectionCard title="Workers disponíveis" bodyClassName="p-0">
          {(workers.data ?? []).length === 0 ? (
            <div className="p-5">
              <EmptyState icon={Server} title="Sem workers" />
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {(workers.data ?? []).slice(0, 5).map((w) => (
                <li key={w.id} className="px-5 py-3">
                  <Link href={`/workers/${w.id}`} className="text-sm font-medium hover:text-primary">
                    {w.name}
                  </Link>
                  <p className="tabular text-xs text-muted-foreground">{w.hostname}</p>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
      </div>
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

function TriggerRow({ trigger }: { trigger: Trigger }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(trigger.route_path);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }
  return (
    <li className="px-5 py-3">
      <div className="flex items-center justify-between gap-2">
        <Badge tone="info">{trigger.trigger_type}</Badge>
        <button onClick={copy} className="text-muted-foreground hover:text-foreground">
          {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
        </button>
      </div>
      <p className="tabular mt-1.5 truncate text-xs text-muted-foreground">{trigger.route_path}</p>
    </li>
  );
}
