import type { Metadata } from "next";
import { Suspense } from "react";

import { AuditoriaView } from "@/components/audit/auditoria-view";
import { PageTitle } from "@/components/shared/page-title";

export const metadata: Metadata = { title: "Auditoria" };

export default function AuditPage() {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Segurança"
        title="Auditoria"
        description="Tudo o que acontece no Portal, em ordem. Clique num evento para ver o que mudou e o que veio junto; clique no nome de alguém para ver só essa pessoa."
      />
      <Suspense fallback={<div className="skeleton h-96 rounded-xl" />}>
        <AuditoriaView />
      </Suspense>
    </div>
  );
}
