import type { Metadata } from "next";

import { PageTitle } from "@/components/shared/page-title";
import { UsersManager } from "@/components/users/users-manager";

export const metadata: Metadata = { title: "Usuários" };

export default function UsersPage() {
  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Pessoas e acesso" title="Usuários" description="Cada pessoa tem um papel (quais telas usa) e times (em quais automações trabalha)." />
      <UsersManager />
    </div>
  );
}
