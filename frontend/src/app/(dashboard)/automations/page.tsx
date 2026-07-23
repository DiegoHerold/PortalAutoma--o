import type { Metadata } from "next";

import { AutomationsManager } from "@/components/automations/automations-manager";
import { PageTitle } from "@/components/shared/page-title";

export const metadata: Metadata = { title: "Automações" };

export default function AutomationsPage() {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Catálogo"
        title="Automações"
        description="Cadastro, organização por categoria e preferência de workers."
      />
      <AutomationsManager />
    </div>
  );
}
