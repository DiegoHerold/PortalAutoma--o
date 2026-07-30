"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Archive, Bot, ExternalLink, Pause, Pencil, PlayCircle, Power, PowerOff } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { StatusBadge } from "@/components/ui/status-badge";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { targetIcon, targetLabel } from "@/components/schedules/schedule-calendar-item";
import { describeSchedule } from "@/lib/cron";
import { archiveSchedule, disableSchedule, enableSchedule, pauseSchedule, triggerSchedule } from "@/lib/schedule-api";
import { maxCatchUpRunsLabel, misfireGraceLabel, misfirePolicyMeta, overlapPolicyMeta } from "@/lib/schedule-policies";
import { durationSummary, plannedRangeLabel } from "@/lib/schedule-duration";
import { scheduleStatusMeta, temporalStatusMeta } from "@/lib/status";
import { formatDateTime } from "@/lib/utils";
import type { Automation } from "@/types/automation";
import type { Flow } from "@/types/flow";
import type { Schedule, ScheduleCalendarItem, ScheduleExecution } from "@/types/schedule";

type Action = "enable" | "pause" | "disable" | "archive" | "trigger";
type Tab = "summary" | "schedule" | "execution" | "timeline" | "history";

export function ScheduleDetailSheet({
  scheduleId,
  item,
  open,
  onClose,
  automationById,
  flowById,
  onEdit,
  onChanged,
  canWrite,
  canTrigger,
}: {
  scheduleId: number | null;
  item: ScheduleCalendarItem | null;
  open: boolean;
  onClose: () => void;
  automationById: Map<number, Automation>;
  flowById: Map<string, Flow>;
  onEdit: (scheduleId: number) => void;
  onChanged: () => void | Promise<void>;
  canWrite: boolean;
  canTrigger: boolean;
}) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [tab, setTab] = useState<Tab>("summary");
  const [busy, setBusy] = useState<Action | null>(null);

  const scheduleQuery = useApi<Schedule>(scheduleId ? `/schedules/${scheduleId}` : null, { enabled: open && !!scheduleId });
  const schedule = scheduleQuery.data ?? null;

  const history = useApi<ScheduleExecution[]>(scheduleId ? `/schedules/${scheduleId}/history` : null, { enabled: open && !!scheduleId });

  const matchingHistoryEntry = useMemo(() => {
    if (!item || !history.data) return null;
    return history.data.find((h) => h.id === item.schedule_execution_id) ?? null;
  }, [item, history.data]);

  if (!open || scheduleId == null) return null;

  const Icon = item ? targetIcon(item.target_type) : Bot;
  const entityLabel =
    item?.schedule_name ||
    item?.target_name ||
    (schedule
      ? schedule.target_type === "flow"
        ? (flowById.get(schedule.flow_id ?? "")?.name ?? schedule.name ?? `Fluxo #${schedule.flow_id ?? "?"}`)
        : (automationById.get(schedule.automation_id ?? -1)?.name ?? schedule.name ?? `Automação #${schedule.automation_id ?? "?"}`)
      : `Agendamento #${scheduleId}`);

  const temporalMeta = item ? temporalStatusMeta(item.temporal_status) : null;
  const scheduleMeta = schedule ? scheduleStatusMeta(schedule.status) : null;

  async function run(action: Action) {
    if (!token || !schedule) return;
    setBusy(action);
    try {
      const fn = { enable: enableSchedule, pause: pauseSchedule, disable: disableSchedule, archive: archiveSchedule, trigger: triggerSchedule }[action];
      await fn(token, schedule.id);
      const labels: Record<Action, string> = {
        enable: "Agendamento habilitado",
        pause: "Agendamento pausado",
        disable: "Agendamento desabilitado",
        archive: "Agendamento arquivado",
        trigger: "Disparo manual enviado",
      };
      toast({ title: labels[action], kind: "success" });
      await Promise.all([onChanged(), scheduleQuery.refetch(), history.refetch()]);
    } catch (err) {
      toast({ title: "Falha na ação", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setBusy(null);
    }
  }

  const tabs: { value: Tab; label: string; count?: number }[] = [
    { value: "summary", label: "Resumo" },
    { value: "schedule", label: "Agendamento" },
    ...(item?.execution_id || item?.flow_execution_id ? [{ value: "execution" as Tab, label: "Execução" }] : []),
    { value: "timeline", label: "Timeline" },
    { value: "history", label: "Histórico", count: history.data?.length },
  ];

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={
        <span className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-muted-foreground" /> {entityLabel}
        </span>
      }
      description={schedule ? describeSchedule(schedule) : undefined}
      widthClassName="w-full sm:max-w-xl"
      footer={
        <div className="flex w-full flex-wrap items-center justify-end gap-2">
          {!schedule ? (
            <Spinner />
          ) : (
            <>
              <Button variant="outline" size="sm" onClick={() => onEdit(schedule.id)} disabled={!canWrite} title={canWrite ? undefined : "Sem permissão para editar"}>
                <Pencil className="h-3.5 w-3.5" /> Editar
              </Button>
              {canWrite && schedule.status !== "active" && schedule.status !== "archived" && (
                <Button variant="secondary" size="sm" disabled={!!busy} onClick={() => run("enable")}>
                  {busy === "enable" ? <Spinner /> : <Power className="h-3.5 w-3.5" />} Habilitar
                </Button>
              )}
              {canWrite && schedule.status === "active" && (
                <Button variant="secondary" size="sm" disabled={!!busy} onClick={() => run("pause")}>
                  {busy === "pause" ? <Spinner /> : <Pause className="h-3.5 w-3.5" />} Pausar
                </Button>
              )}
              {canWrite && schedule.status !== "disabled" && schedule.status !== "archived" && (
                <Button variant="outline" size="sm" disabled={!!busy} onClick={() => run("disable")}>
                  {busy === "disable" ? <Spinner /> : <PowerOff className="h-3.5 w-3.5" />} Desabilitar
                </Button>
              )}
              {canWrite && schedule.status !== "archived" && (
                <Button variant="destructive" size="sm" disabled={!!busy} onClick={() => run("archive")}>
                  {busy === "archive" ? <Spinner /> : <Archive className="h-3.5 w-3.5" />} Arquivar
                </Button>
              )}
              <Button size="sm" disabled={!!busy || !canTrigger} title={canTrigger ? undefined : "Sem permissão para disparar"} onClick={() => run("trigger")}>
                {busy === "trigger" ? <Spinner /> : <PlayCircle className="h-3.5 w-3.5" />} Executar agora
              </Button>
            </>
          )}
        </div>
      }
    >
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-2">
          {item && temporalMeta && (
            <Badge tone={temporalMeta.tone} className="gap-1">
              <temporalMeta.icon className="h-3 w-3" /> {temporalMeta.label}
            </Badge>
          )}
          {schedule && scheduleMeta && <Badge tone={scheduleMeta.tone}>Agendamento: {scheduleMeta.label}</Badge>}
          <Badge tone="outline">{item ? targetLabel(item.target_type) : schedule?.target_type === "flow" ? "Fluxo" : "Automação"}</Badge>
          {item?.reason && <span className="text-xs text-muted-foreground">{item.reason}</span>}
        </div>

        <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)} items={tabs} className="max-w-full overflow-x-auto" />

        {!schedule ? (
          <Skeleton className="h-48 rounded-lg" />
        ) : tab === "summary" ? (
          <SummaryTab item={item} schedule={schedule} />
        ) : tab === "schedule" ? (
          <ScheduleTab schedule={schedule} />
        ) : tab === "execution" ? (
          <ExecutionTab item={item} />
        ) : tab === "timeline" ? (
          <TimelineTab item={item} historyEntry={matchingHistoryEntry} />
        ) : (
          <HistoryList history={history} />
        )}
      </div>
    </Sheet>
  );
}

