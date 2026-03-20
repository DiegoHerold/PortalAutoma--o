import { PageTitle } from "@/components/shared/page-title";
import { UsersManager } from "@/components/users/users-manager";

export default function UsersPage() {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Acesso"
        title="Usuarios"
        description="Base para gestao de usuarios, papeis globais e permissoes por categoria."
      />
      <UsersManager />
    </div>
  );
}
