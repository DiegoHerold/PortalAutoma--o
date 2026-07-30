"use client";

import Link from "next/link";
import { CalendarClock, ExternalLink, KeyRound, Pencil, RotateCcw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { WebhookExecutions } from "@/components/webhooks/webhook-executions";
import { WebhookUrlCard } from "@/components/webhooks/webhook-url-card";
import { webhookStatusMeta } from "@/lib/status";
import { formatDateTime, formatDuration } from "@/lib/utils";
import type { Automation } from "@/types/automation";
import type { Trigger } from "@/types/trigger";

import { automationName, formatLastSecret, mappingSummary, webhookStatus } from "./webhook-utils";

export function WebhookDetailsSheet({
  trigger,
  automations,
  invokeBaseUrl,
  onClose,
  onEdit,
  onRotate,
}: {
  trigger: Trigger | null;
  automations: Automation[];
  invokeBaseUrl?: string | null;
  onClose: () => void;
  onEdit: (trigger: Trigger) => void;
  onRotate: (trigger: Trigger) => void;
}) {
  if (!trigger) return null;
  const status = webhookStatusMeta(webhookStatus(trigger));
  const Icon = status.icon;

  return (
    <Sheet
      open
      onClose={onClose}
      title={trigger.name || trigger.route_path}
      description={automationName(automations, trigger.automation_id)}
      widthClassName="w-full sm:max-w-3xl"
      footer={
        <>
          <Button variant="outline" onClick={() => onRotate(trigger)}>
            <RotateCcw className="h-4 w-4" /> Rotacionar secret
          </Button>
          <Button onClick={() => onEdit(trigger)}>
            <Pencil className="h-4 w-4" /> Editar
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={status.tone}>
            <Icon className="h-3.5 w-3.5" /> {status.label}
          </Badge>
          <Badge tone="outline">{trigger.method}</Badge>
          <Badge tone={trigger.secret_configured ? "success" : "destructive"}>
            <KeyRound className="h-3.5 w-3.5" /> {formatLastSecret(trigger)}
          </Badge>
        </div>

        <WebhookUrlCard trigger={trigger} invokeBaseUrl={invokeBaseUrl} />

        <div className="grid gap-3 md:grid-cols-2">
          <InfoItem label="Route path" value={trigger.route_path} mono />
          <InfoItem label="Mapeamento" value={mappingSummary(trigger.parameter_mapping_json)} />
          <InfoItem label="Criado em" value={formatDateTime(trigger.created_at)} />
          <InfoItem label="Atualizado em" value={formatDateTime(trigger.updated_at)} />
          <InfoItem label="Ultima invocacao" value={formatDateTime(trigger.last_invoked_at)} />
          <InfoItem label="Duracao da ultima Execution" value={formatDuration(trigger.last_execution_duration_seconds)} />
        </div>

        {trigger.parameter_mapping_json && (
          <div className="rounded-md border border-border bg-background p-3">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Mapping JSON</p>
            <pre className="tabular max-h-56 overflow-auto text-xs">{JSON.stringify(trigger.parameter_mapping_json, null, 2)}</pre>
          </div>
        )}

        {trigger.last_execution_id && (
          <Button variant="outline" asChild>
            <Link href={`/executions/${trigger.last_execution_id}`}>
              <ExternalLink className="h-4 w-4" /> Abrir ultima Execution
            </Link>
          </Button>
        )}

        <WebhookExecutions trigger={trigger} />

        <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
          <CalendarClock className="mr-1.5 inline h-3.5 w-3.5" />
          Headers, query params e payload sao mantidos apenas como entrada da Execution. Secrets completos nao sao retornados por listagem ou detalhe.
        </div>
      </div>
    </Sheet>
  );
}

function InfoItem({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-md border border-border bg-card p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={mono ? "tabular mt-1 truncate text-sm" : "mt-1 text-sm"}>{value}</p>
    </div>
  );
}
