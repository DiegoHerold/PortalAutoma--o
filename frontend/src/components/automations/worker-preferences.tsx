"use client";

import { useEffect, useState } from "react";
import { GripVertical, ArrowUp, ArrowDown, Plus, X, Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type { Worker, WorkerPreference } from "@/types/worker";

/**
 * Ordered list of preferred workers for an automation. The dispatcher tries them
 * in order; if none are available the job waits in queue. Persists to
 * `/automations/{id}/worker-preferences` (best-effort — tolerates a not-yet-built endpoint).
 */
export function WorkerPreferences({ automationId, workers }: { automationId: number; workers: Worker[] }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [prefs, setPrefs] = useState<WorkerPreference[]>([]);
  const [saving, setSaving] = useState(false);
  const [pendingWorker, setPendingWorker] = useState("");

  useEffect(() => {
    if (!token) return;
    apiRequest<WorkerPreference[]>(`/automations/${automationId}/worker-preferences`, { token })
      .then((data) => setPrefs([...data].sort((a, b) => a.priority_order - b.priority_order)))
      .catch(() => setPrefs([]));
  }, [token, automationId]);

  const available = workers.filter((w) => !prefs.some((p) => p.worker_id === w.id));

  function move(index: number, dir: -1 | 1) {
    setPrefs((prev) => {
      const next = [...prev];
      const target = index + dir;
      if (target < 0 || target >= next.length) return prev;
      [next[index], next[target]] = [next[target], next[index]];
      return next.map((p, i) => ({ ...p, priority_order: i }));
    });
  }

  function add() {
    if (!pendingWorker) return;
    const worker = workers.find((w) => w.id === Number(pendingWorker));
    if (!worker) return;
    setPrefs((prev) => [...prev, { worker_id: worker.id, worker_name: worker.name, priority_order: prev.length }]);
    setPendingWorker("");
  }

  function remove(workerId: number) {
    setPrefs((prev) => prev.filter((p) => p.worker_id !== workerId).map((p, i) => ({ ...p, priority_order: i })));
  }

  async function save() {
    if (!token) return;
    setSaving(true);
    try {
      await apiRequest(`/automations/${automationId}/worker-preferences`, {
        method: "PUT",
        token,
        body: JSON.stringify({
          preferences: prefs.map((p, i) => ({ worker_id: p.worker_id, priority_order: i })),
        }),
      });
      toast({ title: "Preferências salvas", kind: "success" });
    } catch {
      toast({
        title: "Não foi possível salvar",
        description: "O endpoint de preferências ainda não está disponível no backend.",
        kind: "warning",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2 rounded-md border border-info/30 bg-info/5 p-3 text-xs text-muted-foreground">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <p>
          O dispatcher tenta os workers nesta ordem. Se nenhum estiver disponível, o job aguarda na fila pelo primeiro
          da lista que ficar livre.
        </p>
      </div>

      {prefs.length === 0 ? (
        <p className="rounded-md border border-dashed border-border py-6 text-center text-sm text-muted-foreground">
          Nenhum worker preferido — o job pode rodar em qualquer worker compatível.
        </p>
      ) : (
        <ol className="space-y-2">
          {prefs.map((p, index) => {
            const worker = workers.find((w) => w.id === p.worker_id);
            return (
              <li
                key={p.worker_id}
                className="flex items-center gap-3 rounded-md border border-border bg-background p-2.5"
              >
                <GripVertical className="h-4 w-4 text-muted-foreground" />
                <Badge tone="primary" className="tabular">
                  {index + 1}º
                </Badge>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{worker?.name ?? p.worker_name ?? `Worker #${p.worker_id}`}</p>
                  <p className="tabular truncate text-xs text-muted-foreground">{worker?.hostname}</p>
                </div>
                <div className="flex items-center gap-1">
                  <Button variant="ghost" size="icon" onClick={() => move(index, -1)} disabled={index === 0}>
                    <ArrowUp className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => move(index, 1)} disabled={index === prefs.length - 1}>
                    <ArrowDown className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => remove(p.worker_id)}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </li>
            );
          })}
        </ol>
      )}

      <div className="flex items-center gap-2">
        <Select value={pendingWorker} onChange={(e) => setPendingWorker(e.target.value)} className="flex-1">
          <option value="">Adicionar worker…</option>
          {available.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name} · {w.hostname}
            </option>
          ))}
        </Select>
        <Button variant="outline" onClick={add} disabled={!pendingWorker}>
          <Plus className="h-4 w-4" /> Adicionar
        </Button>
      </div>

      <div className="flex justify-end">
        <Button onClick={save} disabled={saving}>
          Salvar ordem
        </Button>
      </div>
    </div>
  );
}
