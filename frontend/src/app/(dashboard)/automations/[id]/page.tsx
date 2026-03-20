import { DetailJson } from "@/components/shared/detail-json";
import { DetailState } from "@/components/shared/detail-state";
import { PageTitle } from "@/components/shared/page-title";
import type { Automation } from "@/types/automation";

export default function AutomationDetailPage({ params }: { params: { id: string } }) {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Detalhe"
        title="Automacao"
        description="Visualize o payload completo da automacao selecionada."
      />
      <DetailState<Automation>
        path={`/automations/${encodeURIComponent(params.id)}`}
        loadingLabel="Carregando automacao..."
        render={(data) => <DetailJson data={data} />}
      />
    </div>
  );
}
