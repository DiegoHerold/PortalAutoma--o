import { QueueOverview } from "@/components/dashboard/queue-overview";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { WorkersSummary } from "@/components/dashboard/workers-summary";
import { PageTitle } from "@/components/shared/page-title";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Controle"
        title="Dashboard operacional"
        description="Visao inicial do ambiente com filas por prioridade, workers e capacidade para crescimento distribuido."
      />
      <StatsCards />
      <QueueOverview />
      <WorkersSummary />
    </div>
  );
}