function DetailGrid({ items }: { items: [string, string][] }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt className="text-xs text-muted-foreground">{label}</dt>
          <dd className="tabular font-medium">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function SummaryTab({ item, schedule }: { item: ScheduleCalendarItem | null; schedule: Schedule }) {
  return (
    <div className="space-y-5">
      <DetailGrid
        items={[
          ["Horário", item ? plannedRangeLabel(item) : "—"],
          ["Duração", item ? durationSummary(item) : "—"],
          ["Fuso horário", schedule.timezone],
          ["Responsável", item?.responsible ?? "—"],
          ["Automação/Fluxo", item?.target_name ?? "—"],
          ["Versão", item?.target_version ?? "—"],
          ["Agent", item?.agent ?? "—"],
          ["Próxima execução (agendamento)", formatDateTime(schedule.next_run_at)],
        ]}
      />
      {item?.progress && item.progress.total > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Progresso do fluxo</p>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div className="h-full bg-success" style={{ width: `${(item.progress.succeeded / item.progress.total) * 100}%` }} />
          </div>
          <p className="text-xs text-muted-foreground">
            {item.progress.succeeded} de {item.progress.total} nós concluídos
            {item.progress.running > 0 && ` · ${item.progress.running} em execução`}
            {item.progress.failed > 0 && ` · ${item.progress.failed} com falha`}
          </p>
        </div>
      )}
      {item?.is_estimated && (
        <p className="rounded-md border border-border bg-muted/20 p-2 text-xs text-muted-foreground">
          Duração estimada a partir do histórico ({item.estimation_confidence === "high" ? "alta confiança" : item.estimation_confidence === "medium" ? "confiança média" : "poucas execuções anteriores"}) — o horário de término ainda não é definitivo.
        </p>
      )}
    </div>
  );
}

