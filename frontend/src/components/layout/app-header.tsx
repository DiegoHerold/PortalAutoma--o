"use client";

import { useRouter } from "next/navigation";

import { useAuth } from "@/hooks/use-auth";

export function AppHeader() {
  const router = useRouter();
  const { user, signOut } = useAuth();

  return (
    <header className="flex items-center justify-between rounded-3xl border border-slate-200 bg-white/80 px-6 py-4 shadow-sm backdrop-blur">
      <div>
        <p className="text-sm font-medium text-slate-500">Ambiente operacional</p>
        <p className="text-lg font-semibold">{user?.name ?? "Usuario autenticado"}</p>
      </div>
      <button
        type="button"
        onClick={() => {
          signOut();
          router.push("/login");
        }}
        className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium transition hover:border-slate-400"
      >
        Sair
      </button>
    </header>
  );
}
