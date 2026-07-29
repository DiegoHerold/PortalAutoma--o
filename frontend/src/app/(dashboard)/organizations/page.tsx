import { Building2 } from "lucide-react";

import { ComingSoonPage } from "@/components/shared/coming-soon";

export default function OrganizationsPage() {
  return (
    <ComingSoonPage
      eyebrow="Administração"
      title="Organizações"
      description="Organizações, limites e atividade multi-tenant."
      phase="Fase 9 (Access e administração multi-organização)"
      icon={Building2}
    />
  );
}
