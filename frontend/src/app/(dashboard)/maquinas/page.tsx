import type { Metadata } from "next";

import { MaquinasView } from "@/components/maquinas/maquinas-view";

export const metadata: Metadata = { title: "Máquinas" };

export default function MaquinasPage() {
  return <MaquinasView />;
}
