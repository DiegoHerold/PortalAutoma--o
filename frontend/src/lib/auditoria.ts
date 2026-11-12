/*
 * Auditoria em frases (12/11/2026): cada evento vira "fez o quê" em português, para a linha do
 * tempo ler como uma conversa ("criou a máquina MAQ194", "abriu a tela Histórico").
 */

import { ALL_NAV_ITEMS } from "@/lib/navigation";

export type EventoDeAuditoria = {
  id: string;
  quando: string | null;
  acao: string;
  tipo: "alteracao" | "acesso" | "execucao" | "sistema";
  tipo_de_ator: string;
  ator_id: string | null;
  ator_nome: string | null;
  ator_email: string | null;
  recurso_tipo: string;
  recurso_id: string;
  antes: Record<string, unknown> | null;
  depois: Record<string, unknown> | null;
  detalhes: Record<string, unknown>;
  correlacao: string | null;
  ip: string | null;
  navegador: string | null;
};

export const TIPOS = [
  { valor: "", rotulo: "Tudo" },
  { valor: "alteracao", rotulo: "Alterações" },
  { valor: "acesso", rotulo: "Acessos" },
  { valor: "execucao", rotulo: "Execuções" },
  { valor: "sistema", rotulo: "Sistema" },
] as const;

const FRASES: Record<string, string> = {
  login_succeeded: "entrou no Portal",
  login_failed: "tentou entrar e não conseguiu",
  logout: "saiu do Portal",
  "tela.aberta": "abriu a tela",
  "maquina.cadastrada": "cadastrou a máquina",
  "maquina.removida": "apagou a máquina",
  "automation.archived": "arquivou a automação",
  "automation.restored": "restaurou a automação",
  "automation.created": "criou a automação",
  "automation.updated": "alterou a automação",
  "automation_version.created": "publicou uma versão da automação",
  "automacao.declarada": "declarou as entradas da automação",
  "automacao.campos.alterados": "alterou as entradas da automação",
  "automacao.item.criado": "criou um item",
  "automacao.item.alterado": "alterou um item",
  "automacao.item.importado": "importou um item",
  "automacao.item.situacao": "ativou ou desativou um item",
  "automacao.itens.proposta.aprovada": "aprovou o cadastro mandado pela automação",
  "automacao.itens.proposta.descartada": "descartou o cadastro mandado pela automação",
  "automacao.arquivo.baixado": "baixou um arquivo",
  "automacao.concessao.definida": "deu acesso a uma automação",
  "automacao.concessao.retirada": "tirou o acesso a uma automação",
  "execucao.parada_pedida": "pediu para parar a execução",
  "execucao.continuada": "continuou a execução cancelada",
  "execucao.encerrada_no_portal": "encerrou no Portal a execução que não respondia ao cancelamento",
  "execucao.telas.vistas": "viu as telas de uma execução",
  "execucao.tela.ampliada": "ampliou uma tela de execução",
  "direto.codigo.gerado": "gerou um código de inscrição",
  "direto.instancia.aprovar": "aprovou uma automação direta numa máquina",
  "direto.instancia.quarentena": "pôs uma automação direta em quarentena",
  "direto.instancia.revogar": "revogou uma automação direta",
  "direto.inscricao": "se inscreveu no Portal",
  "direto.sessao.aberta": "abriu uma sessão",
  "direto.sessao.recusada": "teve a sessão recusada",
  "direto.desafio.recusado": "teve o desafio de entrada recusado",
  user_created: "criou o usuário",
  user_updated: "alterou o usuário",
  user_deleted: "apagou o usuário",
  user_permissions_updated: "alterou as permissões do usuário",
  team_created: "criou o time",
  team_updated: "alterou o time",
  team_deleted: "apagou o time",
  "time.membros.adicionados": "pôs pessoas no time",
  "time.membro.removido": "tirou uma pessoa do time",
  "time.categorias.definidas": "mudou as permissões do time",
  "usuario.times.definidos": "mudou os times de uma pessoa",
  organization_created: "criou a organização",
  "category.created": "criou a categoria",
  "flow.created": "criou o fluxo",
  "flow_version.created": "salvou uma versão do fluxo",
  "schedule.updated": "alterou o agendamento",
  "schedule.created": "criou o agendamento",
  "retencao.definida": "mudou o prazo de retenção",
  "retencao.aplicada": "apagou o que passou do prazo de retenção",
  secret_created: "criou um segredo",
  secret_rotated: "trocou um segredo",
};

