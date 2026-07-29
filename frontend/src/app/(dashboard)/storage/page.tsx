import { Database } from "lucide-react";

import { ComingSoonPage } from "@/components/shared/coming-soon";

export default function StoragePage() {
  return (
    <ComingSoonPage
      eyebrow="Infraestrutura"
      title="Armazenamento"
      description="Artefatos gerados por execuções e fluxos."
      phase="Fase 8 (Governança e armazenamento)"
      icon={Database}
    />
  );
}
