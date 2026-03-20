import { SectionCard } from "@/components/shared/section-card";

export function QueueOverview() {
  return (
    <SectionCard title="Visao da fila">
      <div className="grid gap-3 md:grid-cols-4">
        {["critical", "high", "normal", "low"].map((queue) => (
          <div key={queue} className="rounded-2xl bg-mist p-4">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{queue}</p>
            <p className="mt-2 text-2xl font-semibold">0</p>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
