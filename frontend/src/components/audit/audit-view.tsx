"use client";

import { useMemo, useState } from "react";
import { ScrollText, ChevronDown, Search } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { DetailJson } from "@/components/shared/detail-json";
import { useApi } from "@/hooks/use-api";
import { cn, formatDateTime } from "@/lib/utils";
import type { AuditEntry } from "@/types/audit";

export function AuditView() {
  const audit = useApi<AuditEntry[]>("/audit", { pollMs: 15000 });
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);

  const filtered = useMemo(() => {
    const list = audit.data ?? [];
    const q = query.trim().toLowerCase();
    if (!q) return list;
    return list.filter(
      (e) =>
        e.action.toLowerCase().includes(q) ||
        (e.actor ?? "").toLowerCase().includes(q) ||
        (e.entity_type ?? "").toLowerCase().includes(q),
    );
  }, [audit.data, query]);

  if (audit.error)
    return (
      <div className="space-y-4">
        <ErrorState message={audit.error} onRetry={audit.refetch} />
        <p className="text-center text-xs text-muted-foreground">
          A trilha de auditoria depende do endpoint <code className="tabular">/audit</code> no backend.
        </p>
      </div>
    );
  if (audit.loading) return <Skeleton className="h-72 rounded-lg" />;
  if (filtered.length === 0)
    return <EmptyState icon={ScrollText} title="Sem registros" description="Nenhum evento de auditoria encontrado." />;

  return (
    <div className="space-y-4">
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input className="pl-9" placeholder="Filtrar por ação, ator, entidade…" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>

      <ol className="relative space-y-3 border-l border-border pl-6">
        {filtered.map((entry) => {
          const isOpen = expanded === entry.id;
          const hasDiff = entry.before || entry.after;
          return (
            <li key={entry.id} className="relative">
              <span className="absolute -left-[27px] top-2 h-2.5 w-2.5 rounded-full border-2 border-primary bg-background" />
              <div className="rounded-lg border border-border bg-card">
                <button
                  onClick={() => hasDiff && setExpanded(isOpen ? null : entry.id)}
                  className={cn("flex w-full items-center gap-3 p-3.5 text-left", hasDiff && "hover:bg-muted/40")}
                >
                  <Badge tone="outline" className="tabular">
                    {entry.action}
                  </Badge>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm">
                      {entry.entity_type ? (
                        <span className="font-medium">
                          {entry.entity_type}
                          {entry.entity_id != null ? ` #${entry.entity_id}` : ""}
                        </span>
                      ) : (
                        entry.message
                      )}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {entry.actor ?? "sistema"} · <span className="tabular">{formatDateTime(entry.created_at)}</span>
                    </p>
                  </div>
                  {hasDiff && <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform", isOpen && "rotate-180")} />}
                </button>
                {isOpen && hasDiff && (
                  <div className="grid gap-3 border-t border-border p-3.5 md:grid-cols-2">
                    <div>
                      <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">Antes</p>
                      <DetailJson data={entry.before ?? {}} />
                    </div>
                    <div>
                      <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">Depois</p>
                      <DetailJson data={entry.after ?? {}} />
                    </div>
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
