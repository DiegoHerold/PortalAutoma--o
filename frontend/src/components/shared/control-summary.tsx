import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

type SummaryMetric = {
  label: string;
  value: string | number;
  detail: string;
  icon: LucideIcon;
  tone?: "default" | "success" | "warning" | "danger" | "info";
};

const tones = {
  default: "text-foreground",
  success: "text-success",
  warning: "text-warning",
  danger: "text-destructive",
  info: "text-info",
};

export function ControlSummary({
  metrics,
  children,
}: {
  metrics: SummaryMetric[];
  children?: ReactNode;
}) {
  return (
    <section className="border-y border-border py-1">
      <div className="grid divide-y divide-border sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-4">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <div key={metric.label} className="flex min-w-0 gap-3 px-4 py-4 first:pl-0 last:pr-0 sm:first:pl-0 lg:last:pr-0">
              <Icon className={cn("mt-0.5 h-5 w-5 shrink-0", tones[metric.tone ?? "default"])} />
              <div className="min-w-0">
                <p className="tabular text-xl font-semibold">{metric.value}</p>
                <p className="text-sm font-medium">{metric.label}</p>
                <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{metric.detail}</p>
              </div>
            </div>
          );
        })}
      </div>
      {children && <div className="mt-1 border-t border-border py-3">{children}</div>}
    </section>
  );
}
