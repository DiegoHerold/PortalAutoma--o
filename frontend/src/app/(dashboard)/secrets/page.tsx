import { KeyRound } from "lucide-react";

import { ComingSoonPage } from "@/components/shared/coming-soon";

export default function SecretsPage() {
  return (
    <ComingSoonPage
      eyebrow="Governança"
      title="Segredos"
      description="Segredos, rotação e concessões de acesso (grants)."
      phase="Fase 8 (Governança)"
      icon={KeyRound}
    />
  );
}
