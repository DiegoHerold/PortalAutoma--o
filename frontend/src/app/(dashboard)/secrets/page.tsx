import { SecretsManager } from "@/components/secrets/secrets-manager";
import { PageTitle } from "@/components/shared/page-title";

export default function SecretsPage() {
  return <div className="space-y-6"><PageTitle eyebrow="Segurança" title="Segredos" description="Metadados, rotação e concessões de acesso. Valores protegidos não podem ser consultados." /><SecretsManager /></div>;
}
