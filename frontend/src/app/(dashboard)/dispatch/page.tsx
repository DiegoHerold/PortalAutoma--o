import type { Metadata } from "next";

import { DispatchQueueView } from "@/components/dispatch/dispatch-queue-view";
import { PageTitle } from "@/components/shared/page-title";

export const metadata: Metadata = { title: "Fila de execução" };

export default function DispatchPage() {
  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Infraestrutura" title="Fila de execução" description="Snapshot de tasks prontas para despacho e decisões de scheduling." />
      <DispatchQueueView />
    </div>
  );
}
