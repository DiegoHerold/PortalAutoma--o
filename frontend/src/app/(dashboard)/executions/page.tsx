import type { Metadata } from "next";

import { ExecutionsManager } from "@/components/executions/executions-manager";

export const metadata: Metadata = { title: "Execucoes" };

export default function ExecutionsPage() {
  return (
    <div>
      <ExecutionsManager />
    </div>
  );
}
