"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import { LoadingState } from "@/components/shared/loading-state";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type { Automation } from "@/types/automation";
import type { Trigger } from "@/types/trigger";

export function TriggersManager() {
  const { token } = useAuth();
  const [triggers, setTriggers] = useState<Trigger[]>([]);
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [form, setForm] = useState({
    automation_id: "",
    trigger_type: "https",
    route_path: "",
    secret_token: "",
    is_active: true,
  });
  const [loading, setLoading] = useState(true);

  async function load() {
    if (!token) return;
    setLoading(true);
    const [triggerData, automationData] = await Promise.all([
      apiRequest<Trigger[]>("/triggers", { token }),
      apiRequest<Automation[]>("/automations", { token }),
    ]);
    setTriggers(triggerData);
    setAutomations(automationData);
    if (!form.automation_id && automationData[0]) {
      setForm((current) => ({ ...current, automation_id: String(automationData[0].id) }));
    }
    setLoading(false);
  }

  useEffect(() => {
    void load();
  }, [token]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    await apiRequest<Trigger>("/triggers", {
      method: "POST",
      token,
      body: JSON.stringify({
        ...form,
        automation_id: Number(form.automation_id),
      }),
    });
    setForm({
      automation_id: "",
      trigger_type: "https",
      route_path: "",
      secret_token: "",
      is_active: true,
    });
    await load();
  }

  if (loading) return <LoadingState label="Carregando triggers..." />;

  return (
    <div className="space-y-6">
      <form className="grid gap-3 rounded-3xl bg-white/80 p-6 shadow-sm md:grid-cols-2" onSubmit={handleSubmit}>
        <select className="rounded-2xl border border-slate-200 px-4 py-3" value={form.automation_id} onChange={(event) => setForm({ ...form, automation_id: event.target.value })}>
          <option value="">Selecione uma automacao</option>
          {automations.map((automation) => (
            <option key={automation.id} value={automation.id}>
              {automation.name}
            </option>
          ))}
        </select>
        <input className="rounded-2xl border border-slate-200 px-4 py-3" placeholder="route_path" value={form.route_path} onChange={(event) => setForm({ ...form, route_path: event.target.value })} />
        <input className="rounded-2xl border border-slate-200 px-4 py-3 md:col-span-2" placeholder="secret_token" value={form.secret_token} onChange={(event) => setForm({ ...form, secret_token: event.target.value })} />
        <button className="rounded-2xl bg-ink px-4 py-3 text-sm font-semibold text-white md:col-span-2" type="submit">
          Criar trigger HTTPS
        </button>
      </form>
      <div className="grid gap-4">
        {triggers.map((trigger) => (
          <div key={trigger.id} className="rounded-3xl bg-white/80 p-5 shadow-sm">
            <p className="text-lg font-semibold">{trigger.route_path}</p>
            <p className="mt-1 text-sm text-slate-500">Automation #{trigger.automation_id}</p>
            <p className="mt-3 text-sm text-slate-600">Segredo: {trigger.secret_token}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
