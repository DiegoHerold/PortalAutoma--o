import type { Automation } from "@/types/automation";

export function AutomationCard({ automation }: { automation: Automation }) {
  return (
    <div className="rounded-3xl border border-slate-200 bg-white/80 p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold">{automation.name}</h3>
          <p className="mt-1 text-sm text-slate-500">{automation.slug}</p>
        </div>
        <span className="rounded-full bg-mist px-3 py-1 text-xs font-medium uppercase text-accent">
          {automation.default_priority}
        </span>
      </div>
      <p className="mt-4 text-sm text-slate-600">{automation.description ?? "Sem descricao cadastrada."}</p>
    </div>
  );
}
