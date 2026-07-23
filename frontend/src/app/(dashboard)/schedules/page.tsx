import type { Metadata } from "next";

import { PageTitle } from "@/components/shared/page-title";
import { SchedulesManager } from "@/components/schedules/schedules-manager";

export const metadata: Metadata = { title: "Agendamentos" };

export default function SchedulesPage() {
  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Agenda" title="Agendamentos" description="Execuções recorrentes por expressão cron." />
      <SchedulesManager />
    </div>
  );
}
