import type { Metadata } from "next";

import { PageTitle } from "@/components/shared/page-title";
import { RolesManager } from "@/components/roles/roles-manager";

export const metadata: Metadata = { title: "Papéis" };

export default function RolesPage() {
  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Pessoas e acesso" title="Papéis globais" description="Cada papel diz quais abas as pessoas veem. Só administradores mudam." />
      <RolesManager />
    </div>
  );
}
