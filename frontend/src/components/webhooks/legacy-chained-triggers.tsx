"use client";

import Link from "next/link";
import { AlertTriangle, GitBranch, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { webhookStatusMeta } from "@/lib/status";
import { formatDateTime } from "@/lib/utils";
import type { Automation } from "@/types/automation";
import type { Trigger } from "@/types/trigger";

import { automationName, conditionLabel } from "./webhook-utils";

export function LegacyChainedTriggers({
  triggers,
  automations,
  onDisable,
  onDelete,
}: {
  triggers: Trigger[];
  automations: Automation[];
  onDisable: (trigger: Trigger) => void;
  onDelete: (trigger: Trigger) => void;
}) {
  if (triggers.length === 0) return null;
  const activeCount = triggers.filter((trigger) => trigger.is_active).length;

  return (
    <Card className="p-4">
      <div className="flex flex-col gap-3 border-b border-border pb-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="inline-flex items-center gap-2 font-display text-base font-semibold">
            <AlertTriangle className="h-4 w-4 text-warning" /> Gatilhos legados
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {triggers.length} registro(s) encontrados, {activeCount} ativo(s). Fluxos sao o mecanismo oficial para orquestracao entre automacoes.
          </p>
        </div>
        <Button variant="outline" asChild>
          <Link href="/flows">
            <GitBranch className="h-4 w-4" /> Abrir Fluxos
          </Link>
        </Button>
      </div>
      <Table>
        <THead>
          <TR>
            <TH>Origem</TH>
            <TH>Destino</TH>
            <TH>Condicao</TH>
            <TH>Status</TH>
            <TH>Última utilizacao</TH>
            <TH className="text-right">Ações</TH>
          </TR>
        </THead>
        <TBody>
          {triggers.map((trigger) => {
            const meta = webhookStatusMeta(trigger.is_active ? "legacy" : "inactive");
            const Icon = meta.icon;
            return (
              <TR key={trigger.id}>
                <TD>{trigger.source_automation_id ? automationName(automations, trigger.source_automation_id) : "Origem ausente"}</TD>
                <TD>{automationName(automations, trigger.automation_id)}</TD>
                <TD>{conditionLabel(trigger.condition)}</TD>
                <TD>
                  <Badge tone={meta.tone}>
                    <Icon className="h-3.5 w-3.5" /> {trigger.is_active ? "Legado ativo" : "Inativo"}
                  </Badge>
                </TD>
                <TD>{formatDateTime(trigger.last_invoked_at)}</TD>
                <TD>
                  <div className="flex justify-end gap-2">
                    <Button size="sm" variant="outline" asChild>
                      <Link href={`/flows?legacy_trigger_id=${trigger.id}`}>Criar Fluxo equivalente</Link>
                    </Button>
                    {trigger.is_active && (
                      <Button size="sm" variant="outline" onClick={() => onDisable(trigger)}>
                        Desativar
                      </Button>
                    )}
                    <Button size="icon" variant="ghost" onClick={() => onDelete(trigger)} title="Excluir após validação">
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
