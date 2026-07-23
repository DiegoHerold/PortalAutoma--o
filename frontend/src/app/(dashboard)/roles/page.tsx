import type { Metadata } from "next";

import { PageTitle } from "@/components/shared/page-title";
import { RolesManager } from "@/components/roles/roles-manager";

export const metadata: Metadata = { title: "Papéis" };

export default function RolesPage() {
  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Governança" title="Papéis globais" description="Papéis que definem o alcance operacional dos usuários." />
      <RolesManager />
    </div>
  );
}
