import type { Metadata } from "next";

import { EmailsPage } from "@/components/emails/emails-page";

export const metadata: Metadata = { title: "E-mails" };

export default function EmailsRoutePage() {
  return <EmailsPage />;
}
