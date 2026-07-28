import { AlertTriangle, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";

export function ErrorState({ message, onRetry }: { message?: string | null; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-destructive/30 bg-destructive/5 px-6 py-10 text-center">
      <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <AlertTriangle className="h-5 w-5" />
      </div>
      <p className="text-sm font-medium text-foreground">Não foi possível carregar</p>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">{message || "Erro na comunicação com a API."}</p>
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-4" onClick={onRetry}>
          <RotateCw className="h-3.5 w-3.5" /> Tentar novamente
        </Button>
      )}
    </div>
  );
}
