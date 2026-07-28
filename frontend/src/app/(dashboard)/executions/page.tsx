import type { Metadata } from "next";

import { ExecutionsManager } from "@/components/executions/executions-manager";
import { PageTitle } from "@/components/shared/page-title";

export const metadata: Metadata = { title: "Execuções" };

export default function ExecutionsPage() {
  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Histórico" title="Execuções" description="Resultado, logs e duração de cada execução." />
      <ExecutionsManager />
    </div>
  );
}
