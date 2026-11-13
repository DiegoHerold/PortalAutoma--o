/**
 * Configurações do sistema (limites e limpeza automática). O catálogo vem do backend
 * (`backend/modules/governance/domain/configuracoes.py`): a tela não repete nomes nem padrões.
 */

export type LimiteDoSistema = {
  chave: string;
  grupo: string;
  nome: string;
  descricao: string;
  unidade: "mb" | "segundos" | "quantidade" | "bytes";
  padrao: number;
  minimo: number;
  maximo: number;
  onde_vale: string;
  origem: "portal" | "arquivo";
  variavel_de_ambiente: string | null;
  valor: number;
  personalizado: boolean;
  atualizado_em: string | null;
};

export type RegraDeLimpeza = {
  chave: string;
  grupo: string;
  nome: string;
  descricao: string;
  o_que_sai: string;
  padrao_dias: number | null;
  minimo_dias: number;
  maximo_dias: number;
  editavel: boolean;
  dias: number | null;
  personalizado: boolean;
  atualizado_por: string | null;
  atualizado_em: string | null;
  ultima_limpeza_em: string | null;
  ultima_limpeza_apagados: number | null;
  total_apagados: number;
};

export type Catalogo<T> = { grupos: string[]; itens: T[] };

const numero = new Intl.NumberFormat("pt-BR");

function plural(n: number, um: string, varios: string): string {
  return `${numero.format(n)} ${n === 1 ? um : varios}`;
}

/** 14400 segundos -> "4 horas"; 65536 bytes -> "64 KB"; 200 mb -> "200 MB". */
export function valorLegivel(valor: number, unidade: LimiteDoSistema["unidade"]): string {
  if (unidade === "mb") return `${numero.format(valor)} MB`;
  if (unidade === "quantidade") return numero.format(valor);
  if (unidade === "bytes") {
    if (valor >= 1024 * 1024 && valor % (1024 * 1024) === 0) return `${numero.format(valor / 1024 / 1024)} MB`;
    if (valor >= 1024 && valor % 1024 === 0) return `${numero.format(valor / 1024)} KB`;
    return plural(valor, "byte", "bytes");
  }
  if (valor % 86400 === 0) return plural(valor / 86400, "dia", "dias");
  if (valor % 3600 === 0) return plural(valor / 3600, "hora", "horas");
  if (valor % 60 === 0) return plural(valor / 60, "minuto", "minutos");
  return plural(valor, "segundo", "segundos");
}

export const NOME_DA_UNIDADE: Record<LimiteDoSistema["unidade"], string> = {
  mb: "MB",
  segundos: "segundos",
  quantidade: "",
  bytes: "bytes",
};

export function prazoLegivel(dias: number | null): string {
  return dias == null ? "Sem prazo" : plural(dias, "dia", "dias");
}

/** Os itens do catálogo; resposta fora do formato vira lista vazia (a tela não cai). */
export function itensDe<T>(catalogo: Catalogo<T> | null): T[] {
  return catalogo && Array.isArray(catalogo.itens) ? catalogo.itens : [];
}

/** Agrupa na ordem que o backend mandou e filtra pela busca (nome, descrição ou chave). */
export function agrupar<T extends { grupo: string; nome: string; descricao: string; chave: string }>(
  catalogo: Catalogo<T> | null,
  busca: string,
): Array<{ grupo: string; itens: T[] }> {
  const itens = itensDe(catalogo);
  const grupos = catalogo && Array.isArray(catalogo.grupos) ? catalogo.grupos : [...new Set(itens.map((i) => i.grupo))];
  const termo = busca.trim().toLowerCase();
  const passa = (i: T) => !termo || [i.nome, i.descricao, i.chave, i.grupo].some((t) => String(t).toLowerCase().includes(termo));
  return grupos
    .map((grupo) => ({ grupo, itens: itens.filter((i) => i.grupo === grupo && passa(i)) }))
    .filter((g) => g.itens.length > 0);
}
