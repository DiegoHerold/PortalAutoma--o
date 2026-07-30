import { SystemLimitsView } from "@/components/governance/system-limits-view";
import { PageTitle } from "@/components/shared/page-title";

export default function GovernanceLimitsPage() {
  return <div className="space-y-6"><PageTitle eyebrow="Governança" title="Limites do sistema" description="Configurações livres consumidas pelos serviços do Portal." /><SystemLimitsView /></div>;
}
