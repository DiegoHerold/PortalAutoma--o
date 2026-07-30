// Fase 7 (Central de Agendamentos): a spec define exatamente 5 visões — Agora, Dia, Semana,
// Mês e Agenda (seção 2/5/45) — sem uma view "Lista" separada. A antiga razão de ser desta
// view (agendamentos schedule_type="interval" não apareciam em GET /schedules/calendar) foi
// corrigida no backend (calendar.py::occurrences_in_window agora também calcula ocorrências de
// intervalo), então a visão Agenda já cobre esses agendamentos. Mantido vazio em vez de
// removido — ver nota em calendar/occurrence-chip.tsx sobre a restrição de exclusão de arquivos.
export {};
