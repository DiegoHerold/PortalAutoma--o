"use client";

import { useEffect, useState } from "react";
import { CalendarClock } from "lucide-react";

import { Spinner } from "@/components/ui/spinner";
import { useAuth } from "@/hooks/use-auth";
import { previewScheduleOccurrences } from "@/lib/schedule-api";
import { formatDateTime } from "@/lib/utils";
import type { SchedulePreviewPayload } from "@/types/schedule";

/**
 * "Próximas N ocorrências" (seção 24) — calculado via POST /schedules/preview, que não
 * persiste nada. Recalcula com debounce sempre que os campos de recorrência do formulário mudam.
 */
export function ScheduleOccurrencesPreview({ payload }: { payload: SchedulePreviewPayload | null }) {
  const { token } = useAuth();
  const [occurrences, setOccurrences] = useState<string[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !payload) {
      setOccurrences(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const id = setTimeout(async () => {
      try {
        const result = await previewScheduleOccurrences(token, payload);
        if (!cancelled) {
          setOccurrences(result.occurrences);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Não foi possível calcular as próximas execuções.");
          setOccurrences(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 400);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [token, JSON.stringify(payload)]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="space-y-2">
      <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <CalendarClock className="h-3.5 w-3.5" /> Próximas execuções
      </h3>
      {loading && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Spinner /> Calculando…
        </p>
      )}
      {!loading && error && <p className="text-xs text-destructive">{error}</p>}
      {!loading && !error && occurrences && occurrences.length === 0 && <p className="text-xs text-muted-foreground">Nenhuma ocorrência futura com esta configuração.</p>}
      {!loading && !error && occurrences && occurrences.length > 0 && (
        <ul className="space-y-1 rounded-md border border-border bg-muted/20 p-2">
          {occurrences.map((occ) => (
            <li key={occ} className="tabular text-xs">
              {formatDateTime(occ)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
