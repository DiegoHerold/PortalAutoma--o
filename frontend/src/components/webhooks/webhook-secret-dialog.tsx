"use client";

import { useState } from "react";
import { Check, Copy, KeyRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";

export function WebhookSecretDialog({
  secret,
  title,
  onClose,
}: {
  secret: string | null;
  title: string;
  onClose: () => void;
}) {
  const { toast } = useToast();
  const [copied, setCopied] = useState(false);
  if (!secret) return null;

  async function copy() {
    await navigator.clipboard.writeText(secret ?? "");
    setCopied(true);
    toast({ title: "Secret copiado", kind: "success" });
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={title}
      description="Guarde este valor agora. Depois desta janela o Portal mostrara apenas os últimos caracteres."
      className="max-w-xl"
      footer={
        <>
          <Button variant="outline" onClick={copy}>
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />} Copiar secret
          </Button>
          <Button onClick={onClose}>Entendi</Button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="rounded-md border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
          O secret anterior não fica disponível para consulta. Em rotação, o valor antigo deixa de autenticar novas chamadas.
        </div>
        <div className="rounded-md border border-border bg-muted/40 p-3">
          <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <KeyRound className="h-3.5 w-3.5" /> Secret exibido uma unica vez
          </div>
          <code className="tabular block break-all text-sm">{secret}</code>
        </div>
      </div>
    </Modal>
  );
}
