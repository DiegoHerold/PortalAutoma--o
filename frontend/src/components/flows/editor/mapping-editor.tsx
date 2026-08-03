"use client";

import { useMemo, useState } from "react";
import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/input";
import { TRANSFORM_OPTIONS, type MappingSpec } from "@/lib/flow-mapping";

type Row = {
  id: string;
  field: string;
  kind: "flow.input" | "flow.metadata" | "node.output" | "node.status" | "constant";
  nodeKey: string;
  path: string;
  constantValue: string;
  transform: string;
};

function displayPath(path: string): string {
  return path === "$" ? "" : path.replace(/^\$\./, "");
}

function toMappingPath(path: string): string {
  const trimmed = path.trim();
  if (!trimmed || trimmed === "$") return "$";
  return trimmed.startsWith("$.") ? trimmed : `$.${trimmed.replace(/^\.+/, "")}`;
}

function transformOf(spec: unknown): string {
  const raw = (spec as { transform?: string | string[] } | undefined)?.transform;
  if (Array.isArray(raw)) return raw[0] ?? "";
  return raw ?? "";
}

function mappingToRows(mapping: Record<string, MappingSpec>): Row[] {
  return Object.entries(mapping || {}).map(([field, spec], index) => {
    const id = `${field}-${index}`;
    const transform = transformOf(spec);
    if (typeof spec === "object" && spec !== null && "value" in (spec as Record<string, unknown>)) {
      const value = (spec as Record<string, unknown>).value;
      return { id, field, kind: "constant", nodeKey: "", path: "", constantValue: typeof value === "string" ? value : JSON.stringify(value), transform };
    }
    const source = String((spec as Record<string, unknown> | undefined)?.source ?? "flow.input");
    const path = displayPath(String((spec as Record<string, unknown> | undefined)?.path ?? "$"));
    const match = /^node\.(.+)\.(output|status)$/.exec(source);
    if (match) {
      return { id, field, kind: match[2] === "output" ? "node.output" : "node.status", nodeKey: match[1], path, constantValue: "", transform };
    }
    return { id, field, kind: source === "flow.metadata" ? "flow.metadata" : "flow.input", nodeKey: "", path, constantValue: "", transform };
  });
}

function rowsToMapping(rows: Row[]): Record<string, MappingSpec> {
  const mapping: Record<string, MappingSpec> = {};
  for (const row of rows) {
    if (!row.field.trim()) continue;
    const transform = row.transform ? { transform: row.transform } : {};
    if (row.kind === "constant") {
      let value: unknown = row.constantValue;
      try {
        value = JSON.parse(row.constantValue);
      } catch {
        // mantém como string bruta se não for JSON válido
      }
      mapping[row.field] = { value, ...transform } as MappingSpec;
    } else if (row.kind === "node.output" || row.kind === "node.status") {
      mapping[row.field] = { source: `node.${row.nodeKey}.${row.kind === "node.output" ? "output" : "status"}`, path: toMappingPath(row.path), ...transform } as MappingSpec;
    } else {
      mapping[row.field] = { source: row.kind, path: toMappingPath(row.path), ...transform } as MappingSpec;
    }
  }
  return mapping;
}

let rowSeq = 0;
function newRowId() {
  rowSeq += 1;
  return `row-${rowSeq}`;
}

