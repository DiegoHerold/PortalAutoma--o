import type { Metadata } from "next";

import { AcompanharExecucao } from "@/components/acompanhar/acompanhar-execucao";

export const metadata: Metadata = { title: "Acompanhar" };

export default async function AcompanharPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AcompanharExecucao id={id} />;
}
