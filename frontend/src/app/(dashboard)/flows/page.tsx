import { FlowsManager } from "@/components/flows/flows-manager";
import { PageTitle } from "@/components/shared/page-title";

export default function FlowsPage() {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Operação"
        title="Fluxos"
        description="Orquestre automações com dependências, condições e acompanhamento visual em tempo real."
      />
      <FlowsManager />
    </div>
  );
}
