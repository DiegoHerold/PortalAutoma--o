"use client";

import { useState } from "react";
import type { PropsWithChildren } from "react";

import { AppHeader } from "@/components/layout/app-header";
import { AppSidebar, MobileSidebar } from "@/components/layout/app-sidebar";
import { RealtimeStatusProvider } from "@/components/layout/realtime-provider";

export function AppShell({ children }: PropsWithChildren) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <RealtimeStatusProvider>
      <div className="flex min-h-screen">
        <AppSidebar />
        <MobileSidebar open={mobileOpen} onClose={() => setMobileOpen(false)} />
        <div className="flex min-w-0 flex-1 flex-col">
          <AppHeader onOpenSidebar={() => setMobileOpen(true)} />
          <main className="mx-auto w-full max-w-[1400px] flex-1 space-y-6 px-4 py-6 sm:px-6 lg:py-8">{children}</main>
        </div>
      </div>
    </RealtimeStatusProvider>
  );
}
