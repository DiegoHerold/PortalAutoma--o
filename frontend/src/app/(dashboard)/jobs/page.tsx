import { JobsManager } from "@/components/jobs/jobs-manager";
import { PageTitle } from "@/components/shared/page-title";

export default function JobsPage() {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Fila"
        title="Jobs"
        description="Acompanhe criacao, despacho e status de execucao por prioridade."
      />
      <JobsManager />
    </div>
  );
}