const METODOS: Record<string, string> = { "api.post": "fez uma alteração em", "api.put": "alterou", "api.patch": "alterou", "api.delete": "apagou algo em" };

const RECURSOS: Record<string, string> = {
  machine: "máquina", maquinas: "Máquinas", automation: "automação", automations: "Automações", schedules: "Agendamentos",
  schedule: "agendamento", users: "Usuários", user: "usuário", teams: "Times", team: "time", fila: "Fila", flows: "Fluxos",
  categories: "Categorias", governance: "Governança", "instancias-diretas": "Automações diretas", execucoes: "Execuções",
  executions: "Execuções", execution: "execução", tela: "tela", automation_item: "item", artifact: "arquivo", workers: "Agents",
};

export function nomeDoRecurso(tipo: string): string {
  return RECURSOS[tipo] ?? tipo.replace(/[_-]+/g, " ");
}

/** Nome da tela pelo caminho ("/historico" → "Histórico"), com a do menu quando existe. */
export function nomeDaTela(caminho: string): string {
  const item = [...ALL_NAV_ITEMS].sort((a, b) => b.href.length - a.href.length).find((i) => caminho === i.href || caminho.startsWith(`${i.href}/`));
  if (!item) return caminho;
  return caminho === item.href ? item.label : `${item.label} (${caminho.slice(item.href.length + 1)})`;
}

/** "abriu a tela Histórico", "cadastrou a máquina mch_…", "fez uma alteração em Agendamentos". */
export function frase(e: EventoDeAuditoria, nomes: Record<string, string> = {}): { verbo: string; objeto: string | null } {
  if (e.acao === "tela.aberta") return { verbo: FRASES["tela.aberta"], objeto: nomeDaTela(e.recurso_id) };
  if (e.acao.startsWith("api.")) {
    const falhou = typeof e.detalhes.status === "number" && (e.detalhes.status as number) >= 400;
    return { verbo: `${falhou ? "tentou: " : ""}${METODOS[e.acao] ?? "mexeu em"}`, objeto: nomeDoRecurso(e.recurso_tipo) };
  }
  const verbo = FRASES[e.acao] ?? e.acao.replace(/[._]+/g, " ");
  const id = e.recurso_id && e.recurso_id !== "-" && !e.acao.startsWith("login") ? e.recurso_id : null;
  // Pessoa citada pelo número vira o nome ("alterou as permissões do usuário Ana Souza").
  return { verbo, objeto: id && e.recurso_tipo === "user" && nomes[id] ? nomes[id] : id };
}

export function quem(e: EventoDeAuditoria): string {
  if (e.tipo_de_ator === "user") return e.ator_nome ?? (e.ator_id ? `Usuário ${e.ator_id}` : "Alguém");
  if (e.tipo_de_ator === "system") return "Portal";
  if (e.tipo_de_ator === "direct_instance") return `Automação direta ${e.ator_id ?? ""}`.trim();
  if (e.tipo_de_ator === "agent") return `Agent ${e.ator_id ?? ""}`.trim();
  return e.tipo_de_ator;
}

const LIGACOES = new Set(["de", "da", "do", "das", "dos", "e"]);

/** "Equipe de TI" → "ET", "Ana Souza" → "AS". */
export function iniciais(nome: string): string {
  return nome.split(/\s+/).filter((p) => p && !LIGACOES.has(p.toLowerCase())).slice(0, 2).map((p) => p[0]!.toUpperCase()).join("") || "?";
}
