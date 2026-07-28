import { Suspense } from "react";

import { PageTitle } from "@/components/shared/page-title";
import { GithubIntegrationsPanel } from "@/components/settings/github-integrations-panel";

export default function IntegrationsSettingsPage() {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Preferências"
        title="Integrações"
        description="Conexões externas usadas para importar automações."
      />
      <Suspense>
        <GithubIntegrationsPanel />
      </Suspense>
    </div>
  );
}
