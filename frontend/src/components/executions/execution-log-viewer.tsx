"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import { cn, formatTime } from "@/lib/utils";

type LogEntry = { id: string | number; level: string; message: string; created_at: string };

const levelColor: Record<string, string> = {
  error: "text-destructive",
  warning: "text-warning",
  warn: "text-warning",
  info: "text-info",
  debug: "text-muted-foreground",
};

export function ExecutionLogViewer({ logs = [] }: { logs?: LogEntry[] }) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return logs;
    return logs.filter((l) => l.message.toLowerCase().includes(q) || l.level.toLowerCase().includes(q));
  }, [logs, query]);

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input className="pl-9" placeholder="Filtrar logs…" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      <div className="max-h-96 overflow-auto rounded-lg border border-border bg-[hsl(224_28%_7%)] p-4">
        {filtered.length === 0 ? (
          <p className="tabular text-xs text-slate-500">Nenhum log.</p>
        ) : (
          <div className="space-y-1">
            {filtered.map((log) => (
              <div key={log.id} className="tabular flex gap-3 text-xs leading-relaxed">
                <span className="shrink-0 text-slate-500">{formatTime(log.created_at)}</span>
                <span className={cn("w-14 shrink-0 uppercase", levelColor[log.level.toLowerCase()] ?? "text-slate-400")}>
                  {log.level}
                </span>
                <span className="whitespace-pre-wrap break-all text-slate-200">{log.message}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
