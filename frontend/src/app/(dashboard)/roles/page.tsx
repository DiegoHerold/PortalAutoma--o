import { PageTitle } from "@/components/shared/page-title";
import { RolesManager } from "@/components/roles/roles-manager";

export default function RolesPage() {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Governanca"
        title="Papeis Globais"
        description="Visualize os papeis globais que definem o alcance operacional dos usuarios."
      />
      <RolesManager />
    </div>
  );
}
