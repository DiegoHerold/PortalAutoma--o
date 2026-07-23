import Link from "next/link";
import { ShieldX } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function ForbiddenPage() {
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-10 text-center shadow-sm">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
          <ShieldX className="h-6 w-6" />
        </div>
        <h1 className="font-display text-2xl font-semibold">Acesso negado</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Seu usuário não possui permissão suficiente para visualizar este recurso.
        </p>
        <Button asChild className="mt-6" variant="outline">
          <Link href="/dashboard">Voltar ao dashboard</Link>
        </Button>
      </div>
    </main>
  );
}
