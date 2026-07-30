"use client";

import { useState } from "react";
import { Check, Copy, KeyRound, RefreshCw, ShieldAlert, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { revokeAgentCredential, rotateAgentCredential } from "@/lib/agent-api";
import type { RotateCredentialResult } from "@/types/agent";

export function AgentCredentialsPanel({ agentId }: { agentId: string }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [rotating, setRotating] = useState(false);
  const [revoking, setRevoking] = useState(false);
  const [revokeId, setRevokeId] = useState("");
  const [rotated, setRotated] = useState<RotateCredentialResult[]>([]);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  async function rotate() {
    if (!token) return;
    if (!window.confirm("Rotacionar a credencial revoga TODAS as credenciais ativas deste Agent e emite uma nova. O Agent vai precisar reconectar com o novo segredo. Continuar?")) return;
    setRotating(true);
    try {
      const result = await rotateAgentCredential(token, agentId);
      setRotated((list) => [result, ...list]);
      toast({ title: "Credencial rotacionada", description: "Copie o novo segredo agora — ele não será mostrado de novo.", kind: "success" });
    } catch (err) {
      toast({ title: "Falha ao rotacionar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setRotating(false);
    }
  }

  async function revoke() {
    if (!token || !revokeId.trim()) return;
    if (!window.confirm(`Revogar a credencial "${revokeId.trim()}"? Se for a única ativa, o Agent perde acesso até rotacionar de novo.`)) return;
    setRevoking(true);
    try {
      await revokeAgentCredential(token, agentId, revokeId.trim());
      toast({ title: "Credencial revogada", kind: "success" });
      setRevokeId("");
    } catch (err) {
      toast({ title: "Falha ao revogar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setRevoking(false);
    }
  }

  async function copy(id: string, value: string) {
    await navigator.clipboard.writeText(value);
    setCopiedId(id);
    setTimeout(() => setCopiedId((current) => (current === id ? null : current)), 1500);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2 rounded-md border border-info/30 bg-info/5 p-3 text-xs text-muted-foreground">
        <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-info" />
        <span>
          O backend não expõe uma listagem de credenciais existentes — só é possível rotacionar (emite uma nova e invalida as ativas) ou revogar uma
          específica pelo id.
        </span>
      </div>

      <Button variant="outline" onClick={rotate} disabled={rotating}>
        {rotating ? <Spinner /> : <RefreshCw className="h-4 w-4" />} Rotacionar credencial
      </Button>

      {rotated.length > 0 && (
        <ul className="space-y-2">
          {rotated.map((item) => (
            <li key={item.id} className="space-y-2 rounded-md border border-border p-3">
              <p className="tabular text-xs text-muted-foreground">{item.public_identifier}</p>
              <div className="flex items-center gap-2 rounded-md bg-muted p-2">
                <code className="tabular flex-1 truncate text-xs">{item.bearer_token}</code>
                <button
                  type="button"
                  onClick={() => copy(item.id, item.bearer_token)}
                  className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                  title="Copiar"
                >
                  {copiedId === item.id ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="space-y-2 border-t border-border pt-4">
        <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <KeyRound className="h-3.5 w-3.5" /> Revogar credencial por ID
        </p>
        <div className="flex gap-2">
          <Input value={revokeId} onChange={(e) => setRevokeId(e.target.value)} placeholder="acr_..." className="tabular" />
          <Button variant="destructive" onClick={revoke} disabled={!revokeId.trim() || revoking}>
            {revoking ? <Spinner /> : <XCircle className="h-4 w-4" />} Revogar
          </Button>
        </div>
      </div>
    </div>
  );
}
