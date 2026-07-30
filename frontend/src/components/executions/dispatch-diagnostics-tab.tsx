"use client";

import { useState } from "react";
import { Info } from "lucide-react";

import { DispatchDecisionPanel } from "@/components/dispatch/dispatch-decision-panel";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { SectionCard } from "@/components/shared/section-card";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { formatDateTime } from "@/lib/utils";
import type { ExecutionDispatchInfo, ExecutionLeaseInfo, ExecutionLocksInfo, ExecutionReservationsInfo } from "@/types/execution";

type AttemptLike = { id: string; attempt_number?: number | null; agent_id?: string | null; status: string };

/**
 * Painéis técnicos de suporte para diagnosticar "por que essa tentativa está presa": decisões de
 * dispatch da execução inteira, e lease/reservas/locks de uma tentativa específica. Não duplica a
 * ação de retry — isso continua só na aba "Tasks" (AttemptsTab), aqui é só leitura.
 */
export function DispatchDiagnosticsTab({ executionId, attempts }: { executionId: string; attempts: AttemptLike[] }) {
  const sortedAttempts = [...attempts].sort((a, b) => (b.attempt_number ?? 0) - (a.attempt_number ?? 0));
  const [attemptId, setAttemptId] = useState<string>(sortedAttempts[0]?.id ?? "");

  const dispatch = useApi<ExecutionDispatchInfo>(`/executions/${executionId}/dispatch`);
  const lease = useApi<ExecutionLeaseInfo>(attemptId ? `/execution-attempts/${attemptId}/lease` : null, { enabled: !!attemptId });
  const reservations = useApi<ExecutionReservationsInfo>(attemptId ? `/execution-attempts/${attemptId}/reservations` : null, { enabled: !!attemptId });
  const locks = useApi<ExecutionLocksInfo>(attemptId ? `/execution-attempts/${attemptId}/locks` : null, { enabled: !!attemptId });

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-2 rounded-md border border-info/30 bg-info/5 p-3 text-xs text-muted-foreground">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-info" />
        <span>Painéis de suporte, só leitura — mostram como o agendador decidiu e o que está reservado/travado para esta execução.</span>
      </div>

      <SectionCard title="Decisões de dispatch">
        {dispatch.error ? (
          <ErrorState message={dispatch.error} onRetry={dispatch.refetch} />
        ) : dispatch.loading ? (
          <Skeleton className="h-32 rounded-lg" />
        ) : (dispatch.data?.decisions.length ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhuma decisão de dispatch registrada para esta execução ainda.</p>
        ) : (
          <div className="space-y-5">
            {dispatch.data!.decisions
              .slice()
              .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))
              .map((decision) => (
                <div key={decision.id} className="border-b border-border pb-5 last:border-0 last:pb-0">
                  <DispatchDecisionPanel decision={decision} />
                </div>
              ))}
          </div>
        )}
      </SectionCard>

      <SectionCard
        title="Lease, reservas e locks de uma tentativa"
        description="Escolha a tentativa (execution attempt) para inspecionar."
        actions={
          sortedAttempts.length > 0 ? (
            <Select value={attemptId} onChange={(e) => setAttemptId(e.target.value)} className="w-64">
              {sortedAttempts.map((attempt) => (
                <option key={attempt.id} value={attempt.id}>
                  #{attempt.attempt_number ?? "?"} — {attempt.id.slice(0, 12)} ({attempt.status})
                </option>
              ))}
            </Select>
          ) : undefined
        }
      >
        {sortedAttempts.length === 0 ? (
          <EmptyState title="Sem tentativas" description="Esta execução ainda não tem execution attempts." />
        ) : (
          <div className="grid gap-5 lg:grid-cols-3">
            <LeasePanel lease={lease} />
            <ReservationsPanel reservations={reservations} />
            <LocksPanel locks={locks} />
          </div>
        )}
      </SectionCard>
    </div>
  );
}

