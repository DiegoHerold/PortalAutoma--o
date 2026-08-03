import type { Metadata } from "next";

import { WebhooksPage } from "@/components/webhooks/webhooks-page";

export const metadata: Metadata = { title: "Webhooks" };

export default function WebhooksRoutePage() {
  return (
    <div>
      <WebhooksPage />
    </div>
  );
}
