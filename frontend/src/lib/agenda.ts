/*
 * Regras do calendário de Agendamentos (12/11/2026): onde cada ocorrência cai na grade (no
 * fuso do agendamento) e o que muda no agendamento quando alguém arrasta uma ocorrência.
 *
 * Arrastar muda o agendamento inteiro (não há exceção por ocorrência no backend):
 * - data específica: muda a data e a hora;
 * - todo dia: muda só a hora;
 * - dias da semana: troca o dia arrastado pelo dia de destino e muda a hora;
 * - mensal: muda o dia do mês e a hora;
 * - por intervalo: não dá para arrastar (não tem horário fixo).
 */

import type { Schedule, ScheduleWritePayload } from "@/types/schedule";

export const FUSO_PADRAO = "America/Sao_Paulo";
export const DURACAO_MINIMA_MIN = 30;
const DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"];

/** Dia ("AAAA-MM-DD") e minuto do dia de um instante, no fuso pedido. */
export function noFuso(iso: string, fuso: string = FUSO_PADRAO): { dia: string; minutos: number } {
  const partes = Object.fromEntries(new Intl.DateTimeFormat("en-CA", {
    timeZone: fuso, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date(iso)).map((p) => [p.type, p.value]));
  return { dia: `${partes.year}-${partes.month}-${partes.day}`, minutos: Number(partes.hour) * 60 + Number(partes.minute) };
}

/** 0 = segunda ... 6 = domingo (a mesma convenção dos agendamentos). */
export function diaDaSemana(dia: string): number {
  const [a, m, d] = dia.split("-").map(Number);
  return (new Date(Date.UTC(a, m - 1, d)).getUTCDay() + 6) % 7;
}

export function horaTexto(minutos: number): string {
  const m = ((minutos % 1440) + 1440) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

/** Arredonda para o passo da grade (15 min), sem sair do dia. */
export function noPasso(minutos: number, passo = 15): number {
  return Math.min(Math.max(Math.round(minutos / passo) * passo, 0), 1440 - passo);
}

function listaDeDias(dias: number[]): string {
  const nomes = [...dias].sort((a, b) => a - b).map((d) => DIAS[d]);
  if (nomes.length === 7) return "todo dia";
  if (nomes.length === 5 && !dias.includes(5) && !dias.includes(6)) return "de segunda a sexta";
  return nomes.length <= 1 ? `toda ${nomes[0] ?? ""}` : `toda ${nomes.slice(0, -1).join(", ")} e ${nomes.at(-1)}`;
}

type Recorrencia = Pick<Schedule, "recurrence_type" | "time_of_day" | "weekdays" | "day_of_month" | "specific_date" | "schedule_type" | "interval_seconds">;

/** "Toda segunda e quarta às 08:00", "Dia 10 de cada mês às 09:30", "Em 20/11/2026 às 14:00". */
export function descrever(s: Recorrencia): string {
  if (s.schedule_type === "interval") {
    const min = Math.round((s.interval_seconds ?? 0) / 60);
    return min >= 60 && min % 60 === 0 ? `A cada ${min / 60} h` : `A cada ${min} min`;
  }
  const hora = `às ${s.time_of_day}`;
  if (s.recurrence_type === "once" && s.specific_date) {
    const [a, m, d] = s.specific_date.split("-");
    return `Em ${d}/${m}/${a} ${hora}`;
  }
  if (s.recurrence_type === "weekly") {
    const texto = listaDeDias(s.weekdays ?? []);
    return `${texto.charAt(0).toUpperCase()}${texto.slice(1)} ${hora}`;
  }
  if (s.recurrence_type === "monthly") {
    return s.day_of_month === 0 ? `Último dia de cada mês ${hora}` : `Dia ${s.day_of_month} de cada mês ${hora}`;
  }
  return `Todo dia ${hora}`;
}

export type Movimento =
  | { ok: true; patch: Partial<ScheduleWritePayload>; antes: string; depois: string; serie: boolean }
  | { ok: false; motivo: string };

/** O que muda no agendamento ao arrastar a ocorrência do dia ``de`` para ``para`` às ``minutos``. */
export function mover(s: Schedule, de: string, para: string, minutos: number): Movimento {
  if (s.schedule_type === "interval") {
    return { ok: false, motivo: "Agendamento por intervalo não tem horário fixo: abra e edite o intervalo." };
  }
  const hora = horaTexto(minutos);
  const base = { recurrence_type: s.recurrence_type, time_of_day: hora, weekdays: null as number[] | null,
    day_of_month: null as number | null, specific_date: null as string | null,
    schedule_type: null } as Partial<ScheduleWritePayload>;  // o backend deduz "uma vez" e regera o cron
  let novo: Recorrencia;
  if (s.recurrence_type === "once") {
    novo = { ...s, specific_date: para, time_of_day: hora };
    base.specific_date = para;
  } else if (s.recurrence_type === "weekly") {
    const origem = diaDaSemana(de);
    const destino = diaDaSemana(para);
    const dias = [...new Set((s.weekdays ?? []).map((d) => (d === origem ? destino : d)))].sort((a, b) => a - b);
    novo = { ...s, weekdays: dias, time_of_day: hora };
    base.weekdays = dias;
  } else if (s.recurrence_type === "monthly") {
    const dia = Number(para.split("-")[2]);
    novo = { ...s, day_of_month: dia, time_of_day: hora };
    base.day_of_month = dia;
  } else {
    novo = { ...s, time_of_day: hora };
  }
  const antes = descrever(s);
  const depois = descrever(novo);
  if (antes === depois) return { ok: false, motivo: "Nada mudou." };
  return { ok: true, patch: base, antes, depois, serie: s.recurrence_type !== "once" };
}

export type Bloco<T> = { item: T; inicio: number; fim: number; coluna: number; colunas: number };

/** Lado a lado o que se sobrepõe no mesmo dia (como na agenda do Google). */
export function lado(blocos: Array<{ item: unknown; inicio: number; fim: number }>): Bloco<unknown>[] {
  const ordenados = [...blocos].sort((a, b) => a.inicio - b.inicio || b.fim - a.fim);
  const saida: Bloco<unknown>[] = [];
  let grupo: Bloco<unknown>[] = [];
  let fimDoGrupo = -1;
  const fechar = () => {
    const total = Math.max(1, ...grupo.map((b) => b.coluna + 1));
    grupo.forEach((b) => { b.colunas = total; });
    saida.push(...grupo);
    grupo = [];
  };
  for (const b of ordenados) {
    if (b.inicio >= fimDoGrupo && grupo.length) fechar();
    const ocupadas = new Set(grupo.filter((g) => g.fim > b.inicio).map((g) => g.coluna));
    let coluna = 0;
    while (ocupadas.has(coluna)) coluna += 1;
    grupo.push({ ...b, coluna, colunas: 1 });
    fimDoGrupo = Math.max(fimDoGrupo, b.fim);
  }
  if (grupo.length) fechar();
  return saida;
}
