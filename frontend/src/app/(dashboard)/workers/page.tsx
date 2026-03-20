import { PageTitle } from "@/components/shared/page-title";
import { WorkersManager } from "@/components/workers/workers-manager";

export default function WorkersPage() {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Infra"
        title="Workers"
        description="Monitore as maquinas executoras, concorrencia e status operacional."
      />
      <WorkersManager />
    </div>
  );
}
