import { SecretsManager } from "@/components/secrets/secrets-manager";
import { PageTitle } from "@/components/shared/page-title";

export default function SecretsPage() {
  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Segurança" title="Segredos"
        description="Senhas e chaves que as automações recebem do Portal durante a execução. O valor nunca é mostrado." />
      <SecretsManager />
    </div>
  );
}
