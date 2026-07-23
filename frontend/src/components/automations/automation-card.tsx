import Link from "next/link";
import { ArrowUpRight, Timer } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PriorityBadge } from "@/components/ui/status-badge";
import { executorLabel } from "@/lib/status";
import { formatDuration } from "@/lib/utils";
import type { Automation } from "@/types/automation";

export function AutomationCard({ automation, categoryName }: { automation: Automation; categoryName?: string }) {
  return (
    <Link href={`/automations/${automation.id}`} className="group block">
      <Card className="h-full p-5 transition-colors hover:border-primary/40">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="truncate font-display text-base font-semibold">{automation.name}</h3>
              {!automation.is_active && <Badge tone="neutral">Inativa</Badge>}
            </div>
            <p className="tabular mt-0.5 truncate text-xs text-muted-foreground">{automation.slug}</p>
          </div>
          <ArrowUpRight className="h-4 w-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
        </div>

        <p className="mt-3 line-clamp-2 text-sm text-muted-foreground">
          {automation.description || "Sem descrição cadastrada."}
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <PriorityBadge priority={automation.default_priority} />
          <Badge tone="outline">{executorLabel(automation.executor_type)}</Badge>
          {categoryName && <Badge tone="neutral">{categoryName}</Badge>}
          <span className="tabular ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Timer className="h-3.5 w-3.5" /> {formatDuration(automation.timeout_seconds)}
          </span>
        </div>
      </Card>
    </Link>
  );
}
