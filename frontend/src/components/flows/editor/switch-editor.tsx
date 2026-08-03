"use client";

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { OperandFields, emptyOperand, operandToSpec, specToOperand, type Operand } from "@/components/flows/editor/condition-editor";
import { newSwitchCaseId, type SwitchCase, type SwitchConfig } from "@/components/flows/editor/branch-logic";

function parseCaseValue(raw: string): unknown {
  if (raw.trim() === "") return "";
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

function stringifyCaseValue(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

/**
 * Editor visual dos "casos" de um bloco Switch: qual campo é comparado (subject) e a lista
 * de valores que geram uma saída própria, mais a saída "Padrão" para o que sobrar.
 * Produz exatamente o formato lido por branch-logic.ts (switchConfigOf/switchCaseCondition).
 */
export function SwitchCaseEditor({
  value,
  onChange,
  upstreamNodes,
  readOnly,
}: {
  value: SwitchConfig;
  onChange: (next: SwitchConfig) => void;
  upstreamNodes: { key: string; name: string }[];
  readOnly?: boolean;
}) {
  const [subject, setSubject] = useState<Operand>(() => (value.subject ? specToOperand(value.subject) : emptyOperand("flow.input")));
  const [cases, setCases] = useState<{ id: string; label: string; valueText: string }[]>(() =>
    value.cases.map((c) => ({ id: c.id, label: c.label, valueText: stringifyCaseValue(c.value) })),
  );
  const [hasDefault, setHasDefault] = useState(value.hasDefault);

  function commit(nextSubject: Operand, nextCases: { id: string; label: string; valueText: string }[], nextHasDefault: boolean) {
    setSubject(nextSubject);
    setCases(nextCases);
    setHasDefault(nextHasDefault);
    const resolvedCases: SwitchCase[] = nextCases
      .filter((c) => c.label.trim() !== "")
      .map((c) => ({ id: c.id, label: c.label, value: parseCaseValue(c.valueText) }));
    onChange({ subject: operandToSpec(nextSubject), cases: resolvedCases, hasDefault: nextHasDefault });
  }

  function addCase() {
    commit(subject, [...cases, { id: newSwitchCaseId(), label: "", valueText: "" }], hasDefault);
  }

  function updateCase(id: string, patch: Partial<{ label: string; valueText: string }>) {
    commit(subject, cases.map((c) => (c.id === id ? { ...c, ...patch } : c)), hasDefault);
  }

  function removeCase(id: string) {
    commit(subject, cases.filter((c) => c.id !== id), hasDefault);
  }

  return (
    <div className="space-y-4">
      <div>
        <Label>Campo a testar</Label>
        <div className="mt-1.5">
          <OperandFields
            operand={subject}
            onChange={(patch) => commit({ ...subject, ...patch }, cases, hasDefault)}
            upstreamNodes={upstreamNodes}
            readOnly={readOnly}
            allowConstant={false}
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label>Casos (cada um vira uma saída própria)</Label>
        {cases.length === 0 && (
          <div className="rounded-lg border border-dashed border-border p-4">
            <p className="text-xs text-muted-foreground">Nenhum caso configurado — o bloco só terá a saída Padrão.</p>
          </div>
        )}
        {cases.map((c, index) => (
          <div key={c.id} className="flex items-center gap-2 rounded-lg border border-border bg-card p-2.5">
            <span className="w-5 shrink-0 text-center text-[11px] text-muted-foreground">{index + 1}</span>
            <Input
              placeholder="Nome do caso (ex.: Ativo)"
              value={c.label}
              disabled={readOnly}
              onChange={(e) => updateCase(c.id, { label: e.target.value })}
              className="h-8 flex-1 text-xs"
            />
            <Input
              placeholder='Valor (ex.: "ativo")'
              value={c.valueText}
              disabled={readOnly}
              onChange={(e) => updateCase(c.id, { valueText: e.target.value })}
              className="h-8 flex-1 text-xs font-mono"
            />
            {!readOnly && (
              <Button size="icon" variant="ghost" onClick={() => removeCase(c.id)}>
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        ))}
        {!readOnly && (
          <Button size="sm" variant="outline" onClick={addCase}>
            <Plus className="h-3.5 w-3.5" /> Adicionar caso
          </Button>
        )}
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={hasDefault} disabled={readOnly} onChange={(e) => commit(subject, cases, e.target.checked)} />
        Incluir saída Padrão (para valores que não batem com nenhum caso)
      </label>
    </div>
  );
}
