import type { Metadata } from "next";
import { Suspense } from "react";

import { HistoricoView } from "@/components/historico/historico-view";

export const metadata: Metadata = { title: "Histórico" };

export default function HistoricoPage() {
  return (
    <Suspense fallback={<div className="skeleton h-96 rounded-xl" />}>
      <HistoricoView />
    </Suspense>
  );
}
