import type { Metadata } from "next";

import { ExecutionsManager } from "@/components/executions/executions-manager";
import { PageTitle } from "@/components/shared/page-title";

export const metadata: Metadata = { title: "Execucoes" };

export default function ExecutionsPage() {
  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Historico" title="Execucoes" description="Automacoes e Fluxos com timeline, telemetria e artefatos." />
      <ExecutionsManager />
    </div>
  );
}
