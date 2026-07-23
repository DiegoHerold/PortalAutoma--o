import Link from "next/link";
import { ChevronRight } from "lucide-react";

import { JobDetail } from "@/components/jobs/job-detail";
import { PageTitle } from "@/components/shared/page-title";

export default async function JobDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="space-y-6">
      <nav className="flex items-center gap-1 text-sm text-muted-foreground">
        <Link href="/jobs" className="hover:text-foreground">
          Jobs
        </Link>
        <ChevronRight className="h-4 w-4" />
        <span className="tabular text-foreground">#{id}</span>
      </nav>
      <PageTitle eyebrow="Detalhe" title={`Job #${id}`} description="Estado, estimativas e payload do job." />
      <JobDetail id={id} />
    </div>
  );
}
