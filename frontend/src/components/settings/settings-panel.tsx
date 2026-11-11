"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bell, Github, LayoutList, Moon, Server, Sun, UserRound } from "lucide-react";

import { PageTitle } from "@/components/shared/page-title";
import { AreasDoPortal } from "@/components/settings/areas-do-portal";
import { NotificacoesPreferencias } from "@/components/settings/notificacoes";
import { useTheme } from "@/components/theme/theme-provider";
import { useAuth } from "@/hooks/use-auth";
import { API_BASE_URL } from "@/lib/constants";
import { cn } from "@/lib/utils";

const ABAS = [
  { id: "menu", rotulo: "Menu e atalhos", icone: LayoutList },
  { id: "notificacoes", rotulo: "Notificações", icone: Bell },
  { id: "conta", rotulo: "Conta e aparência", icone: UserRound },
  { id: "sistema", rotulo: "Sistema", icone: Server },
] as const;
type Aba = (typeof ABAS)[number]["id"];

const PAPEIS: Record<string, string> = { admin: "Administrador", manager: "Gestor", operator: "Operador", viewer: "Leitura" };

function abaDoEndereco(): Aba {
  const hash = typeof window === "undefined" ? "" : window.location.hash.replace("#", "");
  return (ABAS.find((a) => a.id === hash)?.id ?? "menu") as Aba;
}

/** Configurações em abas. A aba fica no endereço (#notificacoes...), então o sino e os links levam direto a ela. */
export function SettingsPanel() {
  const [aba, setAba] = useState<Aba>("menu");

  useEffect(() => {
    const ler = () => setAba(abaDoEndereco());
    ler();
    window.addEventListener("hashchange", ler);
    return () => window.removeEventListener("hashchange", ler);
  }, []);

  function abrir(id: Aba) {
    setAba(id);
    window.history.replaceState(null, "", `#${id}`);
  }

  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Preferências" title="Configurações" description="O seu menu, os avisos que você recebe, a sua conta e o sistema." />
      <div className="grid gap-6 lg:grid-cols-[14rem_minmax(0,1fr)]">
        <nav aria-label="Seções das configurações" className="flex gap-1 overflow-x-auto lg:sticky lg:top-24 lg:flex-col lg:self-start">
          {ABAS.map(({ id, rotulo, icone: Icone }) => (
            <button key={id} onClick={() => abrir(id)} aria-current={aba === id ? "page" : undefined}
              className={cn("flex shrink-0 items-center gap-3 rounded-lg px-3 py-2.5 text-left font-medium transition-colors",
                aba === id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground")}>
              <Icone className="h-[18px] w-[18px]" /> {rotulo}
            </button>
          ))}
        </nav>
        <div className="min-w-0">
          {aba === "menu" && <AreasDoPortal />}
          {aba === "notificacoes" && <NotificacoesPreferencias />}
          {aba === "conta" && <ContaEAparencia />}
          {aba === "sistema" && <Sistema />}
        </div>
      </div>
    </div>
  );
}

function ContaEAparencia() {
  const { user } = useAuth();
  const { theme, setTheme } = useTheme();
  const iniciais = (user?.name || "U").split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <h2 className="titulo-condensado text-2xl">Sua conta</h2>
        <div className="flex flex-wrap items-center gap-5 rounded-xl border border-border bg-card p-5 shadow-sm">
          <span className="titulo-condensado flex h-16 w-16 items-center justify-center rounded-full bg-primary text-2xl text-primary-foreground">{iniciais}</span>
          <div className="min-w-0 flex-1">
            <p className="text-lg font-semibold text-titulo">{user?.name ?? "—"}</p>
            <p className="text-muted-foreground">{user?.email ?? "—"}</p>
          </div>
          <div className="text-right">
            <p className="eyebrow">Papel</p>
            <p className="font-medium">{PAPEIS[user?.role ?? ""] ?? user?.role ?? "—"}</p>
          </div>
        </div>
        <p className="text-sm text-muted-foreground">Nome, e-mail e papel são definidos por um administrador, na área Usuários.</p>
      </section>

      <section className="space-y-4">
        <h2 className="titulo-condensado text-2xl">Aparência</h2>
        <div className="grid max-w-xl gap-3 sm:grid-cols-2">
          {([["light", "Claro", Sun], ["dark", "Escuro", Moon]] as const).map(([valor, rotulo, Icone]) => (
            <button key={valor} onClick={() => setTheme(valor)} aria-pressed={theme === valor}
              className={cn("overflow-hidden rounded-xl border-2 text-left transition-colors",
                theme === valor ? "border-primary" : "border-border hover:border-primary/40")}>
              <span className={cn("block h-20 p-3", valor === "light" ? "bg-[#eef2f7]" : "bg-[#0b1223]")}>
                <span className={cn("block h-3 w-1/3 rounded", valor === "light" ? "bg-[#1b3a63]" : "bg-[#c9d6e6]")} />
                <span className={cn("mt-2 block h-8 rounded", valor === "light" ? "bg-white" : "bg-[#162540]")} />
              </span>
              <span className="flex items-center gap-2 px-3 py-2 font-medium"><Icone className="h-4 w-4" /> {rotulo}</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

function Sistema() {
  return (
    <section className="space-y-4">
      <h2 className="titulo-condensado text-2xl">Sistema</h2>
      <dl className="divide-y divide-border rounded-xl border border-border bg-card shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2 px-5 py-4">
          <dt className="text-muted-foreground">Endereço da API</dt>
          <dd><code className="tabular rounded bg-muted px-2 py-1 text-sm" suppressHydrationWarning>{API_BASE_URL}</code></dd>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 px-5 py-4">
          <dt className="text-muted-foreground">Autenticação</dt>
          <dd>Token no cabeçalho (JWT), nunca no endereço</dd>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 px-5 py-4">
          <dt className="flex items-center gap-2 text-muted-foreground"><Github className="h-4 w-4" /> GitHub App</dt>
          <dd><Link href="/settings/integrations" className="font-medium text-primary hover:underline">Gerenciar integração</Link></dd>
        </div>
      </dl>
    </section>
  );
}
