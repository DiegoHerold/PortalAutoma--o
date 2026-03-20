"use client";

import { useEffect, useState } from "react";

import { LoadingState } from "@/components/shared/loading-state";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type { Execution } from "@/types/execution";

export function ExecutionsManager() {
  const { token } = useAuth();
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    apiRequest<Execution[]>("/executions", { token })
      .then(setExecutions)
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <LoadingState label="Carregando execucoes..." />;

  return (
    <div className="space-y-4">
      {executions.map((execution) => (
        <div key={execution.id} className="rounded-3xl bg-white/80 p-5 shadow-sm">
          <div className="flex items-center justify-between gap-4">
            <h3 className="text-lg font-semibold">Execucao #{execution.id}</h3>
            <span className="rounded-full bg-mist px-3 py-1 text-xs font-semibold uppercase">
              {execution.execution_status}
            </span>
          </div>
          <p className="mt-3 text-sm text-slate-600">{execution.result_summary ?? "Sem resumo."}</p>
          <div className="mt-4 space-y-2">
            {execution.logs?.map((log) => (
              <div key={log.id} className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
                <span className="font-semibold">{log.level}</span>: {log.message}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
