"use client";

import { useEffect, useState } from "react";

import { EmptyState } from "@/components/shared/empty-state";
import { LoadingState } from "@/components/shared/loading-state";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type { Schedule } from "@/types/schedule";

export function SchedulesManager() {
  const { token } = useAuth();
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    apiRequest<Schedule[]>("/schedules", { token })
      .then(setSchedules)
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <LoadingState label="Carregando schedules..." />;
  if (schedules.length === 0) {
    return (
      <EmptyState
        title="Nenhum schedule cadastrado"
        description="A API ja expoe a listagem e o proximo passo natural e adicionar criacao e edicao de agendamentos."
      />
    );
  }

  return (
    <div className="grid gap-4">
      {schedules.map((schedule) => (
        <div key={schedule.id} className="rounded-3xl bg-white/80 p-5 shadow-sm">
          <p className="text-lg font-semibold">Automation #{schedule.automation_id}</p>
          <p className="mt-1 text-sm text-slate-500">{schedule.cron_expression}</p>
          <p className="mt-3 text-sm text-slate-600">{schedule.timezone}</p>
        </div>
      ))}
    </div>
  );
}
