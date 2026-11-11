import type { Metadata } from "next";

import { HistoricoView } from "@/components/historico/historico-view";

export const metadata: Metadata = { title: "Histórico" };

export default function HistoricoPage() {
  return <HistoricoView />;
}
