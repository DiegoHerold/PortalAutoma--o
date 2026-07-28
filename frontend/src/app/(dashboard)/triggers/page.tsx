import type { Metadata } from "next";

import { PageTitle } from "@/components/shared/page-title";
import { TriggersManager } from "@/components/triggers/triggers-manager";

export const metadata: Metadata = { title: "Gatilhos" };

export default function TriggersPage() {
  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Entrada" title="Gatilhos" description="Webhooks HTTP para disparar automações externamente." />
      <TriggersManager />
    </div>
  );
}
