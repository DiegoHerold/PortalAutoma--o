"use client";

import { useState } from "react";
import { Check, Copy, Terminal } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import type { Trigger } from "@/types/trigger";

import { webhookInvocationUrl } from "./webhook-utils";

export function WebhookUrlCard({ trigger, invokeBaseUrl }: { trigger: Trigger; invokeBaseUrl?: string | null }) {
  const { toast } = useToast();
  const [copied, setCopied] = useState<"url" | "curl" | null>(null);
  const url = webhookInvocationUrl(trigger, invokeBaseUrl);
  const curl = [
    `curl -X POST "${url || "{url}"}"`,
    '  -H "Content-Type: application/json"',
    `  -H "${trigger.required_header || "X-Trigger-Secret"}: SEU_SECRET"`,
    '  -H "Idempotency-Key: opcional-chave-unica"',
    "  -d '{\"company_id\": 123}'",
  ].join(" \\\n");

  async function copy(value: string, kind: "url" | "curl") {
    if (!value) return;
    await navigator.clipboard.writeText(value);
    setCopied(kind);
    toast({ title: kind === "url" ? "URL copiada" : "Exemplo copiado", kind: "success" });
    setTimeout(() => setCopied(null), 1400);
  }

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Invocacao publica</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge tone="outline">{trigger.method || "POST"}</Badge>
            <Badge tone="info">{trigger.required_header || "X-Trigger-Secret"}</Badge>
          </div>
        </div>
        <Button size="sm" variant="outline" onClick={() => copy(url, "url")} disabled={!url}>
          {copied === "url" ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />} URL
        </Button>
      </div>
      <div className="mt-3 rounded-md border border-border bg-muted/40 px-3 py-2">
        <code className="tabular block truncate text-xs">{url || "URL indisponivel"}</code>
      </div>
      <div className="mt-3 rounded-md border border-border bg-background">
        <div className="flex items-center justify-between border-b border-border px-3 py-2">
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <Terminal className="h-3.5 w-3.5" /> Exemplo curl
          </span>
          <button type="button" className="text-xs text-primary underline underline-offset-2" onClick={() => copy(curl, "curl")}>
            {copied === "curl" ? "Copiado" : "Copiar"}
          </button>
        </div>
        <pre className="tabular max-h-44 overflow-auto whitespace-pre-wrap p-3 text-xs">{curl}</pre>
      </div>
      <div className="mt-3 rounded-md border border-border bg-muted/30 p-3">
        <p className="text-xs font-medium text-foreground">Resposta esperada</p>
        <pre className="tabular mt-2 text-xs">{'{ "success": true, "job_id": 123, "execution_id": "..." }'}</pre>
      </div>
    </Card>
  );
}
