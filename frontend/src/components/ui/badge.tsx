import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type Tone = "neutral" | "primary" | "success" | "warning" | "info" | "destructive" | "outline";

const tones: Record<Tone, string> = {
  neutral: "bg-muted text-muted-foreground",
  primary: "bg-primary/10 text-primary ring-1 ring-inset ring-primary/20",
  success: "bg-success/12 text-success ring-1 ring-inset ring-success/25",
  warning: "bg-warning/15 text-warning ring-1 ring-inset ring-warning/30",
  info: "bg-info/12 text-info ring-1 ring-inset ring-info/25",
  destructive: "bg-destructive/12 text-destructive ring-1 ring-inset ring-destructive/25",
  outline: "border border-border text-foreground",
};

export type BadgeProps = HTMLAttributes<HTMLSpanElement> & { tone?: Tone };

export function Badge({ className, tone = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
