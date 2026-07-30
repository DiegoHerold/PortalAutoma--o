"use client";

import { useMemo, useState } from "react";

import { DetailJson } from "@/components/shared/detail-json";
import { Tabs } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

type DiffRow = { path: string; before: unknown; after: unknown; kind: "added" | "removed" | "changed" };

export function JsonDiff({ before, after }: { before: unknown; after: unknown }) {
  const [mode, setMode] = useState("diff");
  const rows = useMemo(() => diffValues(before, after), [before, after]);

  return (
    <div className="space-y-3">
      <Tabs items={[{ value: "diff", label: "Diff", count: rows.length }, { value: "before", label: "Antes" }, { value: "after", label: "Depois" }]} value={mode} onValueChange={setMode} />
      {mode === "before" && <DetailJson data={before ?? {}} />}
      {mode === "after" && <DetailJson data={after ?? {}} />}
      {mode === "diff" && (rows.length ? <div className="overflow-hidden rounded-lg border border-border">{rows.map((row) => <DiffLine key={row.path} row={row} />)}</div> : <p className="rounded-md border border-dashed border-border px-3 py-4 text-sm text-muted-foreground">Não há alterações de campos para comparar.</p>)}
    </div>
  );
}

function DiffLine({ row }: { row: DiffRow }) {
  const tone = row.kind === "added" ? "text-success bg-success/5" : row.kind === "removed" ? "text-destructive bg-destructive/5" : "text-warning bg-warning/5";
  const label = row.kind === "added" ? "Adicionado" : row.kind === "removed" ? "Removido" : "Alterado";
  return (
    <div className="grid gap-1 border-b border-border px-3 py-2.5 last:border-b-0 sm:grid-cols-[minmax(10rem,1fr)_minmax(0,1fr)_minmax(0,1fr)] sm:gap-3">
      <div><p className="tabular text-xs font-medium">{row.path}</p><span className={cn("text-[11px] font-medium", tone)}>{label}</span></div>
      <pre className="overflow-auto whitespace-pre-wrap break-words rounded bg-muted/50 p-2 text-xs text-muted-foreground">{row.kind === "added" ? "—" : stringify(row.before)}</pre>
      <pre className="overflow-auto whitespace-pre-wrap break-words rounded bg-muted/50 p-2 text-xs">{row.kind === "removed" ? "—" : stringify(row.after)}</pre>
    </div>
  );
}

function diffValues(before: unknown, after: unknown, path = ""): DiffRow[] {
  if (same(before, after)) return [];
  if (isContainer(before) && isContainer(after) && Array.isArray(before) === Array.isArray(after)) {
    const beforeRecord = toRecord(before);
    const afterRecord = toRecord(after);
    const keys = new Set([...Object.keys(beforeRecord), ...Object.keys(afterRecord)]);
    return [...keys].flatMap((key) => diffValues(beforeRecord[key], afterRecord[key], path ? `${path}.${key}` : key));
  }
  if (before === undefined) return [{ path: path || "valor", before, after, kind: "added" }];
  if (after === undefined) return [{ path: path || "valor", before, after, kind: "removed" }];
  return [{ path: path || "valor", before, after, kind: "changed" }];
}

function isContainer(value: unknown): value is Record<string, unknown> | unknown[] {
  return Array.isArray(value) || (typeof value === "object" && value !== null);
}

function toRecord(value: Record<string, unknown> | unknown[]): Record<string, unknown> {
  return Array.isArray(value) ? Object.fromEntries(value.map((item, index) => [String(index), item])) : value;
}

function same(left: unknown, right: unknown): boolean { return JSON.stringify(left) === JSON.stringify(right); }
function stringify(value: unknown): string { return value === undefined ? "—" : JSON.stringify(value, null, 2); }
