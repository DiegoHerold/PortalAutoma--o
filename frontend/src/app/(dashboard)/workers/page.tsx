import type { Metadata } from "next";

import { PageTitle } from "@/components/shared/page-title";
import { AgentsManager } from "@/components/agents/agents-manager";

export const metadata: Metadata = { title: "Agents" };

export default function WorkersPage() {
  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Infraestrutura" title="Agents" description="Máquinas executoras, capacidade, diagnóstico e credenciais." />
      <AgentsManager />
    </div>
  );
}
