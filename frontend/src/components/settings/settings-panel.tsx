"use client";

import Link from "next/link";
import { Github, Moon, Sun, User as UserIcon, Wifi } from "lucide-react";

import { PageTitle } from "@/components/shared/page-title";
import { SectionCard } from "@/components/shared/section-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/hooks/use-auth";
import { useTheme } from "@/components/theme/theme-provider";
import { API_BASE_URL } from "@/lib/constants";

export function SettingsPanel() {
  const { user } = useAuth();
  const { theme, setTheme } = useTheme();

  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Preferências" title="Configurações" description="Perfil, aparência e informações do ambiente." />

      <div className="grid gap-6 lg:grid-cols-2">
        <SectionCard title="Perfil" description="Sessão atual">
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary text-lg font-semibold text-primary-foreground">
                {(user?.name || "U").slice(0, 1).toUpperCase()}
              </span>
              <div>
                <p className="font-medium">{user?.name ?? "—"}</p>
                <p className="text-sm text-muted-foreground">{user?.email ?? "—"}</p>
              </div>
            </div>
            <div className="flex items-center justify-between border-t border-border pt-3 text-sm">
              <span className="text-muted-foreground">Papel</span>
              <Badge tone="primary">{user?.role ?? "—"}</Badge>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Permissões por categoria</span>
              <span className="tabular font-medium">{user?.permissions.length ?? 0}</span>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="Aparência" description="Tema da interface">
          <div className="flex gap-3">
            <button
              onClick={() => setTheme("light")}
              className={`flex flex-1 flex-col items-center gap-2 rounded-lg border p-4 text-sm transition-colors ${
                theme === "light" ? "border-primary bg-primary/5" : "border-border hover:bg-accent"
              }`}
            >
              <Sun className="h-5 w-5" /> Claro
            </button>
            <button
              onClick={() => setTheme("dark")}
              className={`flex flex-1 flex-col items-center gap-2 rounded-lg border p-4 text-sm transition-colors ${
                theme === "dark" ? "border-primary bg-primary/5" : "border-border hover:bg-accent"
              }`}
            >
              <Moon className="h-5 w-5" /> Escuro
            </button>
          </div>
        </SectionCard>

        <SectionCard title="Ambiente" description="Conexão com a API" className="lg:col-span-2">
          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-2 text-muted-foreground">
                <Wifi className="h-4 w-4" /> Endpoint da API
              </span>
              <code className="tabular rounded bg-muted px-2 py-1 text-xs">{API_BASE_URL}</code>
            </div>
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-2 text-muted-foreground">
                <UserIcon className="h-4 w-4" /> Autenticação
              </span>
              <span>Bearer token (JWT)</span>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="Integrações" description="Conexões externas para importar automações" className="lg:col-span-2">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
              <Github className="h-4 w-4" /> GitHub App (repositório de automações)
            </span>
            <Button variant="outline" size="sm" asChild>
              <Link href="/settings/integrations">Gerenciar</Link>
            </Button>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
