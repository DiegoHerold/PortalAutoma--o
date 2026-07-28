import { SectionCard } from "@/components/shared/section-card";

export function WorkersSummary() {
  return (
    <SectionCard title="Resumo dos workers">
      <p className="text-sm text-slate-600">
        Estrutura pronta para mostrar heartbeat, capacidade por executor e distribuicao entre maquinas.
      </p>
    </SectionCard>
  );
}
