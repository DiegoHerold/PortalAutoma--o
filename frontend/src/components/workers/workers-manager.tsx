"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { LoadingState } from "@/components/shared/loading-state";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type { Worker } from "@/types/worker";

export function WorkersManager() {
  const { token } = useAuth();
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    apiRequest<Worker[]>("/workers", { token })
      .then(setWorkers)
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <LoadingState label="Carregando workers..." />;

  return (
    <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white/80 shadow-sm">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-left text-slate-500">
          <tr>
            <th className="px-4 py-3">Nome</th>
            <th className="px-4 py-3">Hostname</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Concorrencia</th>
            <th className="px-4 py-3"></th>
          </tr>
        </thead>
        <tbody>
          {workers.map((worker) => (
            <tr key={worker.id} className="border-t border-slate-100">
              <td className="px-4 py-3">{worker.name}</td>
              <td className="px-4 py-3">{worker.hostname}</td>
              <td className="px-4 py-3">{worker.status}</td>
              <td className="px-4 py-3">{worker.max_concurrency}</td>
              <td className="px-4 py-3 text-right">
                <Link className="text-accent" href={`/workers/${worker.id}`}>
                  Detalhes
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
