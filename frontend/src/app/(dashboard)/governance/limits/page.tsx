import { Gauge } from "lucide-react";

import { ComingSoonPage } from "@/components/shared/coming-soon";

export default function GovernanceLimitsPage() {
  return (
    <ComingSoonPage
      eyebrow="Governança"
      title="Limites do sistema"
      description="Limites por execuções, Agents, fluxos, agendamentos, uploads, webhooks, retenção e realtime."
      phase="Fase 8 (Governança)"
      icon={Gauge}
    />
  );
}
