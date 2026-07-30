import type { LucideIcon } from "lucide-react";

type OperationStep = { label: string; description: string; icon: LucideIcon };

export function OperationPath({ steps }: { steps: OperationStep[] }) {
  return (
    <ol className="grid divide-y divide-border rounded-lg border border-border bg-card sm:grid-cols-3 sm:divide-x sm:divide-y-0">
      {steps.map((step, index) => {
        const Icon = step.icon;
        return (
          <li key={step.label} className="flex gap-3 p-4">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary"><Icon className="h-4 w-4" /></span>
            <div><p className="text-sm font-medium">{index + 1}. {step.label}</p><p className="mt-1 text-xs leading-relaxed text-muted-foreground">{step.description}</p></div>
          </li>
        );
      })}
    </ol>
  );
}
