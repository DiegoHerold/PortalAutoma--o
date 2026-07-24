"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, Copy, Cpu, Pencil, Plus, Server, Trash2 } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Select, Label, Field } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Spinner } from "@/components/ui/spinner";
import { WorkerStatusBadge } from "@/components/ui/status-badge";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { useRealtime } from "@/hooks/use-realtime";
import { useRealtimeStatus } from "@/components/layout/realtime-provider";
import { apiRequest } from "@/lib/api";
import { cn, relativeFromNow } from "@/lib/utils";
import type { Worker } from "@/types/worker";

type InstallerConfig = { central_api_url: string; central_websocket_url: string };

const POLL = 5000;
const emptyForm = {
  name: "",
  hostname: "",
  ip_address: "",
  status: "offline",
  max_concurrency: 1,
  is_active: true,
};

export function WorkersManager() {
  const { token } = useAuth();
  const { toast } = useToast();
  const workers = useApi<Worker[]>("/workers", { pollMs: POLL });
  const installer = useApi<InstallerConfig>("/workers/installer-config");
  const { setState } = useRealtimeStatus();
  const { state } = useRealtime<Worker>({
    wsPath: "/ws/executions",
    onMessage: () => void workers.refetch(),
    onPoll: () => void workers.refetch(),
    pollMs: POLL,
  });
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [editing, setEditing] = useState<Worker | null>(null);
  const [form, setForm] = useState(emptyForm);

  useEffect(() => setState(state), [state, setState]);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setOpen(true);
  }

  function openEdit(worker: Worker) {
    setEditing(worker);
    setForm({
      name: worker.name,
      hostname: worker.hostname,
      ip_address: worker.ip_address ?? "",
      status: worker.status,
      max_concurrency: worker.max_concurrency,
      is_active: worker.is_active,
    });
    setOpen(true);
  }

  async function save() {
    if (!token) return;
    setSubmitting(true);
    try {
      await apiRequest<Worker>(editing ? `/workers/${editing.id}` : "/workers", {
        method: editing ? "PUT" : "POST",
        token,
        body: JSON.stringify({ ...form, ip_address: form.ip_address || null }),
      });
      toast({ title: editing ? "Worker atualizado" : "Worker criado", kind: "success" });
      setEditing(null);
      setForm(emptyForm);
      setOpen(false);
      await workers.refetch();
    } catch (err) {
      toast({ title: "Falha ao salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(worker: Worker) {
    if (!token) return;
    if (!window.confirm(`Apagar o worker "${worker.name}"?`)) return;
    try {
      await apiRequest<void>(`/workers/${worker.id}`, { method: "DELETE", token });
      toast({ title: "Worker apagado", kind: "success" });
      await workers.refetch();
    } catch (err) {
      toast({ title: "Falha ao apagar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  if (workers.error) return <ErrorState message={workers.error} onRetry={workers.refetch} />;

  const list = workers.data ?? [];
  // Sempre vem do backend/.env (BACKEND_PUBLIC_URL), nunca do host do navegador —
  // um worker em outra maquina precisa do endereco real do servidor, nao do que
  // o admin usou pra abrir o Portal. Trocar de maquina/rede = editar so o .env.
  const centralApiUrl = installer.data?.central_api_url ?? "";
  const centralWebSocketUrl = installer.data?.central_websocket_url ?? "";
  const installerConfig = JSON.stringify(
    {
      agent_name: "",
      central_api_url: centralApiUrl,
      central_websocket_url: centralWebSocketUrl,
      console_port: 8765,
      heartbeat_seconds: 30,
      interactive_slots: 1,
      background_slots: 2,
      update_channel: "stable",
    },
    null,
    2,
  );

  async function copyInstallerConfig() {
    await navigator.clipboard.writeText(installerConfig);
    toast({ title: "Configuracao copiada", kind: "success" });
  }

  return (
    <div className="space-y-5">
      <Card className="p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <h2 className="font-display text-base font-semibold">Configuracao do instalador</h2>
            <div className="mt-2 grid gap-1 text-xs text-muted-foreground">
              {installer.loading ? (
                <span>Carregando...</span>
              ) : (
                <>
                  <span className="tabular truncate">central_api_url: {centralApiUrl}</span>
                  <span className="tabular truncate">central_websocket_url: {centralWebSocketUrl}</span>
                </>
              )}
            </div>
          </div>
          <Button variant="outline" onClick={copyInstallerConfig} disabled={installer.loading}>
            <Copy className="h-4 w-4" /> Copiar JSON
          </Button>
        </div>
      </Card>

      <div className="flex justify-end">
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" /> Novo worker
        </Button>
      </div>

      {workers.loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-40 rounded-lg" />
          ))}
        </div>
      ) : list.length === 0 ? (
        <EmptyState icon={Server} title="Sem workers" description="Nenhum worker registrado." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {list.map((w) => {
            const load = w.active_jobs ?? 0;
            const pct = w.max_concurrency > 0 ? Math.min(100, (load / w.max_concurrency) * 100) : 0;
            return (
              <Card key={w.id} className="h-full p-5 transition-colors hover:border-primary/40">
                <div className="flex items-start justify-between gap-3">
                  <Link href={`/workers/${w.id}`} className="min-w-0">
                    <h3 className="truncate font-display text-base font-semibold hover:text-primary">{w.name}</h3>
                    <p className="tabular mt-0.5 truncate text-xs text-muted-foreground">{w.hostname}</p>
                    {w.agent_id && <p className="tabular mt-0.5 truncate text-xs text-muted-foreground">{w.agent_id}</p>}
                  </Link>
                  <div className="flex items-center gap-1">
                    <WorkerStatusBadge status={w.status} />
                    <Button size="icon" variant="ghost" onClick={() => openEdit(w)} title="Editar worker">
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost" onClick={() => remove(w)} title="Apagar worker">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>

                <div className="mt-4 space-y-2">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1.5">
                      <Cpu className="h-3.5 w-3.5" /> Capacidade
                    </span>
                    <span className="tabular font-medium text-foreground">
                      {load}/{w.max_concurrency}
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn("h-full rounded-full", pct >= 100 ? "bg-destructive" : "bg-primary")}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>

                <div className="mt-4 flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Activity className="h-3.5 w-3.5" />
                  Heartbeat {relativeFromNow(w.last_heartbeat_at)}
                </div>
                {w.agent_version && (
                  <div className="tabular mt-2 text-xs text-muted-foreground">
                    Agent {w.agent_version} {w.architecture ? `- ${w.architecture}` : ""}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? "Editar worker" : "Novo worker"}
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={save} disabled={submitting || !form.name || !form.hostname || form.max_concurrency < 1}>
              {submitting && <Spinner />} {editing ? "Salvar" : "Criar"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field>
            <Label htmlFor="w-name">Nome</Label>
            <Input id="w-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <Field>
            <Label htmlFor="w-hostname">Hostname</Label>
            <Input id="w-hostname" className="tabular" value={form.hostname} onChange={(e) => setForm({ ...form, hostname: e.target.value })} />
          </Field>
          <Field>
            <Label htmlFor="w-ip">IP</Label>
            <Input id="w-ip" className="tabular" value={form.ip_address} onChange={(e) => setForm({ ...form, ip_address: e.target.value })} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field>
              <Label htmlFor="w-status">Status</Label>
              <Select id="w-status" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                <option value="online">online</option>
                <option value="busy">busy</option>
                <option value="offline">offline</option>
                <option value="maintenance">maintenance</option>
              </Select>
            </Field>
            <Field>
              <Label htmlFor="w-max">Concorrencia maxima</Label>
              <Input
                id="w-max"
                type="number"
                min={1}
                value={form.max_concurrency}
                onChange={(e) => setForm({ ...form, max_concurrency: Number(e.target.value) })}
              />
            </Field>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              className="h-4 w-4 accent-primary"
            />
            Worker ativo
          </label>
        </div>
      </Modal>
    </div>
  );
}
