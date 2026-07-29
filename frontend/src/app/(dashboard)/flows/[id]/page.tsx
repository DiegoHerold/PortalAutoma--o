import { Suspense } from "react";

import { FlowDetailShell } from "@/components/flows/flow-detail-shell";
import { Skeleton } from "@/components/ui/skeleton";

export default async function FlowDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense
      fallback={
        <div className="space-y-4">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-[500px] rounded-lg" />
        </div>
      }
    >
      <FlowDetailShell flowId={id} />
    </Suspense>
  );
}
