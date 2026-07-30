import { addDays, toDateKey } from "@/lib/calendar";
import type { ScheduleCalendarItem } from "@/types/schedule";

/**
 * Agrupa itens do calendário por dia local, replicando o item em todo dia que seu intervalo
 * [planned/actual_start, effective_end] atravessa — necessário para execuções de longa duração
 * continuarem visíveis ao virar o dia (seção 19), tanto no Mês/Semana/Dia quanto na Agenda.
 */
export function groupItemsByDay(items: ScheduleCalendarItem[]): Map<string, ScheduleCalendarItem[]> {
  const map = new Map<string, ScheduleCalendarItem[]>();
  for (const item of items) {
    const start = new Date(item.actual_start ?? item.planned_start);
    const rawEnd = item.actual_end ?? item.effective_end ?? item.planned_start;
    const end = new Date(rawEnd);
    let cursor = new Date(start.getFullYear(), start.getMonth(), start.getDate());
    const lastDay = new Date(end.getFullYear(), end.getMonth(), end.getDate());
    // Segurança: nunca duplicar em mais de 31 dias (evita loop infinito com dados malformados).
    let guard = 0;
    while (cursor <= lastDay && guard < 31) {
      const key = toDateKey(cursor);
      const bucket = map.get(key) ?? [];
      bucket.push(item);
      map.set(key, bucket);
      cursor = addDays(cursor, 1);
      guard += 1;
    }
  }
  for (const bucket of map.values()) bucket.sort((a, b) => a.planned_start.localeCompare(b.planned_start));
  return map;
}