function LeasePanel({ lease }: { lease: ReturnType<typeof useApi<ExecutionLeaseInfo>> }) {
  if (lease.error) return <ErrorState message={lease.error} onRetry={lease.refetch} />;
  if (lease.loading) return <Skeleton className="h-32 rounded-lg" />;
  const item = lease.data?.lease;
  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Lease</h3>
      {!item ? (
        <p className="text-sm text-muted-foreground">Sem lease ativo.</p>
      ) : (
        <div className="space-y-1.5 rounded-md border border-border p-3 text-sm">
          <div className="flex items-center justify-between">
            <Badge tone={item.status === "active" ? "success" : item.status === "revoked" ? "destructive" : "neutral"}>{item.status}</Badge>
            <span className="tabular text-xs text-muted-foreground">renovação #{item.renewal_sequence}</span>
          </div>
          <p className="text-xs text-muted-foreground">Agent {item.agent_id.slice(0, 12)}</p>
          <p className="text-xs text-muted-foreground">Emitido {formatDateTime(item.issued_at)}</p>
          <p className="text-xs text-muted-foreground">Expira {formatDateTime(item.expires_at)}</p>
          <p className="text-xs text-muted-foreground">Tolerância até {formatDateTime(item.grace_until)}</p>
          {item.last_renewed_at && <p className="text-xs text-muted-foreground">Última renovação {formatDateTime(item.last_renewed_at)}</p>}
          {item.revoked_at && <p className="text-xs text-destructive">Revogado {formatDateTime(item.revoked_at)}: {item.revocation_reason ?? "sem motivo"}</p>}
        </div>
      )}
    </div>
  );
}

function ReservationsPanel({ reservations }: { reservations: ReturnType<typeof useApi<ExecutionReservationsInfo>> }) {
  if (reservations.error) return <ErrorState message={reservations.error} onRetry={reservations.refetch} />;
  if (reservations.loading) return <Skeleton className="h-32 rounded-lg" />;
  const items = reservations.data?.reservations ?? [];
  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Reservas de capacidade</h3>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sem reservas.</p>
      ) : (
        <div className="space-y-2">
          {items.map((reservation) => (
            <div key={reservation.id} className="space-y-1 rounded-md border border-border p-3 text-sm">
              <div className="flex items-center justify-between">
                <Badge tone={reservation.status === "active" ? "success" : reservation.status === "released" ? "neutral" : "warning"}>{reservation.status}</Badge>
                <span className="tabular text-xs text-muted-foreground">{reservation.pool_type}</span>
              </div>
              <p className="text-xs text-muted-foreground">{reservation.units} unidade(s) · Agent {reservation.agent_id.slice(0, 12)}</p>
              <p className="text-xs text-muted-foreground">Reservado {formatDateTime(reservation.reserved_at)}</p>
              {reservation.released_at && <p className="text-xs text-muted-foreground">Liberado {formatDateTime(reservation.released_at)}: {reservation.release_reason ?? "—"}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function LocksPanel({ locks }: { locks: ReturnType<typeof useApi<ExecutionLocksInfo>> }) {
  if (locks.error) return <ErrorState message={locks.error} onRetry={locks.refetch} />;
  if (locks.loading) return <Skeleton className="h-32 rounded-lg" />;
  const items = locks.data?.locks ?? [];
  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Locks de recurso</h3>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sem locks.</p>
      ) : (
        <div className="space-y-2">
          {items.map((lock) => (
            <div key={lock.id} className="space-y-1 rounded-md border border-border p-3 text-sm">
              <div className="flex items-center justify-between">
                <Badge tone={lock.status === "held" ? "warning" : "neutral"}>{lock.status}</Badge>
                <span className="text-xs text-muted-foreground">{lock.scope}</span>
              </div>
              <p className="tabular truncate text-xs text-muted-foreground" title={lock.resource_key}>
                {lock.resource_key}
              </p>
              <p className="text-xs text-muted-foreground">Adquirido {formatDateTime(lock.acquired_at)}</p>
              {lock.released_at && <p className="text-xs text-muted-foreground">Liberado {formatDateTime(lock.released_at)}: {lock.release_reason ?? "—"}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
