import { LimitesDoSistema } from "@/components/governance/limites-do-sistema";
import { PageTitle } from "@/components/shared/page-title";

export default function GovernanceLimitsPage() {
  return (
    <div className="space-y-8">
      <PageTitle eyebrow="Governança" title="Limites do sistema"
        description="Os tetos que protegem o Portal e as máquinas. Cada limite diz onde vale; mudar vale na hora." />
      <LimitesDoSistema />
    </div>
  );
}
