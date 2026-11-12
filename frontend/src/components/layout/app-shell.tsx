"use client";

import { useState } from "react";
import type { PropsWithChildren } from "react";
import { usePathname } from "next/navigation";
import { ShieldOff } from "lucide-react";

import { AppHeader } from "@/components/layout/app-header";
import { AppSidebar, MobileSidebar } from "@/components/layout/app-sidebar";
import { BotaoVoltar } from "@/components/layout/botao-voltar";
import { RealtimeStatusProvider } from "@/components/layout/realtime-provider";
import { useAuth } from "@/hooks/use-auth";
import { ALL_NAV_ITEMS } from "@/lib/navigation";
import { podeVerAba } from "@/lib/permissions";

export function AppShell({ children }: PropsWithChildren) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <RealtimeStatusProvider>
      <div className="flex min-h-screen">
        <AppSidebar />
        <MobileSidebar open={mobileOpen} onClose={() => setMobileOpen(false)} />
        <div className="flex min-w-0 flex-1 flex-col">
          <AppHeader onOpenSidebar={() => setMobileOpen(true)} />
          <main className="mx-auto w-full max-w-[110rem] flex-1 space-y-8 px-5 py-7 sm:px-8 lg:px-12 lg:py-10">
            <BotaoVoltar />
            <GuardaDaAba>{children}</GuardaDaAba>
          </main>
        </div>
      </div>
    </RealtimeStatusProvider>
  );
}

/** A tela de uma aba desligada no papel da pessoa não abre, nem pelo link (Papéis globais). */
function GuardaDaAba({ children }: PropsWithChildren) {
  const pathname = usePathname();
  const { user } = useAuth();
  const aba = [...ALL_NAV_ITEMS].sort((a, b) => b.href.length - a.href.length)
    .find((i) => pathname === i.href || pathname.startsWith(`${i.href}/`));
  if (!user || !aba || podeVerAba(user, aba.href)) return <>{children}</>;
  return (
    <div className="flex items-start gap-4 rounded-xl border border-border bg-card p-8" data-testid="sem-acesso">
      <ShieldOff className="h-8 w-8 shrink-0 text-muted-foreground" />
      <div>
        <p className="titulo-condensado text-2xl">Sem acesso a {aba.label}</p>
        <p className="mt-1 text-muted-foreground">O seu papel não inclui esta aba. Peça a um administrador, em Papéis.</p>
      </div>
    </div>
  );
}
