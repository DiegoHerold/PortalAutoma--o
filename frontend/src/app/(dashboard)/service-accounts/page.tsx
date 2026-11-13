import { PageTitle } from "@/components/shared/page-title";
import { ServiceAccountsManager } from "@/components/service-accounts/service-accounts-manager";

export default function ServiceAccountsPage() {
  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Segurança" title="Contas de serviço"
        description="Credenciais para sistemas que chamam a API do Portal, com papel e times como uma pessoa." />
      <ServiceAccountsManager />
    </div>
  );
}
