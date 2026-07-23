import Link from "next/link";
import { ArrowUpRight, PackageCheck, Pencil, Timer, Trash2 } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PriorityBadge } from "@/components/ui/status-badge";
import { executorLabel } from "@/lib/status";
import { formatDuration } from "@/lib/utils";
import type { Automation } from "@/types/automation";

export function AutomationCard({
  automation,
  categoryName,
  onEdit,
  onDelete,
}: {
  automation: Automation;
  categoryName?: string;
  onEdit?: (automation: Automation) => void;
  onDelete?: (automation: Automation) => void;
}) {
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
          <div className="flex shrink-0 items-center gap-1">
            {onEdit && (
              <Button
                size="icon"
                variant="ghost"
                title="Editar automacao"
                onClick={(e) => {
                  e.preventDefault();
                  onEdit(automation);
                }}
              >
                <Pencil className="h-4 w-4" />
              </Button>
            )}
            {onDelete && (
              <Button
                size="icon"
                variant="ghost"
                title="Apagar automacao"
                onClick={(e) => {
                  e.preventDefault();
                  onDelete(automation);
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
            <ArrowUpRight className="h-4 w-4 text-muted-foreground transition-colors group-hover:text-primary" />
          </div>
        </div>

        <p className="mt-3 line-clamp-2 text-sm text-muted-foreground">
          {automation.description || "Sem descricao cadastrada."}
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <PriorityBadge priority={automation.default_priority} />
          <Badge tone="outline">{executorLabel(automation.executor_type)}</Badge>
          {automation.package_url && (
            <Badge tone="neutral">
              <PackageCheck className="h-3 w-3" /> pacote
            </Badge>
          )}
          {categoryName && <Badge tone="neutral">{categoryName}</Badge>}
          <span className="tabular ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Timer className="h-3.5 w-3.5" /> {formatDuration(automation.timeout_seconds)}
          </span>
        </div>
      </Card>
    </Link>
  );
}
