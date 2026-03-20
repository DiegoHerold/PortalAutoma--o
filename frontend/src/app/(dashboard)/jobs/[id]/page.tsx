import { DetailJson } from "@/components/shared/detail-json";
import { DetailState } from "@/components/shared/detail-state";
import { PageTitle } from "@/components/shared/page-title";
import type { Job } from "@/types/job";

export default function JobDetailPage({ params }: { params: { id: string } }) {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Detalhe"
        title="Job"
        description="Visualize o estado persistido do job selecionado."
      />
      <DetailState<Job>
        path={`/jobs/${encodeURIComponent(params.id)}`}
        loadingLabel="Carregando job..."
        render={(data) => <DetailJson data={data} />}
      />
    </div>
  );
}
