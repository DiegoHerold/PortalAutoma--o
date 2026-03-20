import { DetailJson } from "@/components/shared/detail-json";
import { DetailState } from "@/components/shared/detail-state";
import { PageTitle } from "@/components/shared/page-title";
import type { Execution } from "@/types/execution";

export default function ExecutionDetailPage({ params }: { params: { id: string } }) {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Detalhe"
        title="Execucao"
        description="Visualize logs e resultado persistido da execucao."
      />
      <DetailState<Execution>
        path={`/executions/${encodeURIComponent(params.id)}`}
        loadingLabel="Carregando execucao..."
        render={(data) => <DetailJson data={data} />}
      />
    </div>
  );
}
