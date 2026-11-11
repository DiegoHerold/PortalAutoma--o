import type { Metadata } from "next";

import { FilaManager } from "@/components/fila/fila-manager";

export const metadata: Metadata = { title: "Fila" };

export default function FilaPage() {
  return <FilaManager />;
}
