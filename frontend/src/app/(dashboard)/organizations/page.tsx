import { OrganizationsManager } from "@/components/organizations/organizations-manager";
import { PageTitle } from "@/components/shared/page-title";

export default function OrganizationsPage() {
  return <div className="space-y-6"><PageTitle eyebrow="Pessoas e acesso" title="Organizações" description="Contextos administrativos para times, segredos e configurações." /><OrganizationsManager /></div>;
}
