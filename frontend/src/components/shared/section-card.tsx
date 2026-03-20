import type { PropsWithChildren } from "react";

import { cn } from "@/lib/utils";

type SectionCardProps = PropsWithChildren<{
  className?: string;
  title?: string;
}>;

export function SectionCard({ className, title, children }: SectionCardProps) {
  return (
    <section className={cn("rounded-3xl border border-slate-200 bg-white/80 p-6 shadow-sm backdrop-blur", className)}>
      {title ? <h2 className="mb-4 text-lg font-semibold">{title}</h2> : null}
      {children}
    </section>
  );
}
