import { Suspense } from "react";

import { FlowExecutionMonitor } from "@/components/flows/execution/flow-execution-monitor";
import { Skeleton } from "@/components/ui/skeleton";

export default async function FlowExecutionMonitorPage({ params }: { params: Promise<{ id: string }> }) {
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
      <FlowExecutionMonitor flowExecutionId={id} />
    </Suspense>
  );
}
