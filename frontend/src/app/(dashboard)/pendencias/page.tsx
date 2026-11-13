import type { Metadata } from "next";

import { PaginaDePendencias } from "@/components/pendencias/pendencias";

export const metadata: Metadata = { title: "Pendências" };

export default function PendenciasRoutePage() {
  return <PaginaDePendencias />;
}
