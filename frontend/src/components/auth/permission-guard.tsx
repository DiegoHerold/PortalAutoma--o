"use client";

import type { ReactNode } from "react";

import { EmptyState } from "@/components/shared/empty-state";

export function PermissionGuard({
  allowed,
  children,
}: {
  allowed: boolean;
  children: ReactNode;
}) {
  if (!allowed) {
    return (
      <EmptyState
        title="Acesso restrito"
        description="Seu usuario nao possui permissao suficiente para acessar este recurso."
      />
    );
  }

  return <>{children}</>;
}
