"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Check,
  Copy,
  Eye,
  FlaskConical,
  History,
  KeyRound,
  Pencil,
  Power,
  RotateCcw,
  Route,
  ShieldCheck,
  Trash2,
  type LucideIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { webhookStatusMeta } from "@/lib/status";
import { cn, formatDateTime, formatDuration, relativeFromNow } from "@/lib/utils";
import type { Automation } from "@/types/automation";
import type { Trigger } from "@/types/trigger";

import { automationName, formatLastSecret, mappingSummary, webhookInvocationUrl, webhookStatus } from "./webhook-utils";

export function WebhooksTable({
  triggers,
  automations,
  invokeBaseUrl,
  onOpen,
  onEdit,
  onTest,
  onRotate,
  onToggle,
  onDelete,
}: {
  triggers: Trigger[];
  automations: Automation[];
  invokeBaseUrl?: string | null;
  onOpen: (trigger: Trigger) => void;
  onEdit: (trigger: Trigger) => void;
  onTest: (trigger: Trigger) => void;
  onRotate: (trigger: Trigger) => void;
  onToggle: (trigger: Trigger) => void;
  onDelete: (trigger: Trigger) => void;
}) {
  return (
    <div className="grid gap-3 xl:grid-cols-2">
      {triggers.map((trigger) => (
        <WebhookCard
          key={trigger.id}
          trigger={trigger}
          automations={automations}
          invokeBaseUrl={invokeBaseUrl}
          onOpen={onOpen}
          onEdit={onEdit}
          onTest={onTest}
          onRotate={onRotate}
          onToggle={onToggle}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}

function WebhookCard({
  trigger,
  automations,
  invokeBaseUrl,
  onOpen,
  onEdit,
  onTest,
  onRotate,
  onToggle,
  onDelete,
}: {
  trigger: Trigger;
  automations: Automation[];
  invokeBaseUrl?: string | null;
  onOpen: (trigger: Trigger) => void;
  onEdit: (trigger: Trigger) => void;
  onTest: (trigger: Trigger) => void;
  onRotate: (trigger: Trigger) => void;
  onToggle: (trigger: Trigger) => void;
  onDelete: (trigger: Trigger) => void;
}) {
  const { toast } = useToast();
  const [copied, setCopied] = useState<"url" | "curl" | null>(null);
  const status = webhookStatusMeta(webhookStatus(trigger));
  const StatusIcon = status.icon;
  const url = webhookInvocationUrl(trigger, invokeBaseUrl);
  const curl = curlFor(trigger, url);
  const lastExecutionTone = executionTone(trigger.last_execution_status);

  async function copy(value: string, kind: "url" | "curl") {
    if (!value) return;
    await navigator.clipboard.writeText(value);
    setCopied(kind);
    toast({ title: kind === "url" ? "URL copiada" : "cURL copiado", kind: "success" });
    setTimeout(() => setCopied(null), 1400);
  }

  return (
    <article className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <button type="button" className="min-w-0 text-left" onClick={() => onOpen(trigger)}>
          <span className="flex items-center gap-2">
            <Route className="h-4 w-4 text-primary" />
            <span className="truncate font-medium hover:text-primary">{trigger.name || trigger.route_path}</span>
          </span>
          <span className="tabular mt-1 block truncate text-xs text-muted-foreground">{trigger.route_path}</span>
        </button>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={status.tone}>
            <StatusIcon className="h-3.5 w-3.5" /> {status.label}
          </Badge>
          <Badge tone={trigger.secret_configured ? "success" : "destructive"}>
            <KeyRound className="h-3.5 w-3.5" /> {formatLastSecret(trigger)}
          </Badge>
        </div>
      </div>

      <div className="mt-4 grid gap-2 md:grid-cols-[1fr_auto] md:items-center">
        <div className="min-w-0 rounded-md border border-border bg-muted/35 px-3 py-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Endpoint público</p>
          <code className="tabular mt-1 block truncate text-xs">{url || "URL indisponível"}</code>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => copy(url, "url")} disabled={!url}>
            {copied === "url" ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />} URL
          </Button>
          <Button size="sm" variant="outline" onClick={() => copy(curl, "curl")} disabled={!url}>
            {copied === "curl" ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />} cURL
          </Button>
        </div>
      </div>

      <div className="mt-4 grid gap-2 text-sm sm:grid-cols-3">
        <InfoBlock label="Destino" value={automationName(automations, trigger.automation_id)} />
        <InfoBlock label="Autenticação" value={`${trigger.method || "POST"} + ${trigger.required_header || "X-Trigger-Secret"}`} />
        <InfoBlock label="Mapeamento" value={mappingSummary(trigger.parameter_mapping_json)} />
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Última execução</span>
            {trigger.last_execution_status && <Badge tone={lastExecutionTone}>{trigger.last_execution_status}</Badge>}
          </div>
          {trigger.last_execution_id ? (
            <p className="mt-1 text-sm">
              <Link href={`/executions/${trigger.last_execution_id}`} className="tabular text-primary hover:underline">
                {trigger.last_execution_id.slice(0, 8)}
              </Link>
              <span className="text-muted-foreground">
                {" "}
                · {formatDuration(trigger.last_execution_duration_seconds)} · {relativeFromNow(trigger.last_invoked_at)}
              </span>
            </p>
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">Ainda sem chamadas recebidas.</p>
          )}
          <p className="mt-1 text-xs text-muted-foreground">Criado {formatDateTime(trigger.created_at)}</p>
        </div>

        <div className="flex flex-wrap justify-end gap-1">
          <IconButton title="Abrir detalhes" onClick={() => onOpen(trigger)} icon={Eye} />
          <IconButton title="Editar" onClick={() => onEdit(trigger)} icon={Pencil} />
          <IconButton title="Testar mapping" onClick={() => onTest(trigger)} icon={FlaskConical} />
          <IconButton title="Rotacionar secret" onClick={() => onRotate(trigger)} icon={RotateCcw} />
          <IconButton title={trigger.is_active ? "Desativar" : "Ativar"} onClick={() => onToggle(trigger)} icon={Power} />
          <Button size="icon" variant="ghost" asChild title="Ver histórico de execuções">
            <Link href={`/executions?origin=trigger&trigger_id=${trigger.id}`}>
              <History className="h-4 w-4" />
            </Link>
          </Button>
          <IconButton title="Excluir" onClick={() => onDelete(trigger)} icon={Trash2} className="text-destructive hover:bg-destructive/10 hover:text-destructive" />
        </div>
      </div>

      {!trigger.secret_configured && (
        <div className="mt-3 flex items-start gap-2 rounded-md border border-destructive/25 bg-destructive/5 px-3 py-2 text-xs text-destructive">
          <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>Sem secret configurado. Rotacione o secret antes de expor este endpoint.</span>
        </div>
      )}
    </article>
  );
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md bg-muted/35 px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-0.5 truncate font-medium">{value}</p>
    </div>
  );
}

function IconButton({
  title,
  onClick,
  icon: Icon,
  className,
}: {
  title: string;
  onClick: () => void;
  icon: LucideIcon;
  className?: string;
}) {
  return (
    <Button size="icon" variant="ghost" onClick={onClick} title={title} className={cn(className)}>
      <Icon className="h-4 w-4" />
    </Button>
  );
}

function curlFor(trigger: Trigger, url: string): string {
  return [
    `curl -X POST "${url || "{url}"}"`,
    '  -H "Content-Type: application/json"',
    `  -H "${trigger.required_header || "X-Trigger-Secret"}: SEU_SECRET"`,
    '  -H "Idempotency-Key: cliente-123-evento-456"',
    '  -H "X-Correlation-ID: crm-123"',
    "  -d '{\"company_id\":123,\"event\":\"created\"}'",
  ].join(" \\\n");
}

function executionTone(status?: string | null): "neutral" | "success" | "warning" | "destructive" | "info" {
  if (!status) return "neutral";
  if (["succeeded", "success", "completed"].includes(status)) return "success";
  if (["failed", "timed_out", "lost"].includes(status)) return "destructive";
  if (["queued", "pending", "created", "ready", "cancelling"].includes(status)) return "warning";
  if (["running", "preparing", "committed"].includes(status)) return "info";
  return "neutral";
}
