import { ListOrdered } from "lucide-react";

import { ComingSoonPage } from "@/components/shared/coming-soon";

export default function DispatchPage() {
  return (
    <ComingSoonPage
      eyebrow="Infraestrutura"
      title="Fila de execução"
      description="Fila de dispatch, decisões de scheduling e candidatos avaliados."
      phase="Fase 6 (Administração avançada de Agents e Dispatch)"
      icon={ListOrdered}
    />
  );
}
