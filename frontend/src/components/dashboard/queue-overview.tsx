// Deprecated: the dashboard queue view now lives in "@/components/dashboard/dashboard-view".
// Kept as a thin, token-based placeholder for backward compatibility.
import { SectionCard } from "@/components/shared/section-card";
import { PriorityBadge } from "@/components/ui/status-badge";

export function QueueOverview() {
  return (
    <SectionCard title="Visão da fila">
      <div className="grid gap-3 md:grid-cols-4">
        {["critical", "high", "normal", "low"].map((queue) => (
          <div key={queue} className="rounded-lg border border-border bg-muted/40 p-4">
            <PriorityBadge priority={queue} />
            <p className="tabular mt-2 text-2xl font-semibold">0</p>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
