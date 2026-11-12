"use client";

import { useState } from "react";
import type { PropsWithChildren } from "react";

import { AppHeader } from "@/components/layout/app-header";
import { AppSidebar, MobileSidebar } from "@/components/layout/app-sidebar";
import { BotaoVoltar } from "@/components/layout/botao-voltar";
import { RealtimeStatusProvider } from "@/components/layout/realtime-provider";
import { RegistroDeTelas } from "@/components/layout/registro-de-telas";

export function AppShell({ children }: PropsWithChildren) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <RealtimeStatusProvider>
      <RegistroDeTelas />
      <div className="flex min-h-screen">
        <AppSidebar />
        <MobileSidebar open={mobileOpen} onClose={() => setMobileOpen(false)} />
        <div className="flex min-w-0 flex-1 flex-col">
          <AppHeader onOpenSidebar={() => setMobileOpen(true)} />
          <main className="mx-auto w-full max-w-[110rem] flex-1 space-y-8 px-5 py-7 sm:px-8 lg:px-12 lg:py-10">
            <BotaoVoltar />
            {children}
          </main>
        </div>
      </div>
    </RealtimeStatusProvider>
  );
}
