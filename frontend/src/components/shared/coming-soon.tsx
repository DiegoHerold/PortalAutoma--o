import type { LucideIcon } from "lucide-react";
import { Construction } from "lucide-react";

import { PageTitle } from "@/components/shared/page-title";
import { EmptyState } from "@/components/shared/empty-state";

export function ComingSoonPage({
  eyebrow,
  title,
  description,
  phase,
  icon,
}: {
  eyebrow: string;
  title: string;
  description: string;
  phase: string;
  icon?: LucideIcon;
}) {
  return (
    <div className="space-y-6">
      <PageTitle eyebrow={eyebrow} title={title} description={description} />
      <EmptyState
        icon={icon ?? Construction}
        title="Em construção"
        description={`Esta área já existe no backend e será conectada ao frontend na ${phase}. Ela aparece aqui para refletir o mapa completo do Portal.`}
      />
    </div>
  );
}
