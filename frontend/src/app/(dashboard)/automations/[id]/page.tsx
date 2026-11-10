import Link from "next/link";
import { ChevronRight, ShieldCheck } from "lucide-react";

import { AutomationDetail } from "@/components/automations/automation-detail";
import { PageTitle } from "@/components/shared/page-title";
import { Button } from "@/components/ui/button";

export default async function AutomationDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="space-y-6">
      <nav className="flex items-center gap-1 text-sm text-muted-foreground">
        <Link href="/automations" className="hover:text-foreground">
          Automações
        </Link>
        <ChevronRight className="h-4 w-4" />
        <span className="tabular text-foreground">#{id}</span>
      </nav>
      <PageTitle
        eyebrow="Detalhe"
        title="Automação"
        description="Configuração, gatilhos, agendamentos e preferência de workers."
        actions={
          <Button size="sm" variant="outline" asChild>
            <Link href={`/automations/${id}/acessos`}>
              <ShieldCheck className="h-3.5 w-3.5" /> Acesso a telas e logs
            </Link>
          </Button>
        }
      />
      <AutomationDetail id={id} />
    </div>
  );
}
