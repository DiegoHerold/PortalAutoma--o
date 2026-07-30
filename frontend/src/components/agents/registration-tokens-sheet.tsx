"use client";

import { useState } from "react";
import { Check, Copy, KeyRound, Plus, ShieldAlert, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Label } from "@/components/ui/input";
import { Sheet } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { createRegistrationToken, revokeRegistrationToken } from "@/lib/agent-api";
import { formatDateTime } from "@/lib/utils";
import type { RegistrationToken } from "@/types/agent";

const EXPIRY_OPTIONS = [
  { value: 3600, label: "1 hora" },
  { value: 3600 * 24, label: "1 dia" },
  { value: 3600 * 24 * 7, label: "7 dias" },
  { value: 3600 * 24 * 30, label: "30 dias" },
];

export function RegistrationTokensSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [expiresIn, setExpiresIn] = useState(3600);
  const [note, setNote] = useState("");
  const [creating, setCreating] = useState(false);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [manualRevokeId, setManualRevokeId] = useState("");
  const [created, setCreated] = useState<RegistrationToken[]>([]);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  async function create() {
    if (!token) return;
    setCreating(true);
    try {
      const result = await createRegistrationToken(token, { expires_in_seconds: expiresIn, metadata: note.trim() ? { note: note.trim() } : {} });
      setCreated((list) => [result, ...list]);
      setNote("");
      toast({ title: "Token de registro criado", description: "Copie agora — o segredo não será mostrado de novo.", kind: "success" });
    } catch (err) {
      toast({ title: "Falha ao criar token", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setCreating(false);
    }
  }

  async function revoke(tokenId: string) {
    if (!token || !tokenId) return;
    setRevokingId(tokenId);
    try {
      const result = await revokeRegistrationToken(token, tokenId);
      setCreated((list) => list.map((item) => (item.id === tokenId ? { ...item, status: result.status, revoked_at: result.revoked_at } : item)));
      toast({ title: "Token revogado", kind: "success" });
      setManualRevokeId("");
    } catch (err) {
      toast({ title: "Falha ao revogar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setRevokingId(null);
    }
  }

  async function copy(id: string, secret: string) {
    await navigator.clipboard.writeText(secret);
    setCopiedId(id);
    setTimeout(() => setCopiedId((current) => (current === id ? null : current)), 1500);
  }

  return (
    <Sheet open={open} onClose={onClose} title="Tokens de registro" description="Permitem que um novo Agent se conecte sozinho, sem intervenção manual.">
      <div className="space-y-6">
        <div className="flex items-start gap-2 rounded-md border border-info/30 bg-info/5 p-3 text-xs text-muted-foreground">
          <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-info" />
          <span>
            O segredo do token só aparece uma vez, logo após criar. O backend não guarda um histórico consultável — esta lista mostra apenas os tokens criados
            nesta sessão do navegador.
          </span>
        </div>

        <section className="space-y-3 rounded-lg border border-border p-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Novo token</h3>
          <Field>
            <Label htmlFor="rt-expiry">Validade</Label>
            <div className="grid grid-cols-4 gap-1.5">
              {EXPIRY_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setExpiresIn(opt.value)}
                  className={
                    expiresIn === opt.value
                      ? "rounded-md border border-primary bg-primary/5 p-2 text-xs font-medium text-primary"
                      : "rounded-md border border-input p-2 text-xs font-medium text-muted-foreground hover:border-primary/50"
                  }
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </Field>
          <Field>
            <Label htmlFor="rt-note">Nota (opcional)</Label>
            <Input id="rt-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ex.: máquina do financeiro" />
          </Field>
          <Button onClick={create} disabled={creating} className="w-full">
            {creating ? <Spinner /> : <Plus className="h-4 w-4" />} Gerar token
          </Button>
        </section>

        <section className="space-y-3 rounded-lg border border-border p-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Revogar por ID</h3>
          <p className="text-xs text-muted-foreground">Para revogar um token criado em outra sessão, cole o id dele (ex. dos logs de auditoria).</p>
          <div className="flex gap-2">
            <Input value={manualRevokeId} onChange={(e) => setManualRevokeId(e.target.value)} placeholder="art_..." className="tabular" />
            <Button variant="outline" onClick={() => revoke(manualRevokeId)} disabled={!manualRevokeId || revokingId === manualRevokeId}>
              {revokingId === manualRevokeId ? <Spinner /> : "Revogar"}
            </Button>
          </div>
        </section>

        {created.length > 0 && (
          <section className="space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Criados nesta sessão</h3>
            <ul className="space-y-2">
              {created.map((item) => (
                <li key={item.id} className="space-y-2 rounded-md border border-border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="tabular truncate text-xs text-muted-foreground">{item.id}</span>
                    <Badge tone={tokenStatusTone(item.status)}>{item.status}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">Expira em {formatDateTime(item.expires_at)}</p>
                  {item.registration_token && (
                    <div className="flex items-center gap-2 rounded-md bg-muted p-2">
                      <code className="tabular flex-1 truncate text-xs">{item.registration_token}</code>
                      <button
                        type="button"
                        onClick={() => copy(item.id, item.registration_token!)}
                        className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                        title="Copiar"
                      >
                        {copiedId === item.id ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                      </button>
                    </div>
                  )}
                  {item.status === "active" && (
                    <Button size="sm" variant="outline" onClick={() => revoke(item.id)} disabled={revokingId === item.id}>
                      {revokingId === item.id ? <Spinner /> : <XCircle className="h-3.5 w-3.5" />} Revogar
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        {created.length === 0 && (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
            <KeyRound className="h-6 w-6" />
            Nenhum token gerado ainda nesta sessão.
          </div>
        )}
      </div>
    </Sheet>
  );
}

function tokenStatusTone(status: string): "success" | "neutral" | "destructive" | "warning" {
  if (status === "active") return "success";
  if (status === "used") return "neutral";
  if (status === "revoked") return "destructive";
  return "warning";
}
