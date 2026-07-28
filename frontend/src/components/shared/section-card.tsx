import type { PropsWithChildren, ReactNode } from "react";

import { cn } from "@/lib/utils";

type SectionCardProps = PropsWithChildren<{
  className?: string;
  title?: string;
  description?: string;
  actions?: ReactNode;
  bodyClassName?: string;
}>;

export function SectionCard({ className, title, description, actions, bodyClassName, children }: SectionCardProps) {
  return (
    <section className={cn("rounded-lg border border-border bg-card text-card-foreground shadow-sm", className)}>
      {(title || actions) && (
        <div className="flex items-center justify-between gap-4 border-b border-border p-5">
          <div>
            {title && <h2 className="font-display text-base font-semibold tracking-tight">{title}</h2>}
            {description && <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>}
          </div>
          {actions}
        </div>
      )}
      <div className={cn("p-5", bodyClassName)}>{children}</div>
    </section>
  );
}
