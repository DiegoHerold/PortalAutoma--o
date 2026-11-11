import { AutomacaoView } from "@/components/automacao/automacao-view";

export default async function AutomationDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AutomacaoView id={id} />;
}
