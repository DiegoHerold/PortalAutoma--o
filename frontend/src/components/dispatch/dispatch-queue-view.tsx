"use client";

import { useState } from "react";
import Link from "next/link";
import { ExternalLink, Info, RotateCw } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { useApi } from "@/hooks/use-api";
import { formatDateTime } from "@/lib/utils";
import type { TaskExecution } from "@/types/flow";

type DispatchQueueResponse = { items: TaskExecution[] };

const POLL = 5000;
const LIMIT_OPTIONS = [25, 50, 100, 200];

export function DispatchQueueView() {
  const [limit, setLimit] = useState(50);
  const queue = useApi<DispatchQueueResponse>(`/dispatch/queue?limit=${limit}`, { pollMs: POLL });

  if (queue.error) return <ErrorState message={queue.error} onRetry={queue.refetch} />;

  const items = queue.data?.items ?? [];

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-2 rounded-md border border-info/30 bg-info/5 p-3 text-xs text-muted-foreground">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-info" />
        <span>
          Isto é uma <strong>foto instantânea</strong> das tasks prontas para despacho no momento da consulta — não é uma fila travada nem editável pelo
          Portal. O backend calcula (<code className="tabular">claim_ready</code>) e imediatamente desfaz a reserva (<code className="tabular">rollback</code>
          ) só para gerar esta visão; o agendador real roda de forma independente.
        </span>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Select value={limit} onChange={(e) => setLimit(Number(e.target.value))} className="w-32">
            {LIMIT_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt} itens
              </option>
            ))}
          </Select>
          <span className="text-xs text-muted-foreground">{items.length} na fila agora</span>
        </div>
        <Button variant="outline" size="sm" onClick={queue.refetch}>
          <RotateCw className="h-3.5 w-3.5" /> Atualizar
        </Button>
      </div>

      {queue.loading ? (
        <Skeleton className="h-64 rounded-lg" />
      ) : items.length === 0 ? (
        <EmptyState title="Fila vazia" description="Nenhuma task pronta para despacho neste momento." />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <Table>
            <THead>
              <TR>
                <TH>Task</TH>
                <TH>Status</TH>
                <TH>Prioridade</TH>
                <TH>Tentativas de agendamento</TH>
                <TH>Próxima tentativa</TH>
                <TH>Disponível desde</TH>
                <TH />
              </TR>
            </THead>
            <TBody>
              {items.map((task) => (
                <TR key={task.id}>
                  <TD>
                    <span className="tabular text-sm font-medium">{task.id.slice(0, 12)}</span>
                    <span className="tabular block text-xs text-muted-foreground">exec {task.execution_id.slice(0, 12)}</span>
                  </TD>
                  <TD>
                    <StatusBadge status={task.status} />
                  </TD>
                  <TD className="tabular text-sm">{task.priority}</TD>
                  <TD className="tabular text-sm text-muted-foreground">{task.scheduling_attempts}</TD>
                  <TD className="tabular text-sm text-muted-foreground">{formatDateTime(task.next_scheduling_attempt_at)}</TD>
                  <TD className="tabular text-sm text-muted-foreground">{formatDateTime(task.available_at ?? task.created_at)}</TD>
                  <TD>
                    <Link href={`/executions/${task.execution_id}?tab=diagnostico`} className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
                      Diagnóstico <ExternalLink className="h-3 w-3" />
                    </Link>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </div>
      )}
    </div>
  );
}
