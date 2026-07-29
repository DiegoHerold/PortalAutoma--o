import { Package } from "lucide-react";

import { ComingSoonPage } from "@/components/shared/coming-soon";

export default function RuntimesPage() {
  return (
    <ComingSoonPage
      eyebrow="Catálogo"
      title="Runtimes"
      description="Runtimes, versões e compatibilidade com Agents."
      phase="Fase 7 (Runtimes e versões de automações)"
      icon={Package}
    />
  );
}
