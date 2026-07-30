"use client";

import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/utils";
import type { ExecutionDispatchDecision } from "@/types/execution";

/** Renderiza uma decisão de dispatch (candidatos avaliados, pesos, motivo) — usado tanto na fila quanto no diagnóstico de execução. */
export function DispatchDecisionPanel({ decision }: { decision: ExecutionDispatchDecision }) {
  const candidates = (decision.candidates ?? []).slice().sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={decisionStatusTone(decision.status)}>{decision.status}</Badge>
        {decision.selected_agent_id && <Badge tone="info">Selecionado: {decision.selected_agent_id}</Badge>}
        <span className="text-xs text-muted-foreground">{formatDateTime(decision.created_at)}</span>
      </div>

      {decision.decision_reason && <p className="text-sm text-muted-foreground">{decision.decision_reason}</p>}

      {decision.weights && Object.keys(decision.weights).length > 0 && (
        <div className="flex flex-wrap gap-1.5 text-xs text-muted-foreground">
          {Object.entries(decision.weights).map(([key, value]) => (
            <span key={key} className="rounded-full bg-muted px-2 py-0.5">
              {key}: {value}
            </span>
          ))}
        </div>
      )}

      {candidates.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhum candidato avaliado.</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left">Agent</th>
                <th className="px-3 py-2 text-left">Elegível</th>
                <th className="px-3 py-2 text-left">Score</th>
                <th className="px-3 py-2 text-left">Motivo (se rejeitado)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {candidates.map((candidate) => (
                <tr key={`${candidate.agent_id}-${candidate.agent_instance_id ?? ""}`} className={candidate.agent_id === decision.selected_agent_id ? "bg-primary/5" : undefined}>
                  <td className="tabular px-3 py-2 text-xs">{candidate.agent_id}</td>
                  <td className="px-3 py-2">
                    <Badge tone={candidate.eligible ? "success" : "neutral"}>{candidate.eligible ? "sim" : "não"}</Badge>
                  </td>
                  <td className="tabular px-3 py-2">{candidate.score?.toFixed(2) ?? "—"}</td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {(candidate.rejection_reasons ?? []).map((reason, idx) => (
                      <div key={idx}>{JSON.stringify(reason)}</div>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function decisionStatusTone(status: string): "success" | "neutral" | "destructive" | "warning" | "info" {
  if (status === "committed" || status === "succeeded") return "success";
  if (status === "failed" || status === "rejected") return "destructive";
  if (status === "pending" || status === "evaluating") return "warning";
  return "neutral";
}