function ScheduleTab({ schedule }: { schedule: Schedule }) {
  const misfire = misfirePolicyMeta(schedule.misfire_policy);
  const overlap = overlapPolicyMeta(schedule.overlap_policy);
  return (
    <div className="space-y-5">
      <DetailGrid
        items={[
          ["Recorrência", describeSchedule(schedule)],
          ["Expressão cron", schedule.cron_expression ?? "—"],
          ["Próxima execução", formatDateTime(schedule.next_run_at)],
          ["Última execução", formatDateTime(schedule.last_run_at)],
        ]}
      />
      <section className="space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Política de atraso (misfire)</h3>
        <p className="text-sm font-medium">{misfire.label}</p>
        <p className="text-xs text-muted-foreground">{misfire.description}</p>
        <p className="text-xs text-muted-foreground">
          Tolerância: {misfireGraceLabel(schedule.misfire_grace_seconds)} · {maxCatchUpRunsLabel(schedule.max_catch_up_runs)}
        </p>
      </section>
      <section className="space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Política de sobreposição</h3>
        <p className="text-sm font-medium">{overlap.label}</p>
        <p className="text-xs text-muted-foreground">{overlap.description}</p>
      </section>
      {schedule.payload && Object.keys(schedule.payload).length > 0 && (
        <section className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Parâmetros</h3>
          <pre className="overflow-x-auto rounded-md border border-border bg-muted/20 p-2 text-xs">{JSON.stringify(schedule.payload, null, 2)}</pre>
        </section>
      )}
    </div>
  );
}

function ExecutionTab({ item }: { item: ScheduleCalendarItem | null }) {
  if (!item || (!item.execution_id && !item.flow_execution_id)) {
    return <p className="text-sm text-muted-foreground">Esta ocorrência ainda não criou uma execução.</p>;
  }
  const href = item.flow_execution_id ? `/flow-executions/${item.flow_execution_id}` : `/executions/${item.execution_id}`;
  return (
    <div className="space-y-4">
      <DetailGrid
        items={[
          ["Status", item.status],
          ["Início real", formatDateTime(item.actual_start)],
          ["Fim real", formatDateTime(item.actual_end)],
          ["Duração", durationSummary(item)],
          ["Agent", item.agent ?? "—"],
        ]}
      />
      {item.reason && <p className="text-xs text-destructive">{item.reason}</p>}
      <Button asChild variant="outline" size="sm">
        <Link href={href}>
          <ExternalLink className="h-3.5 w-3.5" /> Abrir execução
        </Link>
      </Button>
    </div>
  );
}

function TimelineTab({ item, historyEntry }: { item: ScheduleCalendarItem | null; historyEntry: ScheduleExecution | null }) {
  if (!item) return <p className="text-sm text-muted-foreground">Sem ocorrência selecionada.</p>;

  const steps: { label: string; at: string | null }[] = [
    { label: "Ocorrência planejada", at: item.planned_start },
    { label: "Registrada/disparada", at: historyEntry?.created_at ?? null },
    { label: "Execução iniciada", at: item.actual_start },
    {
      label: item.temporal_status === "past_failed" || item.temporal_status === "past_dispatch_failed" ? "Execução falhou" : item.temporal_status === "past_cancelled" ? "Execução cancelada" : "Execução concluída",
      at: item.actual_end,
    },
  ].filter((step) => step.at);

  return (
    <ol className="space-y-3 border-l border-border pl-4">
      {steps.map((step, idx) => (
        <li key={`${step.label}-${idx}`} className="relative">
          <span className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full border-2 border-background bg-primary" />
          <p className="text-sm font-medium">{step.label}</p>
          <p className="tabular text-xs text-muted-foreground">{formatDateTime(step.at)}</p>
        </li>
      ))}
      {item.reason && (
        <li className="relative">
          <span className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full border-2 border-background bg-warning" />
          <p className="text-sm font-medium">{item.reason}</p>
        </li>
      )}
    </ol>
  );
}

function HistoryList({ history }: { history: ReturnType<typeof useApi<ScheduleExecution[]>> }) {
  if (history.loading) return <Skeleton className="h-40 rounded-lg" />;
  if (history.error) return <p className="text-sm text-destructive">{history.error}</p>;
  const items = history.data ?? [];
  if (items.length === 0) return <p className="text-sm text-muted-foreground">Nenhuma execução registrada ainda.</p>;
  return (
    <ul className="space-y-2">
      {items
        .slice()
        .sort((a, b) => b.scheduled_for.localeCompare(a.scheduled_for))
        .map((execution) => (
          <li key={execution.id} className="rounded-md border border-border p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="tabular text-sm font-medium">{formatDateTime(execution.scheduled_for)}</span>
              <StatusBadge status={execution.status} />
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {execution.trigger_type === "manual" ? "Disparo manual" : "Disparo agendado"}
              {execution.started_at && ` · início ${formatDateTime(execution.started_at)}`}
              {execution.completed_at && ` · fim ${formatDateTime(execution.completed_at)}`}
            </p>
            {execution.failure_summary && <p className="mt-1 text-xs text-destructive">{execution.failure_summary}</p>}
          </li>
        ))}
    </ul>
  );
}
