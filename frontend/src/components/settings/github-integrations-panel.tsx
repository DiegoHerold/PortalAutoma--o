"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Github, Trash2 } from "lucide-react";

import { SectionCard } from "@/components/shared/section-card";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type { GithubIntegration } from "@/types/automation-import";

export function GithubIntegrationsPanel() {
  const { token } = useAuth();
  const { toast } = useToast();
  const router = useRouter();
  const searchParams = useSearchParams();
  const integrations = useApi<GithubIntegration[]>("/integrations/github");

  useEffect(() => {
    const status = searchParams.get("github");
    if (!status) return;
    if (status === "connected") {
      toast({ title: "GitHub conectado", kind: "success" });
      void integrations.refetch();
    } else if (status === "pending") {
      toast({ title: "Solicitação enviada", description: "Aguardando aprovação do proprietário da conta/organização.", kind: "info" });
    } else if (status === "error") {
      toast({ title: "Falha ao conectar GitHub", description: searchParams.get("reason") ?? undefined, kind: "error" });
    }
    router.replace("/settings/integrations");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  async function connect() {
    if (!token) return;
    try {
      const { install_url } = await apiRequest<{ install_url: string }>("/integrations/github/connect", {
        method: "POST",
        token,
      });
      window.location.href = install_url;
    } catch (err) {
      toast({ title: "Falha ao iniciar conexão", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function disconnect(integration: GithubIntegration) {
    if (!token) return;
    if (!window.confirm(`Desconectar a conta GitHub "${integration.account_login}"?`)) return;
    try {
      await apiRequest(`/integrations/github/${integration.id}`, { method: "DELETE", token });
      toast({ title: "Integração removida", kind: "success" });
      await integrations.refetch();
    } catch (err) {
      toast({ title: "Falha ao desconectar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  return (
    <SectionCard
      title="Integração GitHub"
      description="Conta usada para importar automações do repositório biason-automations"
    >
      {integrations.error ? (
        <ErrorState message={integrations.error} onRetry={integrations.refetch} />
      ) : integrations.loading ? (
        <Skeleton className="h-24 rounded-lg" />
      ) : (integrations.data ?? []).length === 0 ? (
        <EmptyState
          icon={Github}
          title="Nenhuma conta conectada"
          description="Conecte uma conta ou organização GitHub via GitHub App para habilitar a importação de automações."
          action={
            <Button onClick={connect}>
              <Github className="h-4 w-4" /> Conectar GitHub
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          <ul className="divide-y divide-border rounded-lg border border-border">
            {integrations.data!.map((i) => (
              <li key={i.id} className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="flex items-center gap-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-full bg-muted">
                    <Github className="h-4 w-4" />
                  </span>
                  <div>
                    <p className="text-sm font-medium">{i.account_login}</p>
                    <p className="text-xs text-muted-foreground">{i.account_type}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={i.suspended_at ? "warning" : "success"}>{i.suspended_at ? "Suspensa" : "Ativa"}</Badge>
                  <Button variant="ghost" size="icon" onClick={() => disconnect(i)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
          <Button variant="outline" size="sm" onClick={connect}>
            <Github className="h-4 w-4" /> Conectar outra conta
          </Button>
        </div>
      )}
    </SectionCard>
  );
}
