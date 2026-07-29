"use client";

import { useMemo, useState } from "react";
import { Plus, Trash2, FlaskConical, Code2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { MappingError, resolveMapping, type MappingSpec } from "@/lib/flow-mapping";

type Row = {
  id: string;
  field: string;
  kind: "flow.input" | "flow.metadata" | "node.output" | "node.status" | "constant";
  nodeKey: string;
  path: string;
  constantValue: string;
};

function mappingToRows(mapping: Record<string, MappingSpec>): Row[] {
  return Object.entries(mapping || {}).map(([field, spec], index) => {
    const id = `${field}-${index}`;
    if (typeof spec === "object" && spec !== null && "value" in (spec as Record<string, unknown>)) {
      const value = (spec as Record<string, unknown>).value;
      return { id, field, kind: "constant", nodeKey: "", path: "", constantValue: typeof value === "string" ? value : JSON.stringify(value) };
    }
    const source = String((spec as Record<string, unknown> | undefined)?.source ?? "flow.input");
    const path = String((spec as Record<string, unknown> | undefined)?.path ?? "$");
    const match = /^node\.(.+)\.(output|status)$/.exec(source);
    if (match) {
      return { id, field, kind: match[2] === "output" ? "node.output" : "node.status", nodeKey: match[1], path, constantValue: "" };
    }
    return { id, field, kind: source === "flow.metadata" ? "flow.metadata" : "flow.input", nodeKey: "", path, constantValue: "" };
  });
}

function rowsToMapping(rows: Row[]): Record<string, MappingSpec> {
  const mapping: Record<string, MappingSpec> = {};
  for (const row of rows) {
    if (!row.field.trim()) continue;
    if (row.kind === "constant") {
      let value: unknown = row.constantValue;
      try {
        value = JSON.parse(row.constantValue);
      } catch {
        // mantém como string bruta se não for JSON válido
      }
      mapping[row.field] = { value };
    } else if (row.kind === "node.output" || row.kind === "node.status") {
      mapping[row.field] = { source: `node.${row.nodeKey}.${row.kind === "node.output" ? "output" : "status"}`, path: row.path || "$" };
    } else {
      mapping[row.field] = { source: row.kind, path: row.path || "$" };
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
}: {
  title: string;
  description?: string;
  mapping: Record<string, MappingSpec>;
  upstreamNodes: { key: string; name: string }[];
  onChange: (mapping: Record<string, MappingSpec>) => void;
  readOnly?: boolean;
}) {
  const [rows, setRows] = useState<Row[]>(() => mappingToRows(mapping));
  const [advanced, setAdvanced] = useState(false);
  const [rawJson, setRawJson] = useState(() => JSON.stringify(mapping, null, 2));
  const [testOpen, setTestOpen] = useState(false);
  const [sampleContext, setSampleContext] = useState(() => defaultSampleContext(upstreamNodes));
  const [testResult, setTestResult] = useState<{ ok: true; value: Record<string, unknown> } | { ok: false; error: string } | null>(null);

  function commit(nextRows: Row[]) {
    setRows(nextRows);
    onChange(rowsToMapping(nextRows));
  }

  function addRow() {
    commit([...rows, { id: newRowId(), field: "", kind: "flow.input", nodeKey: upstreamNodes[0]?.key ?? "", path: "$", constantValue: "" }]);
  }

  function updateRow(id: string, patch: Partial<Row>) {
    commit(rows.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  function removeRow(id: string) {
    commit(rows.filter((r) => r.id !== id));
  }

  function applyRawJson() {
    try {
      const parsed = JSON.parse(rawJson);
      setRows(mappingToRows(parsed));
      onChange(parsed);
      setAdvanced(false);
    } catch {
      // erro de JSON fica visível pelo próprio textarea; não aplica.
    }
  }

  function runTest() {
    try {
      const context = JSON.parse(sampleContext);
      const value = resolveMapping(rowsToMapping(rows), context);
      setTestResult({ ok: true, value });
    } catch (err) {
      setTestResult({ ok: false, error: err instanceof MappingError ? err.message : err instanceof Error ? err.message : "Erro desconhecido" });
    }
  }

  const fieldErrors = useMemo(() => {
    const errors: Record<string, string> = {};
    rows.forEach((row) => {
      if (!row.field.trim()) errors[row.id] = "Informe o campo de destino.";
      else if ((row.kind === "node.output" || row.kind === "node.status") && !row.nodeKey) errors[row.id] = "Selecione o nó de origem.";
      else if (row.kind !== "constant" && row.path && row.path !== "$" && !row.path.startsWith("$.")) errors[row.id] = 'Path deve começar com "$."';
    });
    return errors;
  }, [rows]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <Label>{title}</Label>
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </div>
        {!readOnly && (
          <button type="button" className="inline-flex items-center gap-1 text-xs text-primary underline underline-offset-2" onClick={() => setAdvanced((v) => !v)}>
            <Code2 className="h-3.5 w-3.5" /> {advanced ? "Usar editor visual" : "Editar como JSON"}
          </button>
        )}
      </div>

      {advanced ? (
        <div className="space-y-2">
          <Textarea rows={8} className="font-mono text-xs" value={rawJson} onChange={(e) => setRawJson(e.target.value)} disabled={readOnly} />
          {!readOnly && (
            <Button size="sm" variant="outline" onClick={applyRawJson}>
              Aplicar JSON
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {rows.length === 0 && <p className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">Nenhum campo mapeado ainda.</p>}
          {rows.map((row) => (
            <div key={row.id} className="space-y-1.5 rounded-md border border-border p-2.5">
              <div className="flex items-center gap-2">
                <Input
                  placeholder="campo de destino"
                  value={row.field}
                  disabled={readOnly}
                  onChange={(e) => updateRow(row.id, { field: e.target.value })}
                  className="h-8 flex-1 text-xs"
                />
                <Select value={row.kind} disabled={readOnly} onChange={(e) => updateRow(row.id, { kind: e.target.value as Row["kind"] })} className="h-8 w-40 text-xs">
                  <option value="flow.input">Entrada do fluxo</option>
                  <option value="flow.metadata">Metadados do fluxo</option>
                  <option value="node.output">Saída de outro nó</option>
                  <option value="node.status">Status de outro nó</option>
                  <option value="constant">Valor constante</option>
                </Select>
                {!readOnly && (
                  <Button size="icon" variant="ghost" onClick={() => removeRow(row.id)}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>

              {(row.kind === "node.output" || row.kind === "node.status") && (
                <Select value={row.nodeKey} disabled={readOnly} onChange={(e) => updateRow(row.id, { nodeKey: e.target.value })} className="h-8 text-xs">
                  <option value="">Selecione o nó...</option>
                  {upstreamNodes.map((n) => (
                    <option key={n.key} value={n.key}>
                      {n.name} ({n.key})
                    </option>
                  ))}
                </Select>
              )}

              {row.kind === "constant" ? (
                <Input
                  placeholder='valor (texto ou JSON, ex: "ok" ou 42)'
                  value={row.constantValue}
                  disabled={readOnly}
                  onChange={(e) => updateRow(row.id, { constantValue: e.target.value })}
                  className="h-8 text-xs font-mono"
                />
              ) : (
                <Input
                  placeholder="$.campo.subcampo (ou $ para o valor inteiro)"
                  value={row.path}
                  disabled={readOnly}
                  onChange={(e) => updateRow(row.id, { path: e.target.value })}
                  className="h-8 text-xs font-mono"
                />
              )}

              {fieldErrors[row.id] && <p className="text-[11px] text-destructive">{fieldErrors[row.id]}</p>}
            </div>
          ))}
          {!readOnly && (
            <Button size="sm" variant="outline" onClick={addRow}>
              <Plus className="h-3.5 w-3.5" /> Adicionar campo
            </Button>
          )}
        </div>
      )}

      <div className="rounded-md border border-dashed border-border p-2.5">
        <button type="button" className="inline-flex items-center gap-1.5 text-xs font-medium text-foreground" onClick={() => setTestOpen((v) => !v)}>
          <FlaskConical className="h-3.5 w-3.5 text-primary" /> Testar mapping
        </button>
        {testOpen && (
          <div className="mt-2 space-y-2">
            <p className="text-[11px] text-muted-foreground">Informe um contexto de exemplo (entrada do fluxo e saídas de nós já executados) e veja o resultado do mapeamento.</p>
            <Textarea rows={6} className="font-mono text-xs" value={sampleContext} onChange={(e) => setSampleContext(e.target.value)} />
            <Button size="sm" onClick={runTest}>
              Executar teste
            </Button>
            {testResult && (
              <div className={testResult.ok ? "rounded-md border border-success/30 bg-success/5 p-2" : "rounded-md border border-destructive/30 bg-destructive/5 p-2"}>
                {testResult.ok ? (
                  <pre className="max-h-40 overflow-auto text-[11px]">{JSON.stringify(testResult.value, null, 2)}</pre>
                ) : (
                  <p className="text-[11px] text-destructive">{testResult.error}</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function defaultSampleContext(upstreamNodes: { key: string; name: string }[]): string {
  const nodes: Record<string, unknown> = {};
  upstreamNodes.forEach((n) => {
    nodes[n.key] = { status: "succeeded", output: {} };
  });
  return JSON.stringify({ flow: { input: {}, metadata: {} }, nodes }, null, 2);
}

export function summarizeMapping(mapping: Record<string, MappingSpec> | null | undefined): string {
  const count = Object.keys(mapping || {}).length;
  if (count === 0) return "sem mapeamento (usa a entrada do fluxo)";
  return `${count} campo(s) mapeado(s)`;
}
