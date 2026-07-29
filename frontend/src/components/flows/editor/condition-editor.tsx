"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, Code2, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input, Label, Select, Textarea } from "@/components/ui/input";

// Espelha backend/modules/orchestration/flows/domain/mapping.py::evaluate_condition.
// O construtor visual cobre o caso comum (uma lista de regras combinadas por E/OU, cada
// uma podendo ser negada). Condições mais complexas (grupos aninhados) continuam
// editáveis via JSON avançado — o builder detecta esse caso e cai para o modo JSON sozinho.

type SourceKind = "flow.input" | "flow.metadata" | "node.output" | "node.status" | "constant";
type Operator = "equals" | "not_equals" | "exists" | "greater_than" | "less_than";

const OPERATOR_LABELS: Record<Operator, string> = {
  equals: "é igual a",
  not_equals: "é diferente de",
  exists: "existe (não é vazio)",
  greater_than: "é maior que",
  less_than: "é menor que",
};

type Operand = {
  kind: SourceKind;
  nodeKey: string;
  path: string;
  constantValue: string;
};

type Rule = {
  id: string;
  negate: boolean;
  left: Operand;
  operator: Operator;
  rightMode: "constant" | "field";
  right: Operand;
};

function emptyOperand(kind: SourceKind = "flow.input"): Operand {
  return { kind, nodeKey: "", path: "$", constantValue: "" };
}

let ruleSeq = 0;
function newRuleId() {
  ruleSeq += 1;
  return `rule-${ruleSeq}`;
}

function newRule(): Rule {
  return { id: newRuleId(), negate: false, left: emptyOperand(), operator: "equals", rightMode: "constant", right: emptyOperand("constant") };
}

function sourceStringFor(kind: SourceKind, nodeKey: string): string {
  if (kind === "node.output") return `node.${nodeKey}.output`;
  if (kind === "node.status") return `node.${nodeKey}.status`;
  return kind;
}

