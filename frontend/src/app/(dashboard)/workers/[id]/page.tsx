import { DetailJson } from "@/components/shared/detail-json";
import { DetailState } from "@/components/shared/detail-state";
import { PageTitle } from "@/components/shared/page-title";
import type { Worker } from "@/types/worker";

export default function WorkerDetailPage({ params }: { params: { id: string } }) {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Detalhe"
        title="Worker"
        description="Visualize o estado atual do worker fake local."
      />
      <DetailState<Worker>
        path={`/workers/${encodeURIComponent(params.id)}`}
        loadingLabel="Carregando worker..."
        render={(data) => <DetailJson data={data} />}
      />
    </div>
  );
}
