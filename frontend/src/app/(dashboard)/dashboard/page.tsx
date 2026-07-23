import type { Metadata } from "next";

import { DashboardView } from "@/components/dashboard/dashboard-view";
import { PageTitle } from "@/components/shared/page-title";

export const metadata: Metadata = { title: "Dashboard" };

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Operação"
        title="Dashboard operacional"
        description="Filas, workers e execuções em tempo real."
      />
      <DashboardView />
    </div>
  );
}
