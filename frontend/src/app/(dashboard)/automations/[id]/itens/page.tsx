import type { Metadata } from "next";

import { ItensDaAutomacao } from "@/components/itens/itens-da-automacao";

export const metadata: Metadata = { title: "Itens" };

export default async function ItensPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ItensDaAutomacao id={id} />;
}
