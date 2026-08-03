// Fonte única da identidade visual de cada bloco do catálogo lateral do editor de Flows.
// Usado por: flow-editor.tsx (painel "Blocos do fluxo"), nodes.tsx (renderers do canvas) e
// node-panel.tsx (rótulos das abas de configuração). Mantendo tudo aqui evita que o cartão do
// catálogo, o nó no canvas e o painel de configuração fiquem visualmente dessincronizados.

import {
  Braces,
  GitBranch,
  GitMerge,
  ListOrdered,
  ListTree,
  Merge,
  Repeat,
  RotateCw,
  Variable,
  Wand2,
  type LucideIcon,
} from "lucide-react";

import type { FlowNodeType } from "@/types/flow";

export type ConditionBlockId =
  | "if_else"
  | "switch"
  | "for_each"
  | "while"
  | "loop"
  | "join"
  | "set_variable"
  | "map_fields"
  | "transform_data"
  | "merge";

export type BlockStyle = {
  icon: LucideIcon;
  /** cor do ícone/texto de destaque */
  accent: string;
  /** cor da borda do card/nó */
  ring: string;
  /** tint de fundo do cabeçalho do nó */
  bg: string;
};

export type ConditionBlockDefinition = {
  id: ConditionBlockId;
  /** node_type real no backend; null = ainda não existe suporte no motor de execução. */
  nodeType: FlowNodeType | null;
  name: string;
  description: string;
  style: BlockStyle;
  /** Só é possível arrastar/clicar para adicionar quando nodeType != null. */
  unavailableReason?: string;
};

export const CONDITION_BLOCKS: ConditionBlockDefinition[] = [
  {
    id: "if_else",
    nodeType: "if_else",
    name: "If / Else",
    description: "Segue por Verdadeiro ou Falso conforme uma regra sobre os dados recebidos.",
    style: { icon: GitBranch, accent: "text-warning", ring: "border-warning/40", bg: "bg-warning/10" },
  },
  {
    id: "switch",
    nodeType: "switch",
    name: "Switch",
    description: "Direciona para o caminho que combina com o valor testado, com uma saída padrão para os demais casos.",
    style: { icon: ListTree, accent: "text-violet-500", ring: "border-violet-500/40", bg: "bg-violet-500/10" },
  },
  {
    id: "for_each",
    nodeType: null,
    name: "For Each",
    description: "Repete as próximas etapas para cada item de uma lista.",
    style: { icon: ListOrdered, accent: "text-cyan-500", ring: "border-cyan-500/40", bg: "bg-cyan-500/10" },
    unavailableReason: "Em preparo — requer um motor de execução com suporte a iteração (o atual só roda grafos sem ciclos).",
  },
  {
    id: "while",
    nodeType: null,
    name: "While",
    description: "Repete as próximas etapas enquanto uma condição continuar verdadeira.",
    style: { icon: RotateCw, accent: "text-sky-500", ring: "border-sky-500/40", bg: "bg-sky-500/10" },
    unavailableReason: "Em preparo — requer um motor de execução com suporte a repetição (o atual só roda grafos sem ciclos).",
  },
  {
    id: "loop",
    nodeType: null,
    name: "Loop",
    description: "Repete um trecho do fluxo por N vezes ou até uma condição encerrar o ciclo.",
    style: { icon: Repeat, accent: "text-blue-500", ring: "border-blue-500/40", bg: "bg-blue-500/10" },
    unavailableReason: "Em preparo — requer um motor de execução com suporte a ciclos controlados.",
  },
  {
    id: "join",
    nodeType: "join",
    name: "Join",
    description: "Reúne caminhos paralelos antes de continuar — espera todas as entradas, ou só a primeira, conforme configurado.",
    style: { icon: GitMerge, accent: "text-info", ring: "border-info/40", bg: "bg-info/10" },
  },
  {
    id: "set_variable",
    nodeType: "set_variable",
    name: "Set Variable",
    description: "Guarda um valor calculado para ser reaproveitado pelas próximas etapas do fluxo.",
    style: { icon: Variable, accent: "text-emerald-600", ring: "border-emerald-600/40", bg: "bg-emerald-600/10" },
  },
  {
    id: "map_fields",
    nodeType: "map_fields",
    name: "Map Fields",
    description: "Seleciona e renomeia campos vindos de etapas anteriores.",
    style: { icon: Braces, accent: "text-teal-600", ring: "border-teal-600/40", bg: "bg-teal-600/10" },
  },
  {
    id: "transform_data",
    nodeType: "transform_data",
    name: "Transform Data",
    description: "Aplica transformações simples a um valor (maiúsculas, número, arredondar...).",
    style: { icon: Wand2, accent: "text-fuchsia-600", ring: "border-fuchsia-600/40", bg: "bg-fuchsia-600/10" },
  },
  {
    id: "merge",
    nodeType: "merge",
    name: "Merge Data",
    description: "Combina os dados de múltiplos caminhos paralelos em um único objeto.",
    style: { icon: Merge, accent: "text-indigo-600", ring: "border-indigo-600/40", bg: "bg-indigo-600/10" },
  },
];

export const CONDITION_BLOCK_BY_NODE_TYPE: Partial<Record<FlowNodeType, ConditionBlockDefinition>> = {};
for (const block of CONDITION_BLOCKS) {
  if (block.nodeType) CONDITION_BLOCK_BY_NODE_TYPE[block.nodeType] = block;
}

export function conditionBlockFor(nodeType: string): ConditionBlockDefinition | undefined {
  return CONDITION_BLOCK_BY_NODE_TYPE[nodeType as FlowNodeType];
}
