import Link from "next/link";
import { ChevronRight } from "lucide-react";

import { ExecutionDetail } from "@/components/executions/execution-detail";
import { PageTitle } from "@/components/shared/page-title";

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
      <PageTitle eyebrow="Detalhe" title={`Execucao #${id}`} description="Timeline, eventos, logs, metricas, processos, progresso, tasks e artefatos." />
      <ExecutionDetail id={id} />
    </div>
  );
}
