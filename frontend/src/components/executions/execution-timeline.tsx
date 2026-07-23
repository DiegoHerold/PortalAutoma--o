import { cn, formatDateTime } from "@/lib/utils";

type Step = { key: string; label: string; at?: string | null; done: boolean; current?: boolean; failed?: boolean };

export function ExecutionTimeline({ steps }: { steps: Step[] }) {
  return (
    <ol className="relative space-y-6 pl-6">
      <span className="absolute left-[7px] top-1 h-[calc(100%-0.5rem)] w-px bg-border" />
      {steps.map((step) => (
        <li key={step.key} className="relative">
          <span
            className={cn(
              "absolute -left-[23px] top-0.5 flex h-4 w-4 items-center justify-center rounded-full border-2",
              step.failed
                ? "border-destructive bg-destructive"
                : step.done
                  ? "border-success bg-success"
                  : step.current
                    ? "border-info bg-info animate-pulse-dot"
                    : "border-border bg-background",
            )}
          />
          <p className={cn("text-sm font-medium", !step.done && !step.current && "text-muted-foreground")}>
            {step.label}
          </p>
          <p className="tabular text-xs text-muted-foreground">{step.at ? formatDateTime(step.at) : "—"}</p>
        </li>
      ))}
    </ol>
  );
}
