import { LimpezaDoSistema } from "@/components/governance/limpeza-do-sistema";
import { RetencaoPorAutomacao } from "@/components/governance/retencao-por-automacao";
import { PageTitle } from "@/components/shared/page-title";

export default function GovernanceRetentionPage() {
  return (
    <div className="space-y-12">
      <PageTitle eyebrow="Governança" title="Retenção"
        description="Por quanto tempo o Portal guarda cada coisa: os registros do sistema e as imagens, logs e arquivos de cada automação." />
      <LimpezaDoSistema />
      <RetencaoPorAutomacao />
    </div>
  );
}
