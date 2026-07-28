import type { Metadata } from "next";

import { PageTitle } from "@/components/shared/page-title";
import { WorkersManager } from "@/components/workers/workers-manager";

export const metadata: Metadata = { title: "Workers" };

export default function WorkersPage() {
  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Infraestrutura" title="Workers" description="Máquinas executoras, capacidade e status ao vivo." />
      <WorkersManager />
    </div>
  );
}
