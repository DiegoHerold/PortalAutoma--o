import type { Metadata } from "next";

import { PaginaDoAviso } from "@/components/pendencias/pendencias";

export const metadata: Metadata = { title: "Pendência" };

export default async function AvisoRoutePage({ params }: { params: Promise<{ aviso: string }> }) {
  const { aviso } = await params;
  return <PaginaDoAviso avisoId={aviso} />;
}
