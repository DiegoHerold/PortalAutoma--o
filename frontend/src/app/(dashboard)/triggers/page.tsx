import { PageTitle } from "@/components/shared/page-title";
import { TriggersManager } from "@/components/triggers/triggers-manager";

export default function TriggersPage() {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Entrada"
        title="Triggers"
        description="Crie e visualize gatilhos HTTPS para disparar automacoes externamente."
      />
      <TriggersManager />
    </div>
  );
}
