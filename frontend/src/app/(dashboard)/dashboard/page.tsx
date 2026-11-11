import type { Metadata } from "next";

import { PainelAoVivo } from "@/components/painel/painel-ao-vivo";

export const metadata: Metadata = { title: "Painel" };

// Fase 5: o Painel mostra o que roda agora (monitores e, para admin, a Central de telas).
// O resumo antigo (components/dashboard) segue no código, fora da tela.
export default function DashboardPage() {
  return <PainelAoVivo />;
}
