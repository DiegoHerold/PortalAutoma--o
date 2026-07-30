import { effectiveWindow } from "@/lib/schedule-duration";
import type { ScheduleCalendarItem } from "@/types/schedule";

/**
 * Layout de lanes para as visões Semana/Dia. O backend já resolve *quais* itens se
 * sobrepõem (overlap_group/overlap_index/overlap_count — seção 34); aqui só convertemos
 * isso em posição/largura relativa (%) e recorte de horário dentro de um dia. O backend
 * não conhece pixels — essa responsabilidade é só do frontend (seção 34).
 */

export const MAX_INLINE_LANES = 4;

export type ClampedBlock = {
  item: ScheduleCalendarItem;
  /** Minutos desde 00:00 do dia sendo renderizado, já recortado para os limites do dia. */
  startMinutes: number;
  endMinutes: number;
  continuesBefore: boolean;
  continuesAfter: boolean;
  laneIndex: number;
  laneCount: number;
};

/** Recorta um item para o intervalo [dayStart, dayEnd) e devolve minutos relativos ao dia. */
export function clampItemToDay(item: ScheduleCalendarItem, dayDate: Date): ClampedBlock | null {
  const dayStart = new Date(dayDate.getFullYear(), dayDate.getMonth(), dayDate.getDate(), 0, 0, 0, 0);
  const dayEnd = new Date(dayStart.getTime() + 24 * 60 * 60 * 1000);
  const { start, end } = effectiveWindow(item);

  if (end <= dayStart || start >= dayEnd) return null;

  const clampedStart = start < dayStart ? dayStart : start;
  const clampedEnd = end > dayEnd ? dayEnd : end;

  return {
    item,
    startMinutes: (clampedStart.getTime() - dayStart.getTime()) / 60000,
    endMinutes: Math.max((clampedEnd.getTime() - dayStart.getTime()) / 60000, (clampedStart.getTime() - dayStart.getTime()) / 60000 + 12),
    continuesBefore: start < dayStart,
    continuesAfter: end > dayEnd,
    laneIndex: item.overlap_index ?? 0,
    laneCount: Math.min(item.overlap_count ?? 1, MAX_INLINE_LANES),
  };
}

/** Todos os blocos de um dia, prontos para posicionamento (top/height em % de 24h, left/width em % de largura). */
export function layoutDay(items: ScheduleCalendarItem[], dayDate: Date): ClampedBlock[] {
  return items
    .map((item) => clampItemToDay(item, dayDate))
    .filter((block): block is ClampedBlock => block !== null)
    .sort((a, b) => a.startMinutes - b.startMinutes);
}

/** Agrupa por overlap_group para decidir entre "lanes inline" e "cluster (+N)". */
export function groupByOverlapGroup(items: ScheduleCalendarItem[]): Map<number | string, ScheduleCalendarItem[]> {
  const groups = new Map<number | string, ScheduleCalendarItem[]>();
  for (const item of items) {
    const key = item.overlap_group ?? item.id;
    const bucket = groups.get(key) ?? [];
    bucket.push(item);
    groups.set(key, bucket);
  }
  return groups;
}

export function topPercent(minutes: number): number {
  return (minutes / (24 * 60)) * 100;
}

export function heightPercent(startMinutes: number, endMinutes: number): number {
  return Math.max(((endMinutes - startMinutes) / (24 * 60)) * 100, 0.6);
}
