/** Formato de `GET /execucoes/{id}/acompanhar` (backend/modules/telemetry/api/acompanhar.py). */

export type SituacaoImagem = { situacao: "pronta" | "recusada" | "apagada"; motivo: string | null } | null;

/** Por que não há imagem para mostrar: recusada pelo portal ou apagada pela retenção. */
export function semImagem(s: SituacaoImagem | undefined): string | null {
  if (s?.situacao === "recusada") return `Imagem recusada: ${s.motivo ?? "sem motivo"}`;
  if (s?.situacao === "apagada") return `Imagem ${s.motivo ?? "apagada pela retenção"}`;
  return null;
}

export type Passo = {
  id: string;
  rotulo: string | null;
  tipo: "abriu" | "fechou" | "acao" | "falha" | null;
  imagem_id: string | null;
  item: string | null;
  quando: string;
  imagem?: SituacaoImagem;
};

export type Tela = {
  imagem_id: string;
  rotulo: string | null;
  tipo: string | null;
  item: string | null;
  quando: string;
  desde: string | null;
  segundos_nesta_tela: number | null;
  espera_rotulo: string | null;
  imagem?: SituacaoImagem;
};

export type EtapaEstimada = {
  etapa: string;
  nome: string;
  item: string | null;
  estimativa_s: number | null;
  base: { tipo: string; amostras: number; texto: string } | null;
  motivo: string | null;
  motivo_texto: string | null;
  situacao: string;
  real_s: number | null;
  tarefas_previstas: number | null;
  tarefas_feitas: number;
};

export type JobAcompanhado = {
  job_id: string;
  status: string;
  pool: string | null;
  itens: Array<string | Record<string, unknown>>;
  maquina_id: string | null;
  maquina_nome: string | null;
  modo: string | null;
  tentativa: number | null;
  desde: string | null;
  falta_s: number | null;
  motivo_sem_previsao: string | null;
  termino_previsto: string | null;
  falha: string | null;
};

export type Acompanhamento = {
  gerado_em: string;
  execucao: {
    id: string;
    status: string;
    criada_em: string;
    iniciada_em: string | null;
    concluida_em: string | null;
    falha: string | null;
    solicitante: string | null;
  };
  automacao: { id: number | null; nome: string | null; versao: string | null };
  pode: { ver_telas_e_logs: boolean; controlar: boolean };
  rodando: boolean;
  decorrido_s: number | null;
  falta_s: number | null;
  termino_previsto: string | null;
  jobs: JobAcompanhado[];
  agora: {
    etapa_atual: { etapa: string; item: string | null; desde: string; tarefas_previstas: number | null } | null;
    item_atual: { item: string; rotulo: string | null; desde: string } | null;
    progresso: { atual: number; total: number; rotulo: string | null; item: string | null } | null;
    pausa: { motivo: string; detalhe: string | null; desde: string } | null;
    conclusao: { situacao: string; resumo: string | null; quando: string } | null;
    tela: Tela | null;
    passos: Passo[];
    atencoes: Array<{ id: string; item: string | null; motivo: string; quando: string }>;
  };
  estimativa: { jobs: Array<{ job_id: string; etapas: EtapaEstimada[] }> };
};

export type LinhaDeLog = {
  id: string;
  nivel: string | null;
  texto: string | null;
  item: string | null;
  espera: boolean;
  quando: string;
};

export const SITUACOES: Record<string, { texto: string; tom: "success" | "warning" | "destructive" | "info" | "neutral" }> = {
  created: { texto: "Criada", tom: "neutral" },
  pending: { texto: "Na fila", tom: "info" },
  running: { texto: "Rodando", tom: "success" },
  cancelling: { texto: "Cancelando", tom: "warning" },
  succeeded: { texto: "Concluída", tom: "success" },
  partially_succeeded: { texto: "Concluída com atenção", tom: "warning" },
  failed: { texto: "Falhou", tom: "destructive" },
  cancelled: { texto: "Cancelada", tom: "neutral" },
  timed_out: { texto: "Tempo esgotado", tom: "destructive" },
  lost: { texto: "Perdida", tom: "warning" },
};

export const MOTIVOS_SEM_PREVISAO: Record<string, string> = {
  aguardando_job_sem_previsao: "alguma etapa ainda não tem histórico de estimativas",
  acima_da_estimativa: "já passou da estimativa",
};

export const PAUSAS: Record<string, string> = {
  reinicio: "Reiniciando",
  espera_externa: "Esperando algo fora da automação",
};

/** "12:05" ou "1:02:05". */
export function relogio(segundos: number | null | undefined): string {
  if (segundos == null || Number.isNaN(segundos)) return "—";
  const s = Math.max(0, Math.floor(segundos));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  const dois = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${dois(m)}:${dois(r)}` : `${m}:${dois(r)}`;
}

/** "N s nesta tela" como o portal da Integração Contábil: segundos até 2 min, depois minutos. */
export function nestaTela(segundos: number): string {
  if (segundos < 120) return `${segundos} s nesta tela`;
  return `${Math.floor(segundos / 60)} min nesta tela`;
}
