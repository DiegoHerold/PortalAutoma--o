// Regras compartilhadas de ramificação usadas pelos blocos "If / Else" e "Switch".
//
// Nenhum dos dois usa node.condition: isso deixaria o próprio nó "skipped" quando a regra
// não bate, e uma aresta "conditional" só é considerada satisfeita quando a origem
// "succeeded" (ver backend/modules/orchestration/flows/application/use_cases.py::_edge_satisfied).
// Ou seja, se o nó dependesse de node.condition para decidir Verdadeiro/Falso, o caminho
// Falso nunca teria chance de rodar (a origem estaria "skipped", não "succeeded").
//
// Em vez disso, o nó sempre é bem-sucedido (passthrough, igual "condition"/"join" hoje) e
// cada aresta que sai dele carrega sua própria condição "conditional":
//   - If/Else: aresta "Verdadeiro" = a regra escolhida; aresta "Falso" = a mesma regra
//     envolvida em {operator: "not", ...}.
//   - Switch: uma aresta "conditional" por caso (subject equals valor do caso) + uma aresta
//     "Padrão" cuja condição é o E-lógico da negação de todos os casos.
// Isso já é 100% suportado pelo motor hoje (evaluate_condition já entende and/or/not/equals) —
// ver os testes em backend/modules/orchestration/flows/tests/test_flow_domain.py.

import type { FlowEdgeType, FlowNode } from "@/types/flow";

export type ConditionExpr = Record<string, unknown>;

/** Condição sempre verdadeira — usada quando o usuário ainda não configurou nenhuma regra. */
export const ALWAYS_TRUE_CONDITION: ConditionExpr = { operator: "exists", left: { value: true } };

export function negateCondition(condition: ConditionExpr | null | undefined): ConditionExpr {
  return { operator: "not", condition: condition ?? ALWAYS_TRUE_CONDITION };
}

/** Comparação estrutural (ignora ordem de chaves — JSONB do Postgres não preserva ordem). */
export function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
    return a.every((item, i) => deepEqual(item, b[i]));
  }
  if (typeof a === "object" && a !== null && typeof b === "object" && b !== null) {
    const aKeys = Object.keys(a as Record<string, unknown>);
    const bKeys = Object.keys(b as Record<string, unknown>);
    if (aKeys.length !== bKeys.length) return false;
    return aKeys.every((key) => key in (b as Record<string, unknown>) && deepEqual((a as Record<string, unknown>)[key], (b as Record<string, unknown>)[key]));
  }
  return false;
}

// ---- If / Else ----

export const IF_ELSE_TRUE_HANDLE = "true";
export const IF_ELSE_FALSE_HANDLE = "false";

export function ifElseRule(node: Pick<FlowNode, "configuration">): ConditionExpr | null {
  const rule = (node.configuration as Record<string, unknown> | undefined)?.rule;
  return rule && typeof rule === "object" ? (rule as ConditionExpr) : null;
}

export function ifElseTrueCondition(node: Pick<FlowNode, "configuration">): ConditionExpr {
  return ifElseRule(node) ?? ALWAYS_TRUE_CONDITION;
}

export function ifElseFalseCondition(node: Pick<FlowNode, "configuration">): ConditionExpr {
  return negateCondition(ifElseRule(node));
}

/** Handle de origem (Verdadeiro/Falso) para uma aresta já persistida, a partir da condição gravada nela. */
export function ifElseHandleForEdge(node: Pick<FlowNode, "configuration">, edge: { edge_type: string; condition: unknown }): string {
  if (edge.edge_type === "conditional" && deepEqual(edge.condition, ifElseFalseCondition(node))) return IF_ELSE_FALSE_HANDLE;
  return IF_ELSE_TRUE_HANDLE;
}

// ---- Switch ----

export type SwitchCase = { id: string; label: string; value: unknown };
export type SwitchConfig = { subject: ConditionExpr | null; cases: SwitchCase[]; hasDefault: boolean };

