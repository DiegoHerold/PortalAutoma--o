"use client";

import { ShieldCheck } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import type { Role } from "@/types/role";

export function RolesManager() {
  const roles = useApi<Role[]>("/roles");

  if (roles.error) return <ErrorState message={roles.error} onRetry={roles.refetch} />;
  if (roles.loading)
    return (
      <div className="grid gap-4 md:grid-cols-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <Skeleton key={i} className="h-32 rounded-lg" />
        ))}
      </div>
    );
  const list = roles.data ?? [];
  if (list.length === 0) return <EmptyState icon={ShieldCheck} title="Sem papéis" description="Nenhum papel cadastrado." />;

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {list.map((role) => (
        <Card key={role.id} className="p-5">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" />
            <h3 className="font-display text-base font-semibold">{role.name}</h3>
            <Badge tone="outline" className="tabular ml-auto">
              {role.slug}
            </Badge>
          </div>
          <p className="mt-3 text-sm text-muted-foreground">{role.description || "Sem descrição."}</p>
        </Card>
      ))}
    </div>
  );
}
