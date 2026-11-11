/** Formato de `GET /fila` (backend/modules/dispatch/application/use_cases/queue.py::VerFila). */

export type Motivo = { codigo: string; texto: string };

export type JobNaFila = {
  posicao: number;
  job_id: string;
  execution_id: string;
  automation_id: number | null;
  automacao: string | null;
  pool: string;
  itens: string[];
  prioridade: number;
  posicao_manual: number | null;
  maquina_prevista: string | null;
  maquina_prevista_nome: string | null;
  maquina_obrigatoria: string | null;
  inicio_previsto: string | null;
  termino_previsto: string | null;
  /** Soma das etapas quando todas têm base; senão null. */
  estimativa_s: number | null;
  /** Soma só das etapas com base, quando alguma não tem: "pelo menos". */
  estimativa_minima_s: number | null;
  etapas_sem_base: string[];
  motivos: Motivo[];
  enfileirado_em: string;
};

export type JobPerdido = {
  job_id: string;
  execution_id: string;
  automation_id: number | null;
  automacao: string | null;
  itens: Array<string | Record<string, unknown>>;
  maquina_id: string | null;
  maquina_nome: string | null;
  perdido_em: string | null;
  motivo: string | null;
  /** A automação guarda o progresso fora da máquina: "continuar" pode ir para qualquer máquina. */
  estado_central: boolean;
};

export type Rodando = {
  /** null para quem não é admin: vê que a máquina está ocupada, não por qual job. */
  job_id: string | null;
  pool: string;
  restante_s: number | null;
  motivo: string | null;
};

export type MaquinaNaFila = {
  id: string;
  nome: string | null;
  online: boolean;
  sessao_bloqueada: boolean;
  job_perdido: boolean;
  capacidade: Record<string, number>;
  rodando: Rodando[];
  vagas_tela: number;
};

export type VisaoFila = {
  gerado_em: string;
  jobs: JobNaFila[];
  perdidos: JobPerdido[];
  maquinas: MaquinaNaFila[];
};

export const POOLS: Record<string, string> = {
  interactive: "Tela",
  browser: "Navegador",
  background: "Segundo plano",
};

/** "~ 1 h 05 min", "~ 4 min", "< 1 min". Estimativa é sempre aproximada. */
export function duracao(segundos: number | null | undefined): string {
  if (segundos == null || Number.isNaN(segundos)) return "—";
  const s = Math.max(0, Math.round(segundos));
  if (s < 60) return "< 1 min";
  const min = Math.round(s / 60);
  if (min < 60) return `~ ${min} min`;
  const h = Math.floor(min / 60);
  const resto = min % 60;
  return `~ ${h} h ${String(resto).padStart(2, "0")} min`;
}

/** "14:32" hoje, "amanhã 08:10", "12/11 08:10" depois. */
export function horario(iso: string | null | undefined, agora: Date = new Date()): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  const dia = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const dias = Math.round((dia(d) - dia(agora)) / 86_400_000);
  if (dias === 0) return hora;
  if (dias === 1) return `amanhã ${hora}`;
  return `${d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })} ${hora}`;
}

/** "em 12 min", "agora", "há 3 min". */
export function relativo(iso: string | null | undefined, agora: Date = new Date()): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const diff = Math.round((d.getTime() - agora.getTime()) / 60_000);
  if (diff === 0) return "agora";
  if (diff > 0) return diff < 60 ? `em ${diff} min` : `em ${duracao(diff * 60).replace("~ ", "")}`;
  const passado = -diff;
  return passado < 60 ? `há ${passado} min` : `há ${duracao(passado * 60).replace("~ ", "")}`;
}

export function rotuloItem(item: string | Record<string, unknown>): string {
  if (typeof item === "string") return item;
  const chave = item.chave ?? item.rotulo;
  return typeof chave === "string" ? chave : JSON.stringify(item);
}
