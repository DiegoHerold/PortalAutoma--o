import type { Metadata } from "next";

import { AuditView } from "@/components/audit/audit-view";
import { PageTitle } from "@/components/shared/page-title";

export const metadata: Metadata = { title: "Auditoria" };

export default function AuditPage() {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Governança"
        title="Auditoria"
        description="Trilha de eventos: quem fez o quê, quando, com diff antes/depois."
      />
      <AuditView />
    </div>
  );
}
