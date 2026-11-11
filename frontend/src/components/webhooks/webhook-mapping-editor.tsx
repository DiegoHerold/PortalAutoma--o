"use client";

import { useMemo, useState } from "react";
import { Code2, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input, Label, Select, Textarea } from "@/components/ui/input";

type SourceKind = "body" | "headers" | "query_params";
type MappingRow = { id: string; target: string; source: SourceKind; path: string };

let rowSeq = 0;
function newRowId() {
  rowSeq += 1;
  return `webhook-map-${rowSeq}`;
}

function mappingToRows(mapping: Record<string, string> | null | undefined): MappingRow[] {
  return Object.entries(mapping || {}).map(([target, rawPath]) => {
    const parts = String(rawPath).split(".");
    const source = ["body", "headers", "query_params"].includes(parts[0]) ? (parts[0] as SourceKind) : "body";
    const path = source === parts[0] ? parts.slice(1).join(".") : parts.join(".");
    return { id: newRowId(), target, source, path };
  });
}

function rowsToMapping(rows: MappingRow[]): Record<string, string> | null {
  const entries = rows
    .filter((row) => row.target.trim() && row.path.trim())
    .map((row) => [row.target.trim(), `${row.source}.${row.path.trim()}`]);
  return entries.length ? Object.fromEntries(entries) : null;
}

export function WebhookMappingEditor({
  value,
  onChange,
}: {
  value: Record<string, string> | null;
  onChange: (mapping: Record<string, string> | null) => void;
}) {
  const [rows, setRows] = useState<MappingRow[]>(() => mappingToRows(value));
  const [advanced, setAdvanced] = useState(false);
  const [rawJson, setRawJson] = useState(() => JSON.stringify(value ?? {}, null, 2));
  const [jsonError, setJsonError] = useState<string | null>(null);

  function commit(nextRows: MappingRow[]) {
    setRows(nextRows);
    const next = rowsToMapping(nextRows);
    setRawJson(JSON.stringify(next ?? {}, null, 2));
    onChange(next);
  }

  function addRow() {
    commit([...rows, { id: newRowId(), target: "", source: "body", path: "" }]);
  }

  function updateRow(id: string, patch: Partial<MappingRow>) {
    commit(rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  }

  function removeRow(id: string) {
    commit(rows.filter((row) => row.id !== id));
  }

  function applyJson() {
    try {
      const parsed = JSON.parse(rawJson || "{}") as Record<string, unknown>;
      const normalized: Record<string, string> = {};
      Object.entries(parsed).forEach(([key, item]) => {
        if (typeof item !== "string") throw new Error(`${key} precisa ser uma string.`);
        normalized[key] = item;
      });
      setJsonError(null);
      setRows(mappingToRows(normalized));
      onChange(Object.keys(normalized).length ? normalized : null);
      setAdvanced(false);
    } catch (err) {
      setJsonError(err instanceof Error ? err.message : "JSON inválido.");
    }
  }

  const invalidRows = useMemo(() => {
    const invalid = new Set<string>();
    rows.forEach((row) => {
      if (!row.target.trim() || !row.path.trim() || /\s/.test(row.target)) invalid.add(row.id);
    });
    return invalid;
  }, [rows]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <Label>Mapeamento de parâmetros</Label>
          <p className="text-xs text-muted-foreground">
            Sintaxe aceita pelo backend: body.campo, headers.nome, query_params.nome. Constantes ainda não fazem parte deste contrato.
          </p>
        </div>
        <button type="button" className="inline-flex items-center gap-1 text-xs text-primary underline underline-offset-2" onClick={() => setAdvanced((value) => !value)}>
          <Code2 className="h-3.5 w-3.5" /> {advanced ? "Modo visual" : "JSON avancado"}
        </button>
      </div>

      {advanced ? (
        <div className="space-y-2">
          <Textarea className="min-h-[180px] font-mono text-xs" value={rawJson} onChange={(event) => setRawJson(event.target.value)} />
          {jsonError && <p className="text-xs text-destructive">{jsonError}</p>}
          <Button size="sm" variant="outline" onClick={applyJson}>
            Aplicar JSON
          </Button>
        </div>
      ) : (
        <div className="space-y-2">
          {rows.length === 0 && <p className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">Sem mapeamento: o backend envia webhook_data, headers e query_params.</p>}
          {rows.map((row) => (
            <div key={row.id} className="grid gap-2 rounded-md border border-border p-2 md:grid-cols-[1fr_140px_1fr_auto] md:items-center">
              <Input className="h-9 text-xs" placeholder="parametro_destino" value={row.target} onChange={(event) => updateRow(row.id, { target: event.target.value })} />
              <Select className="h-9 text-xs" value={row.source} onChange={(event) => updateRow(row.id, { source: event.target.value as SourceKind })}>
                <option value="body">Payload</option>
                <option value="headers">Headers</option>
                <option value="query_params">Query</option>
              </Select>
              <Input className="h-9 font-mono text-xs" placeholder="company_id" value={row.path} onChange={(event) => updateRow(row.id, { path: event.target.value })} />
              <Button size="icon" variant="ghost" onClick={() => removeRow(row.id)}>
                <Trash2 className="h-4 w-4" />
              </Button>
              {invalidRows.has(row.id) && <p className="text-xs text-destructive md:col-span-4">Destino e path são obrigatórios; destino não deve conter espaços.</p>}
            </div>
          ))}
          <Button size="sm" variant="outline" onClick={addRow}>
            <Plus className="h-3.5 w-3.5" /> Adicionar mapping
          </Button>
        </div>
      )}
    </div>
  );
}
