import type { Metadata } from "next";

import { AgendaCalendario } from "@/components/schedules/agenda/agenda-calendario";

export const metadata: Metadata = { title: "Agendamentos" };

// Agendamentos como uma agenda (12/11/2026): só o calendário. A tela antiga (lista, filtros,
// resumo e legenda) segue em components/schedules, fora da página.
export default function SchedulesPage() {
  return <AgendaCalendario />;
}
