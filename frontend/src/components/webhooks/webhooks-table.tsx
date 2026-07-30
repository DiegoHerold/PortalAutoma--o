"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, Copy, Eye, FlaskConical, History, Pencil, Power, RotateCcw, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { webhookStatusMeta } from "@/lib/status";
import { formatDateTime, formatDuration } from "@/lib/utils";
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
  const { toast } = useToast();
  const [copiedId, setCopiedId] = useState<number | null>(null);

  async function copy(trigger: Trigger) {
    const url = webhookInvocationUrl(trigger, invokeBaseUrl);
    if (!url) return;
    await navigator.clipboard.writeText(url);
    setCopiedId(trigger.id);
    toast({ title: "URL copiada", kind: "success" });
    setTimeout(() => setCopiedId(null), 1200);
  }

  return (
    <Card>
      <Table>
        <THead>
          <TR>
            <TH>Webhook</TH>
            <TH>Destino</TH>
            <TH>Status</TH>
            <TH>URL</TH>
            <TH>Ultima invocacao</TH>
            <TH>Ultima Execution</TH>
            <TH className="text-right">Acoes</TH>
          </TR>
        </THead>
        <TBody>
          {triggers.map((trigger) => {
            const status = webhookStatusMeta(webhookStatus(trigger));
            const StatusIcon = status.icon;
            const url = webhookInvocationUrl(trigger, invokeBaseUrl);
            return (
              <TR key={trigger.id}>
                <TD>
                  <button type="button" className="min-w-0 text-left" onClick={() => onOpen(trigger)}>
                    <p className="truncate font-medium hover:text-primary">{trigger.name || trigger.route_path}</p>
                    <p className="tabular mt-1 truncate text-xs text-muted-foreground">{trigger.route_path}</p>
                  </button>
                  <p className="mt-1 text-xs text-muted-foreground">{mappingSummary(trigger.parameter_mapping_json)}</p>
                </TD>
                <TD className="max-w-[220px] truncate">{automationName(automations, trigger.automation_id)}</TD>
                <TD>
                  <div className="flex flex-col gap-1.5">
                    <Badge tone={status.tone}>
                      <StatusIcon className="h-3.5 w-3.5" /> {status.label}
                    </Badge>
                    <span className="text-xs text-muted-foreground">{formatLastSecret(trigger)}</span>
                  </div>
                </TD>
                <TD>
                  <div className="flex max-w-[300px] items-center gap-2">
                    <code className="tabular truncate rounded bg-muted px-2 py-1 text-xs">{url || "-"}</code>
                    <button type="button" title="Copiar URL" onClick={() => copy(trigger)} className="text-muted-foreground hover:text-foreground">
                      {copiedId === trigger.id ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}
                    </button>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {trigger.method} + {trigger.required_header}
                  </p>
                </TD>
                <TD>
                  <p className="text-sm">{formatDateTime(trigger.last_invoked_at)}</p>
                  <p className="text-xs text-muted-foreground">Criado: {formatDateTime(trigger.created_at)}</p>
                </TD>
                <TD>
                  {trigger.last_execution_id ? (
                    <Link className="tabular text-sm text-primary underline underline-offset-2" href={`/executions/${trigger.last_execution_id}`}>
                      {trigger.last_execution_id.slice(0, 8)}
                    </Link>
                  ) : (
                    <span className="text-sm text-muted-foreground">-</span>
                  )}
                  <p className="text-xs text-muted-foreground">
                    {trigger.last_execution_status || "-"} {trigger.last_execution_duration_seconds != null ? `- ${formatDuration(trigger.last_execution_duration_seconds)}` : ""}
                  </p>
                </TD>
                <TD>
                  <div className="flex justify-end gap-1">
                    <Button size="icon" variant="ghost" onClick={() => onOpen(trigger)} title="Abrir detalhes">
                      <Eye className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost" onClick={() => onEdit(trigger)} title="Editar">
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost" onClick={() => onTest(trigger)} title="Testar mapeamento">
                      <FlaskConical className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost" onClick={() => onRotate(trigger)} title="Rotacionar secret">
                      <RotateCcw className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost" onClick={() => onToggle(trigger)} title={trigger.is_active ? "Desativar" : "Ativar"}>
                      <Power className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost" asChild title="Ver execucoes">
                      <Link href={`/executions?origin=trigger&trigger_id=${trigger.id}`}>
                        <History className="h-4 w-4" />
                      </Link>
                    </Button>
                    <Button size="icon" variant="ghost" onClick={() => onDelete(trigger)} title="Excluir">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </TD>
              </TR>
            );
          })}
        </TBody>
      </Table>
    </Card>
  );
}