export function MappingEditor({
  title,
  description,
  mapping,
  upstreamNodes,
  onChange,
  readOnly,
  allowTransform = false,
  fieldLabel = "campo que a etapa espera",
}: {
  title: string;
  description?: string;
  mapping: Record<string, MappingSpec>;
  upstreamNodes: { key: string; name: string }[];
  onChange: (mapping: Record<string, MappingSpec>) => void;
  readOnly?: boolean;
  /** Bloco "Transform Data": mostra um seletor de transformação (maiúsculas, número, ...) por campo. */
  allowTransform?: boolean;
  fieldLabel?: string;
}) {
  const [rows, setRows] = useState<Row[]>(() => mappingToRows(mapping));

  function commit(nextRows: Row[]) {
    setRows(nextRows);
    onChange(rowsToMapping(nextRows));
  }

  function addRow() {
    commit([...rows, { id: newRowId(), field: "", kind: "flow.input", nodeKey: upstreamNodes[0]?.key ?? "", path: "", constantValue: "", transform: "" }]);
  }

  function updateRow(id: string, patch: Partial<Row>) {
    commit(rows.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  function removeRow(id: string) {
    commit(rows.filter((r) => r.id !== id));
  }

  const fieldErrors = useMemo(() => {
    const errors: Record<string, string> = {};
    rows.forEach((row) => {
      if (!row.field.trim()) errors[row.id] = "Informe o campo de destino.";
      else if ((row.kind === "node.output" || row.kind === "node.status") && !row.nodeKey) errors[row.id] = "Selecione o nó de origem.";
    });
    return errors;
  }, [rows]);

  return (
    <div className="space-y-3">
      <div>
        <Label>{title}</Label>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </div>

      <div className="space-y-2">
        {rows.length === 0 && <p className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">Sem configuração, esta etapa recebe todos os dados de entrada do fluxo.</p>}
        {rows.map((row) => (
          <div key={row.id} className="space-y-2 rounded-lg border border-border bg-card p-3">
            <div className="flex items-center gap-2">
              <Input
                placeholder={fieldLabel}
                value={row.field}
                disabled={readOnly}
                onChange={(e) => updateRow(row.id, { field: e.target.value })}
                className="h-8 flex-1 text-xs"
              />
              <Select value={row.kind} disabled={readOnly} onChange={(e) => updateRow(row.id, { kind: e.target.value as Row["kind"] })} className="h-8 w-40 text-xs">
                <option value="flow.input">Entrada do fluxo</option>
                <option value="flow.metadata">Informação do fluxo</option>
                <option value="node.output">Resultado de outra etapa</option>
                <option value="node.status">Status de outra etapa</option>
                <option value="constant">Valor fixo</option>
              </Select>
              {!readOnly && (
                <Button size="icon" variant="ghost" title="Remover campo" onClick={() => removeRow(row.id)}>
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>

            {(row.kind === "node.output" || row.kind === "node.status") && (
              <Select value={row.nodeKey} disabled={readOnly} onChange={(e) => updateRow(row.id, { nodeKey: e.target.value })} className="h-8 text-xs">
                <option value="">Escolha a etapa de origem...</option>
                {upstreamNodes.map((n) => (
                  <option key={n.key} value={n.key}>
                    {n.name}
                  </option>
                ))}
              </Select>
            )}

            {row.kind === "constant" ? (
              <Input placeholder="valor fixo" value={row.constantValue} disabled={readOnly} onChange={(e) => updateRow(row.id, { constantValue: e.target.value })} className="h-8 text-xs" />
            ) : (
              <Input placeholder="campo (ex.: cliente.codigo)" value={row.path} disabled={readOnly} onChange={(e) => updateRow(row.id, { path: e.target.value })} className="h-8 text-xs" />
            )}

            {allowTransform && (
              <Select value={row.transform} disabled={readOnly} onChange={(e) => updateRow(row.id, { transform: e.target.value })} className="h-8 text-xs">
                <option value="">Sem transformação</option>
                {TRANSFORM_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            )}

            {fieldErrors[row.id] && <p className="text-[11px] text-destructive">{fieldErrors[row.id]}</p>}
          </div>
        ))}
        {!readOnly && (
          <Button size="sm" variant="outline" onClick={addRow}>
            <Plus className="h-3.5 w-3.5" /> Ajustar um campo
          </Button>
        )}
      </div>
    </div>
  );
}

export function summarizeMapping(mapping: Record<string, MappingSpec> | null | undefined): string {
  const count = Object.keys(mapping || {}).length;
  if (count === 0) return "sem mapeamento (usa a entrada do fluxo)";
  return `${count} campo(s) mapeado(s)`;
}
