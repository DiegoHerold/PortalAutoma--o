"use client";

import { PageTitle } from "@/components/shared/page-title";
import { useAuth } from "@/hooks/use-auth";

export function SettingsPanel() {
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Sessao"
        title="Configuracoes"
        description="Resumo da sessao atual e da configuracao operacional carregada no portal."
      />
      <div className="rounded-3xl bg-white/80 p-6 shadow-sm">
        <dl className="grid gap-4 md:grid-cols-2">
          <div>
            <dt className="text-sm text-slate-500">Usuario</dt>
            <dd className="mt-1 text-lg font-semibold">{user?.name ?? "-"}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">E-mail</dt>
            <dd className="mt-1 text-lg font-semibold">{user?.email ?? "-"}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">Papel</dt>
            <dd className="mt-1 text-lg font-semibold">{user?.role ?? "-"}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">Permissoes por categoria</dt>
            <dd className="mt-1 text-lg font-semibold">{user?.permissions.length ?? 0}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
