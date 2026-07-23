import { Spinner } from "@/components/ui/spinner";

export function LoadingState({ label = "Carregando..." }: { label?: string }) {
  return (
    <div className="flex items-center gap-2.5 rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
      <Spinner />
      {label}
    </div>
  );
}
