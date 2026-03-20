import { PageTitle } from "@/components/shared/page-title";
import { SchedulesManager } from "@/components/schedules/schedules-manager";

export default function SchedulesPage() {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Agenda"
        title="Schedules"
        description="Consulte os agendamentos conhecidos pelo backend."
      />
      <SchedulesManager />
    </div>
  );
}
