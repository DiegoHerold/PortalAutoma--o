import Link from "next/link";
import { ChevronRight } from "lucide-react";

import { WorkerDetail } from "@/components/workers/worker-detail";
import { PageTitle } from "@/components/shared/page-title";

export default async function WorkerDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="space-y-6">
      <nav className="flex items-center gap-1 text-sm text-muted-foreground">
        <Link href="/workers" className="hover:text-foreground">
          Workers
        </Link>
        <ChevronRight className="h-4 w-4" />
        <span className="tabular text-foreground">#{id}</span>
      </nav>
      <PageTitle eyebrow="Detalhe" title={`Worker #${id}`} description="Status, capacidade e heartbeat." />
      <WorkerDetail id={id} />
    </div>
  );
}
