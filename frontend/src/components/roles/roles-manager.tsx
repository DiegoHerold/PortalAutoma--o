"use client";

import { useEffect, useState } from "react";

import { LoadingState } from "@/components/shared/loading-state";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type { Role } from "@/types/role";

export function RolesManager() {
  const { token } = useAuth();
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    apiRequest<Role[]>("/roles", { token })
      .then(setRoles)
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <LoadingState label="Carregando papeis..." />;

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {roles.map((role) => (
        <div key={role.id} className="rounded-3xl bg-white/80 p-6 shadow-sm">
          <h3 className="text-lg font-semibold">{role.name}</h3>
          <p className="mt-1 text-sm text-slate-500">{role.slug}</p>
          <p className="mt-3 text-sm text-slate-600">{role.description ?? "Sem descricao."}</p>
        </div>
      ))}
    </div>
  );
}
