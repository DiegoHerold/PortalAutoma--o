import { AutomationsManager } from "@/components/automations/automations-manager";
import { PageTitle } from "@/components/shared/page-title";

export default function AutomationsPage() {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Catalogo"
        title="Automacoes"
        description="Cadastro, organizacao por categoria e disparo manual de automacoes."
      />
      <AutomationsManager />
    </div>
  );
}
