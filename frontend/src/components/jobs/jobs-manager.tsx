"use client";

import { useEffect, useState } from "react";

import { JobsTable } from "@/components/jobs/jobs-table";
import { LoadingState } from "@/components/shared/loading-state";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type { Automation } from "@/types/automation";
import type { Job } from "@/types/job";

export function JobsManager() {
  const { token } = useAuth();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [automationId, setAutomationId] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    if (!token) return;
    setLoading(true);
    const [jobData, automationData] = await Promise.all([
      apiRequest<Job[]>("/jobs", { token }),
      apiRequest<Automation[]>("/automations", { token }),
    ]);
    setJobs(jobData);
    setAutomations(automationData);
    if (!automationId && automationData[0]) {
      setAutomationId(String(automationData[0].id));
    }
    setLoading(false);
  }

  useEffect(() => {
    void load();
  }, [token]);

  async function dispatchJob() {
    if (!token || !automationId) return;
    await apiRequest<Job>("/jobs", {
      method: "POST",
      token,
      body: JSON.stringify({
        automation_id: Number(automationId),
        priority: "normal",
        payload_json: { source: "portal-ui" },
      }),
    });
    await load();
  }

  if (loading) return <LoadingState label="Carregando jobs..." />;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 rounded-3xl bg-white/80 p-6 shadow-sm md:flex-row">
        <select className="rounded-2xl border border-slate-200 px-4 py-3" value={automationId} onChange={(event) => setAutomationId(event.target.value)}>
          <option value="">Selecione uma automacao</option>
          {automations.map((automation) => (
            <option key={automation.id} value={automation.id}>
              {automation.name}
            </option>
          ))}
        </select>
        <button className="rounded-2xl bg-accent px-4 py-3 text-sm font-semibold text-white" onClick={() => void dispatchJob()} type="button">
          Disparar job fake
        </button>
      </div>
      <JobsTable jobs={jobs} />
    </div>
  );
}
