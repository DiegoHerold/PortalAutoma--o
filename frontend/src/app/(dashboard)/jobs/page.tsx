import type { Metadata } from "next";

import { JobsManager } from "@/components/jobs/jobs-manager";
import { PageTitle } from "@/components/shared/page-title";

export const metadata: Metadata = { title: "Fila de jobs" };

export default function JobsPage() {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Fila"
        title="Jobs"
        description="Despacho, prioridade e estimativa de início e término em tempo real."
      />
      <JobsManager />
    </div>
  );
}