function parseConstant(raw: string): unknown {
  if (raw.trim() === "") return "";
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

function stringifyConstant(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

function operandToSpec(op: Operand): unknown {
  if (op.kind === "constant") return { value: parseConstant(op.constantValue) };
  return { source: sourceStringFor(op.kind, op.nodeKey), path: op.path || "$" };
}

function specToOperand(spec: unknown): Operand {
  if (typeof spec !== "object" || spec === null) {
    return { kind: "constant", nodeKey: "", path: "", constantValue: stringifyConstant(spec) };
  }
  const record = spec as Record<string, unknown>;
  if ("value" in record) {
    return { kind: "constant", nodeKey: "", path: "", constantValue: stringifyConstant(record.value) };
  }
  const source = String(record.source ?? "flow.input");
  const path = String(record.path ?? "$");
  const match = /^node\.(.+)\.(output|status)$/.exec(source);
  if (match) {
    return { kind: match[2] === "output" ? "node.output" : "node.status", nodeKey: match[1], path, constantValue: "" };
  }
  return { kind: source === "flow.metadata" ? "flow.metadata" : "flow.input", nodeKey: "", path, constantValue: "" };
}

function ruleToExpr(rule: Rule): Record<string, unknown> {
  const left = operandToSpec(rule.left);
  let expr: Record<string, unknown>;
  if (rule.operator === "exists") {
    expr = { operator: "exists", left };
  } else {
    const right = rule.rightMode === "constant" ? parseConstant(rule.right.constantValue) : operandToSpec(rule.right);
    expr = { operator: rule.operator, left, right };
  }
  return rule.negate ? { operator: "not", condition: expr } : expr;
}

function exprToRule(expr: Record<string, unknown>): Rule | null {
  let negate = false;
  let inner = expr;
  if (expr.operator === "not") {
    const nested = expr.condition;
    if (typeof nested !== "object" || nested === null) return null;
    negate = true;
    inner = nested as Record<string, unknown>;
  }
  const operator = inner.operator;
  if (typeof operator !== "string" || !(operator in OPERATOR_LABELS)) return null;
  const left = specToOperand(inner.left);
  const rightRaw = inner.right;
  const rightIsField = typeof rightRaw === "object" && rightRaw !== null;
  const right = rightIsField ? specToOperand(rightRaw) : { ...emptyOperand("constant"), constantValue: rightRaw === undefined ? "" : stringifyConstant(rightRaw) };
  return { id: newRuleId(), negate, left, operator: operator as Operator, rightMode: rightIsField ? "field" : "constant", right };
}

/** Converte o JSON de condição (formato do backend) em regras editáveis; retorna null se for complexo demais para o builder visual (grupo aninhado, etc.). */
function conditionToRules(condition: Record<string, unknown> | null): { combinator: "and" | "or"; rules: Rule[] } | null {
  if (!condition) return { combinator: "and", rules: [] };
  if (condition.operator === "and" || condition.operator === "or") {
    const items = condition.conditions;
    if (!Array.isArray(items)) return null;
    const rules: Rule[] = [];
    for (const item of items) {
      if (typeof item !== "object" || item === null) return null;
      const rule = exprToRule(item as Record<string, unknown>);
      if (!rule) return null;
      rules.push(rule);
    }
    return { combinator: condition.operator, rules };
  }
  const single = exprToRule(condition);
  if (!single) return null;
  return { combinator: "and", rules: [single] };
}

function rulesToCondition(combinator: "and" | "or", rules: Rule[]): Record<string, unknown> | null {
  if (rules.length === 0) return null;
  if (rules.length === 1) return ruleToExpr(rules[0]);
  return { operator: combinator, conditions: rules.map(ruleToExpr) };
}

export function describeCondition(condition: Record<string, unknown> | null): string {
  if (!condition) return "sem condição (sempre executa)";
  const parsed = conditionToRules(condition);
  if (!parsed || parsed.rules.length === 0) return "condição avançada (JSON)";
  const parts = parsed.rules.map((r) => {
    const leftLabel = r.left.kind === "constant" ? stringifyConstant(parseConstant(r.left.constantValue)) : `${r.left.kind}${r.left.nodeKey ? `(${r.left.nodeKey})` : ""}`;
    if (r.operator === "exists") return `${r.negate ? "não " : ""}${leftLabel} existe`;
    const rightLabel = r.rightMode === "constant" ? stringifyConstant(parseConstant(r.right.constantValue)) : `${r.right.kind}${r.right.nodeKey ? `(${r.right.nodeKey})` : ""}`;
    return `${r.negate ? "não: " : ""}${leftLabel} ${OPERATOR_LABELS[r.operator]} ${rightLabel}`;
  });
  return parts.join(parsed.combinator === "and" ? " E " : " OU ");
}

function OperandFields({
  operand,
  onChange,
  upstreamNodes,
  readOnly,
  allowConstant = true,
  constantPlaceholder,
}: {
  operand: Operand;
  onChange: (patch: Partial<Operand>) => void;
  upstreamNodes: { key: string; name: string }[];
  readOnly?: boolean;
  allowConstant?: boolean;
  constantPlaceholder?: string;
}) {
  return (
    <div className="flex flex-1 flex-wrap items-center gap-1.5">
      <Select value={operand.kind} disabled={readOnly} onChange={(e) => onChange({ kind: e.target.value as SourceKind })} className="h-8 w-[150px] text-xs">
        <option value="flow.input">Entrada do fluxo</option>
        <option value="flow.metadata">Metadados do fluxo</option>
        <option value="node.output">Saída de outro nó</option>
        <option value="node.status">Status de outro nó</option>
        {allowConstant && <option value="constant">Valor fixo</option>}
      </Select>
      {(operand.kind === "node.output" || operand.kind === "node.status") && (
        <Select value={operand.nodeKey} disabled={readOnly} onChange={(e) => onChange({ nodeKey: e.target.value })} className="h-8 w-32 text-xs">
          <option value="">nó...</option>
          {upstreamNodes.map((n) => (
            <option key={n.key} value={n.key}>
              {n.name}
            </option>
          ))}
        </Select>
      )}
      {operand.kind === "constant" ? (
        <Input
          placeholder={constantPlaceholder ?? 'valor (ex: "ok", 42, true)'}
          value={operand.constantValue}
          disabled={readOnly}
          onChange={(e) => onChange({ constantValue: e.target.value })}
          className="h-8 flex-1 min-w-[110px] text-xs font-mono"
        />
      ) : (
        <Input
          placeholder="$.campo (ou $ p/ valor inteiro)"
          value={operand.path}
          disabled={readOnly}
          onChange={(e) => onChange({ path: e.target.value })}
          className="h-8 flex-1 min-w-[110px] text-xs font-mono"
        />
      )}
    </div>
  );
}

export function ConditionEditor({
  value,
  onChange,
  upstreamNodes,
  readOnly,
  emptyHint = "Sem condição — este passo sempre executa quando alcançado.",
}: {
  value: Record<string, unknown> | null;
  onChange: (value: Record<string, unknown> | null) => void;
  upstreamNodes: { key: string; name: string }[];
  readOnly?: boolean;
  emptyHint?: string;
}) {
  const parsedInitial = useMemo(() => conditionToRules(value), [value]);
  const [combinator, setCombinator] = useState<"and" | "or">(parsedInitial?.combinator ?? "and");
  const [rules, setRules] = useState<Rule[]>(parsedInitial?.rules ?? []);
  const [advanced, setAdvanced] = useState(parsedInitial === null && Boolean(value));
  const [rawJson, setRawJson] = useState(() => JSON.stringify(value ?? {}, null, 2));

  const tooComplex = parsedInitial === null && Boolean(value);

  function commit(nextCombinator: "and" | "or", nextRules: Rule[]) {
    setCombinator(nextCombinator);
    setRules(nextRules);
    onChange(rulesToCondition(nextCombinator, nextRules));
  }

  function addRule() {
    commit(combinator, [...rules, newRule()]);
  }

  function updateRule(id: string, patch: Partial<Rule>) {
    commit(combinator, rules.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  function updateOperand(id: string, side: "left" | "right", patch: Partial<Operand>) {
    commit(
      combinator,
      rules.map((r) => (r.id === id ? { ...r, [side]: { ...r[side], ...patch } } : r)),
    );
  }

  function removeRule(id: string) {
    commit(combinator, rules.filter((r) => r.id !== id));
  }

  function applyRawJson() {
    try {
      const parsed = rawJson.trim() ? JSON.parse(rawJson) : null;
      onChange(parsed);
      const reparsed = conditionToRules(parsed);
      if (reparsed) {
        setCombinator(reparsed.combinator);
        setRules(reparsed.rules);
        setAdvanced(false);
      }
    } catch {
      // JSON inválido — mensagem já é implícita (não aplica, usuário continua editando).
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">Todas as regras abaixo precisam ser verdadeiras ou apenas uma, conforme o combinador escolhido.</p>
        {!readOnly && !tooComplex && (
          <button type="button" className="inline-flex shrink-0 items-center gap-1 text-xs text-primary underline underline-offset-2" onClick={() => setAdvanced((v) => !v)}>
            <Code2 className="h-3.5 w-3.5" /> {advanced ? "Usar construtor visual" : "Editar como JSON"}
          </button>
        )}
      </div>

      {tooComplex && (
        <div className="flex items-start gap-2 rounded-md border border-warning/30 bg-warning/5 p-2.5 text-xs text-warning">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          Esta condição tem uma estrutura mais complexa (grupos aninhados) e só pode ser editada em JSON.
        </div>
      )}

      {advanced || tooComplex ? (
        <div className="space-y-2">
          <Textarea rows={8} className="font-mono text-xs" value={rawJson} onChange={(e) => setRawJson(e.target.value)} disabled={readOnly} placeholder="null ou {...}" />
          {!readOnly && (
            <Button size="sm" variant="outline" onClick={applyRawJson}>
              Aplicar JSON
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-2.5">
          {rules.length === 0 && <p className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">{emptyHint}</p>}

          {rules.length > 1 && (
            <div className="flex items-center gap-2 text-xs">
              <Label className="!mb-0">Combinar regras com:</Label>
              <Select value={combinator} disabled={readOnly} onChange={(e) => commit(e.target.value as "and" | "or", rules)} className="h-8 w-32 text-xs">
                <option value="and">E (todas)</option>
                <option value="or">OU (qualquer)</option>
              </Select>
            </div>
          )}

          {rules.map((rule, index) => (
            <div key={rule.id} className="space-y-1.5 rounded-md border border-border p-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-medium text-muted-foreground">Regra {index + 1}</span>
                {!readOnly && (
                  <div className="flex items-center gap-2">
                    <label className="flex items-center gap-1 text-[11px] text-muted-foreground">
                      <input type="checkbox" checked={rule.negate} onChange={(e) => updateRule(rule.id, { negate: e.target.checked })} />
                      negar (NÃO)
                    </label>
                    <Button size="icon" variant="ghost" onClick={() => removeRule(rule.id)}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] text-muted-foreground">Se</span>
                <OperandFields operand={rule.left} onChange={(patch) => updateOperand(rule.id, "left", patch)} upstreamNodes={upstreamNodes} readOnly={readOnly} allowConstant={false} />
              </div>

              <div className="flex flex-wrap items-center gap-1.5">
                <Select
                  value={rule.operator}
                  disabled={readOnly}
                  onChange={(e) => updateRule(rule.id, { operator: e.target.value as Operator })}
                  className="h-8 w-40 text-xs"
                >
                  {(Object.entries(OPERATOR_LABELS) as [Operator, string][]).map(([op, label]) => (
                    <option key={op} value={op}>
                      {label}
                    </option>
                  ))}
                </Select>

                {rule.operator !== "exists" && (
                  <>
                    <Select
                      value={rule.rightMode}
                      disabled={readOnly}
                      onChange={(e) => {
                        const nextMode = e.target.value as "constant" | "field";
                        updateRule(rule.id, {
                          rightMode: nextMode,
                          right: { ...rule.right, kind: nextMode === "constant" ? "constant" : rule.right.kind === "constant" ? "flow.input" : rule.right.kind },
                        });
                      }}
                      className="h-8 w-28 text-xs"
                    >
                      <option value="constant">valor fixo</option>
                      <option value="field">outro campo</option>
                    </Select>
                    <OperandFields
                      operand={rule.right}
                      onChange={(patch) => updateOperand(rule.id, "right", patch)}
                      upstreamNodes={upstreamNodes}
                      readOnly={readOnly}
                      allowConstant={rule.rightMode === "constant"}
                    />
                  </>
                )}
              </div>
            </div>
          ))}

          {!readOnly && (
            <Button size="sm" variant="outline" onClick={addRule}>
              <Plus className="h-3.5 w-3.5" /> Adicionar regra
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
