import { RetencaoPorAutomacao } from "@/components/governance/retencao-por-automacao";
import { RetentionPoliciesView } from "@/components/governance/retention-policies-view";
import { PageTitle } from "@/components/shared/page-title";

export default function GovernanceRetentionPage() {
  return (
    <div className="space-y-10">
      <PageTitle eyebrow="Governança" title="Retenção" description="Por quanto tempo o portal guarda imagens, logs, arquivos entregues e os demais registros." />
      <RetencaoPorAutomacao />
      <section className="space-y-4">
        <div>
          <h2 className="titulo-condensado text-2xl">Políticas por tipo de registro</h2>
          <p className="max-w-3xl text-muted-foreground">
            Referência de prazos por tipo de registro e retenção legal. Hoje estas políticas não apagam nada sozinhas: a
            exclusão automática vale só para imagens, logs e arquivos entregues, por automação, acima.
          </p>
        </div>
        <RetentionPoliciesView />
      </section>
    </div>
  );
}
