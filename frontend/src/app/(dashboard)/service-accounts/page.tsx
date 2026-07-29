import { IdCard } from "lucide-react";

import { ComingSoonPage } from "@/components/shared/coming-soon";

export default function ServiceAccountsPage() {
  return (
    <ComingSoonPage
      eyebrow="Administração"
      title="Contas de serviço"
      description="Credenciais de máquina a máquina, permissões e rotação."
      phase="Fase 9 (Access e administração multi-organização)"
      icon={IdCard}
    />
  );
}
