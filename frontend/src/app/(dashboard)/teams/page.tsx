import { UsersRound } from "lucide-react";

import { ComingSoonPage } from "@/components/shared/coming-soon";

export default function TeamsPage() {
  return (
    <ComingSoonPage
      eyebrow="Administração"
      title="Times"
      description="Times, membros e papéis atribuídos."
      phase="Fase 9 (Access e administração multi-organização)"
      icon={UsersRound}
    />
  );
}
