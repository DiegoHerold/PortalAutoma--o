import { PageTitle } from "@/components/shared/page-title";
import { ServiceAccountsManager } from "@/components/service-accounts/service-accounts-manager";

export default function ServiceAccountsPage() {
  return <div className="space-y-6"><PageTitle eyebrow="Administracao" title="Contas de servico" description="Identidades de maquina com permissoes e credenciais de exibicao unica." /><ServiceAccountsManager /></div>;
}
