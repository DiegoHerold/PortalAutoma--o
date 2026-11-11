import Link from "next/link";
import { ChevronRight, Radio } from "lucide-react";

import { ExecutionDetail } from "@/components/executions/execution-detail";
import { PageTitle } from "@/components/shared/page-title";
import { Button } from "@/components/ui/button";

export default async function ExecutionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="space-y-6">
      <nav className="flex items-center gap-1 text-sm text-muted-foreground">
        <Link href="/executions" className="hover:text-foreground">
          Execucoes
        </Link>
        <ChevronRight className="h-4 w-4" />
        <span className="tabular text-foreground">#{id}</span>
      </nav>
      <PageTitle
        eyebrow="Detalhe"
        title={`Execução #${id}`}
        description="Timeline, eventos, logs, métricas, processos, progresso, tasks e artefatos."
        actions={
          <Button size="sm" asChild>
            <Link href={`/execucoes/${id}`}>
              <Radio className="h-3.5 w-3.5" /> Acompanhar ao vivo
            </Link>
          </Button>
        }
      />
      <ExecutionDetail id={id} />
    </div>
  );
}