export const SWITCH_DEFAULT_HANDLE = "default";

let switchCaseSeq = 0;
export function newSwitchCaseId(): string {
  switchCaseSeq += 1;
  return `case_${Date.now().toString(36)}_${switchCaseSeq}`;
}

export function switchConfigOf(node: Pick<FlowNode, "configuration">): SwitchConfig {
  const raw = (node.configuration as Record<string, unknown> | undefined)?.switch as Partial<SwitchConfig> | undefined;
  return {
    subject: raw?.subject && typeof raw.subject === "object" ? (raw.subject as ConditionExpr) : null,
    cases: Array.isArray(raw?.cases) ? (raw!.cases as SwitchCase[]) : [],
    hasDefault: raw?.hasDefault ?? true,
  };
}

export function switchCaseCondition(subject: ConditionExpr | null, value: unknown): ConditionExpr {
  return { operator: "equals", left: subject ?? { value: null }, right: { value } };
}

export function switchDefaultCondition(subject: ConditionExpr | null, cases: SwitchCase[]): ConditionExpr {
  if (cases.length === 0) return ALWAYS_TRUE_CONDITION;
  return { operator: "and", conditions: cases.map((c) => ({ operator: "not", condition: switchCaseCondition(subject, c.value) })) };
}

/** Handle de origem (case id ou "default") para uma aresta já persistida, a partir da condição gravada nela. */
export function switchHandleForEdge(node: Pick<FlowNode, "configuration">, edge: { edge_type: string; condition: unknown }): string {
  const { subject, cases } = switchConfigOf(node);
  for (const c of cases) {
    if (deepEqual(edge.condition, switchCaseCondition(subject, c.value))) return c.id;
  }
  return SWITCH_DEFAULT_HANDLE;
}

// ---- Wiring usado pelo editor (flow-editor.tsx) ----

/**
 * Ao arrastar uma conexão a partir de um handle nomeado (Verdadeiro/Falso, um caso do Switch
 * ou Padrão), decide o edge_type/condition reais da aresta a ser criada. Para qualquer outro
 * node_type mantém o comportamento de sempre: aresta "success" sem condição.
 */
export function deriveEdgeSpecForConnection(
  sourceNode: Pick<FlowNode, "node_type" | "configuration"> | undefined,
  sourceHandleId: string | null,
): { edgeType: FlowEdgeType; condition: ConditionExpr | null } {
  if (!sourceNode) return { edgeType: "success", condition: null };
  if (sourceNode.node_type === "if_else") {
    const condition = sourceHandleId === IF_ELSE_FALSE_HANDLE ? ifElseFalseCondition(sourceNode) : ifElseTrueCondition(sourceNode);
    return { edgeType: "conditional", condition };
  }
  if (sourceNode.node_type === "switch") {
    const { subject, cases } = switchConfigOf(sourceNode);
    const matchedCase = cases.find((c) => c.id === sourceHandleId);
    const condition = matchedCase ? switchCaseCondition(subject, matchedCase.value) : switchDefaultCondition(subject, cases);
    return { edgeType: "conditional", condition };
  }
  return { edgeType: "success", condition: null };
}

/** Rótulo amigável para a aresta no canvas (substitui o nome cru do edge_type nas saídas ramificadas). */
export function edgeBranchLabelFor(sourceNode: Pick<FlowNode, "node_type" | "configuration"> | undefined, sourceHandleId: string): string | undefined {
  if (!sourceNode) return undefined;
  if (sourceNode.node_type === "if_else") return sourceHandleId === IF_ELSE_FALSE_HANDLE ? "Falso" : "Verdadeiro";
  if (sourceNode.node_type === "switch") {
    if (sourceHandleId === SWITCH_DEFAULT_HANDLE) return "Padrão";
    const match = switchConfigOf(sourceNode).cases.find((c) => c.id === sourceHandleId);
    return match ? match.label || String(match.value) : undefined;
  }
  return undefined;
}
