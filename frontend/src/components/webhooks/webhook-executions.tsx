"use client";

import Link from "next/link";
import { ExternalLink, History } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Trigger } from "@/types/trigger";

export function WebhookExecutions({ trigger }: { trigger: Trigger }) {
  const href = `/executions?origin=trigger&trigger_id=${trigger.id}`;
  return (
    <div className="rounded-md border border-border bg-muted/30 p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="inline-flex items-center gap-1.5 text-sm font-medium">
            <History className="h-4 w-4 text-primary" /> Execucoes oficiais
          </p>
          <p className="mt-1 text-xs text-muted-foreground">O historico vem da tela de Execucoes; nao ha painel paralelo de deliveries.</p>
        </div>
        <Button size="sm" variant="outline" asChild>
          <Link href={href}>
            <ExternalLink className="h-3.5 w-3.5" /> Ver execucoes
          </Link>
        </Button>
      </div>
    </div>
  );
}
