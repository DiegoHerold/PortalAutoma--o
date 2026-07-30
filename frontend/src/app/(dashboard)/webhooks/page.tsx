import type { Metadata } from "next";

import { PageTitle } from "@/components/shared/page-title";
import { WebhooksPage } from "@/components/webhooks/webhooks-page";

export const metadata: Metadata = { title: "Webhooks" };

export default function WebhooksRoutePage() {
  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Entrada" title="Webhooks" description="Webhooks HTTP para receber chamadas externas e iniciar Execucoes oficiais." />
      <WebhooksPage />
    </div>
  );
}
