import type { Metadata } from "next";

import { ExecutionsManager } from "@/components/executions/executions-manager";

export const metadata: Metadata = { title: "Execuções" };

export default function ExecutionsPage() {
  return (
    <div>
      <ExecutionsManager />
    </div>
  );
}
