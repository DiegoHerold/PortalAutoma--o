/*
 * Campos de uma automação (Fase 7): o que se informa ao acionar (``entrada``) e o que cada
 * item guarda (``colunas``). O Portal edita livremente; o manifesto só sugere o início.
 * Formato de `GET /automations/{id}/formulario` (backend/modules/catalog/api/formulario.py).
 */

import { API_BASE_URL } from "@/lib/constants";

export type TipoDeCampo =
  | "texto" | "texto_longo" | "numero" | "inteiro" | "sim_nao" | "data" | "mes_ano" | "lista" | "email" | "pasta" | "json";

export type Campo = {
  chave: string;
  rotulo: string;
  tipo: TipoDeCampo;
  obrigatorio: boolean;
  padrao: unknown;
  opcoes: string[];
  ajuda: string | null;
  afeta_trabalho: boolean;
  /** Fase 8: quem criou o campo. O da automação vem da declaração dela ao conectar. */
  origem?: "automacao" | "portal";
  /** A automação deixou de mandar: não é pedido ao executar, mas não some. */
  fora_de_uso?: boolean;
};

export type Formulario = {
  origem: "manifesto" | "portal";
  versao: number;
  pode_editar: boolean;
  item: { nome: string; chave: string; grupo: string | null } | null;
  entrada: Campo[];
  colunas: Campo[];
  tipos: Array<{ tipo: TipoDeCampo; rotulo: string }>;
};

/** Erro da API com o motivo de cada campo (`{"campos": {"competencia": "obrigatório"}}`). */
export class ErroComCampos extends Error {
  constructor(mensagem: string, readonly campos: Record<string, string>) {
    super(mensagem);
  }
}

export async function enviar<T>(caminho: string, metodo: string, corpo: unknown, token: string | null): Promise<T> {
  const resposta = await fetch(`${API_BASE_URL}${caminho}`, {
    method: metodo, cache: "no-store", body: JSON.stringify(corpo),
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  const texto = await resposta.text();
  const json = texto ? JSON.parse(texto) : null;
  if (!resposta.ok) {
    const detalhes = json?.error?.details ?? json?.detail;
    const campos = (detalhes && typeof detalhes === "object" && detalhes.campos) || {};
    const mensagem = typeof json?.error?.message === "string" ? json.error.message
      : typeof json?.detail === "string" ? json.detail : "Não foi possível salvar.";
    throw new ErroComCampos(Object.keys(campos).length ? "Confira os campos destacados." : mensagem, campos);
  }
  return json as T;
}

/** Chave técnica a partir do nome: "Pasta de destino" → "pasta_de_destino". */
export function chaveDe(rotulo: string): string {
  const base = rotulo.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 60);
  return /^[a-z]/.test(base) ? base : `campo_${base}`.slice(0, 60);
}

/** Valores iniciais do formulário: o padrão de cada campo. */
export function valoresIniciais(campos: Campo[]): Record<string, unknown> {
  return Object.fromEntries(campos.filter((c) => c.padrao !== null && c.padrao !== undefined).map((c) => [c.chave, c.padrao]));
}

export function mostrarValor(campo: Campo | undefined, valor: unknown): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  if (campo?.tipo === "sim_nao" || typeof valor === "boolean") return valor ? "Sim" : "Não";
  if (campo?.tipo === "data" && typeof valor === "string") return valor.split("-").reverse().join("/");
  if (campo?.tipo === "json" || typeof valor === "object") return Array.isArray(valor) ? `${valor.length} registro(s)` : "dados";
  return String(valor);
}
