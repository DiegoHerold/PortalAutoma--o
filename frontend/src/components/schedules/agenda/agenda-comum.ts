import { DURACAO_MINIMA_MIN } from "@/lib/agenda";
import { temporalStatusMeta } from "@/lib/status";
import type { ScheduleCalendarItem } from "@/types/schedule";

export const SEMANA = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"];

/** Cor do bloco pela situação da ocorrência: futura em azul, deu certo em verde, falha em vermelho. */
const COR: Record<string, { bloco: string; ponto: string }> = {
  success: { bloco: "border-success bg-success/20 text-foreground", ponto: "bg-success" },
  destructive: { bloco: "border-destructive bg-destructive/20 text-foreground", ponto: "bg-destructive" },
  warning: { bloco: "border-warning bg-warning/20 text-foreground", ponto: "bg-warning" },
  primary: { bloco: "border-primary bg-primary/20 text-foreground", ponto: "bg-primary" },
  neutral: { bloco: "border-muted-foreground/50 bg-muted text-muted-foreground", ponto: "bg-muted-foreground" },
};

function tomDe(item: ScheduleCalendarItem): keyof typeof COR {
  if (item.temporal_status.startsWith("future")) return item.temporal_status === "future_paused" ? "neutral" : "primary";
  const tom = temporalStatusMeta(item.temporal_status).tone;
  return tom === "info" ? "primary" : ((tom in COR ? tom : "neutral") as keyof typeof COR);
}
export const corDe = (item: ScheduleCalendarItem) => COR[tomDe(item)].bloco;
export const pontoDe = (item: ScheduleCalendarItem) => COR[tomDe(item)].ponto;

export function duracaoMin(item: ScheduleCalendarItem): number {
  const fim = item.effective_end ? Date.parse(item.effective_end) : null;
  const inicio = Date.parse(item.actual_start ?? item.planned_start);
  const min = fim ? (fim - inicio) / 60000 : (item.estimated_duration_seconds ?? 0) / 60;
  return Math.max(DURACAO_MINIMA_MIN, Math.round(min) || DURACAO_MINIMA_MIN);
}

/** Só a ocorrência que ainda vai acontecer pode ser arrastada (a que já rodou é histórico). */
export function podeArrastar(item: ScheduleCalendarItem): boolean {
  return !item.execution_id && !item.actual_start && Date.parse(item.planned_start) > Date.now() && item.schedule_type !== "interval";
}

export const nomeDe = (i: ScheduleCalendarItem) => i.schedule_name || i.target_name;

export type Arraste = { item: ScheduleCalendarItem; deDia: string; agarrouMin: number };
export type Alvo = { dia: string; minutos: number };

export type Comum = {
  porDia: Map<string, Array<{ item: ScheduleCalendarItem; inicio: number; fim: number }>>;
  carregando: boolean;
  podeEscrever: boolean;
  arraste: Arraste | null;
  alvo: Alvo | null;
  setArraste: (a: Arraste | null) => void;
  setAlvo: (a: Alvo | null) => void;
  soltar: (dia: string, minutos: number) => void;
  abrir: (item: ScheduleCalendarItem, x: number, y: number) => void;
};
