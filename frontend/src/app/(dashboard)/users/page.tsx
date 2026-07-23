import type { Metadata } from "next";

import { PageTitle } from "@/components/shared/page-title";
import { UsersManager } from "@/components/users/users-manager";

export const metadata: Metadata = { title: "Usuários" };

export default function UsersPage() {
  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Acesso" title="Usuários" description="Gestão de usuários, papéis e permissões por categoria." />
      <UsersManager />
    </div>
  );
}
