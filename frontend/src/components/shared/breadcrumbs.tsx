import Link from "next/link";
import { ChevronRight } from "lucide-react";

export type Crumb = { label: string; href?: string };

export function Breadcrumbs({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm text-muted-foreground">
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        return (
          <span key={`${item.label}-${index}`} className="flex items-center gap-1.5">
            {index > 0 && <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/60" />}
            {item.href && !isLast ? (
              <Link href={item.href} className="truncate hover:text-foreground">
                {item.label}
              </Link>
            ) : (
              <span className={isLast ? "truncate font-medium text-foreground" : "truncate"}>{item.label}</span>
            )}
          </span>
        );
      })}
    </nav>
  );
}
