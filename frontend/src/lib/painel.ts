/** Formato de `GET /painel`, `/painel/linha-do-tempo` e `/historico` (backend/modules/telemetry/api/painel.py). */

import type { LinhaDeLog, SituacaoImagem } from "@/lib/acompanhar";
import type { SituacaoDoAgora } from "@/components/painel/controle-da-execucao";

export type ExecucaoAoVivo = {
  execucao_id: string;
  job_id: string;
  automation_id: number | null;
  automacao: string | null;
  maquina_id: string | null;
  maquina: string | null;
  modo: string | null;
  itens: Array<{ chave: string; rotulo: string | null }>;
  tentativa: number;
  desde: string | null;
  decorrido_s: number | null;
  falta_s: number | null;
  motivo_sem_previsao: string | null;
  termino_previsto: string | null;
  etapa: { etapa: string; item: string | null } | null;
  item: { item: string; rotulo: string | null } | null;
  progresso: { atual: number; total: number; rotulo: string | null } | null;
  pausa: { motivo: string; detalhe: string | null } | null;
  atencoes: number;
  /** Por que não está andando (cancelando, parando, pausa, espera, sem sinal); null rodando normal. */
  situacao?: SituacaoDoAgora | null;
  pode_controlar?: boolean;
  pode_ver_tela: boolean;
  tela: {
    imagem_id: string;
    rotulo: string | null;
    segundos_nesta_tela: number | null;
    espera_rotulo: string | null;
    imagem?: SituacaoImagem;
  } | null;
  log: LinhaDeLog[] | null;
};

export type MaquinaNoPainel = {
  id: string;
  nome: string | null;
  online: boolean;
  sessao_bloqueada: boolean;
  job_perdido: boolean;
  ocupada: boolean;
  rodando: string | null;
  proximo: { automacao: string | null; inicio_previsto: string | null } | null;
};

export type Painel = {
  gerado_em: string;
  central: boolean;
  execucoes: ExecucaoAoVivo[];
  maquinas: MaquinaNoPainel[];
  fila: { esperando: number; perdidos: number; termina_em: string | null; sem_previsao: number };
};

export type BlocoNaLinha = {
  tipo: "feito" | "rodando" | "previsto";
  inicio: string;
  fim: string | null;
  fim_conhecido: boolean;
  esquerda: number;
  largura: number;
  cortado_no_inicio: boolean;
  cortado_no_fim: boolean;
  execucao_id: string | null;
  job_id: string | null;
  automacao: string | null;
  itens: string[];
  situacao: string | null;
};

export type LinhaDoTempo = {
  inicio: string;
  fim: string;
  agora: string;
  agora_posicao: number;
  marcas: Array<{ quando: string; posicao: number }>;
  maquinas: Array<{ maquina_id: string; nome: string; blocos: BlocoNaLinha[] }>;
};

export type ExecucaoNoHistorico = {
  execucao_id: string;
  status: string;
  automation_id: number | null;
  automacao: string | null;
  itens: string[];
  total_itens: number;
  maquinas: string | null;
  iniciada_em: string | null;
  concluida_em: string | null;
  duracao_s: number | null;
  previsto_s: number | null;
  falha: string | null;
};
