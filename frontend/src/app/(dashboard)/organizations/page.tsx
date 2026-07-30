import { OrganizationsManager } from "@/components/organizations/organizations-manager";
import { PageTitle } from "@/components/shared/page-title";

export default function OrganizationsPage() {
  return <div className="space-y-6"><PageTitle eyebrow="Administracao" title="Organizacoes" description="Contextos administrativos para times, secrets e configuracoes." /><OrganizationsManager /></div>;
}
