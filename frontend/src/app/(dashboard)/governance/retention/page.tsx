import { Archive } from "lucide-react";

import { ComingSoonPage } from "@/components/shared/coming-soon";

export default function GovernanceRetentionPage() {
  return (
    <ComingSoonPage
      eyebrow="Governança"
      title="Retenção"
      description="Políticas de retenção, arquivamento e exclusão por tipo de dado."
      phase="Fase 8 (Governança)"
      icon={Archive}
    />
  );
}
