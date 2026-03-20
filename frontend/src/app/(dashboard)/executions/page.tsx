import { ExecutionsManager } from "@/components/executions/executions-manager";
import { PageTitle } from "@/components/shared/page-title";

export default function ExecutionsPage() {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Historico"
        title="Execucoes"
        description="Acompanhe o resultado da execucao fake persistida no banco com logs e resumo."
      />
      <ExecutionsManager />
    </div>
  );
}
