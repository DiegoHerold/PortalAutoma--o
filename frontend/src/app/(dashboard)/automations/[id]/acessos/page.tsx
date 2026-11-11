import type { Metadata } from "next";

import { AcessosDaAutomacao } from "@/components/acessos/acessos-da-automacao";

export const metadata: Metadata = { title: "Acesso" };

export default async function AcessosPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AcessosDaAutomacao id={id} />;
}
