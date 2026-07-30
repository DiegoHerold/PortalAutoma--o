import type { Metadata } from "next";

import { RuntimesManager } from "@/components/runtimes/runtimes-manager";
import { PageTitle } from "@/components/shared/page-title";

export const metadata: Metadata = { title: "Runtimes" };

export default function RuntimesPage() {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Catalogo"
        title="Runtimes"
        description="Gestao de runtimes, versoes publicadas e compatibilidade informativa com Agents."
      />
      <RuntimesManager />
    </div>
  );
}

