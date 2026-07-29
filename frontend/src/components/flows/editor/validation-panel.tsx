import { AlertTriangle, CheckCircle2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { FlowValidationIssue } from "@/types/flow";

export function ValidationSummary({
  issues,
  onFocusNode,
}: {
  issues: FlowValidationIssue[];
  onFocusNode?: (nodeId: string) => void;
}) {
  if (issues.length === 0) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-success/30 bg-success/5 px-3 py-2 text-xs text-success">
        <CheckCircle2 className="h-4 w-4" /> Nenhum problema encontrado. O Fluxo pode ser publicado.
      </div>
    );
  }

  return (
    <div className="space-y-1.5 rounded-md border border-destructive/30 bg-destructive/5 p-3">
      <p className="flex items-center gap-1.5 text-xs font-semibold text-destructive">
        <AlertTriangle className="h-4 w-4" /> {issues.length} problema(s) de validação
      </p>
      <ul className="space-y-1">
        {issues.map((issue, i) => {
          const nodeId = (issue.details as { node_id?: string })?.node_id;
          return (
            <li key={i} className="flex items-start justify-between gap-2 text-xs text-muted-foreground">
              <span>
                <Badge tone="destructive" className="mr-1.5 text-[10px]">
                  {issue.code}
                </Badge>
                {issue.message}
              </span>
              {nodeId && onFocusNode && (
                <button type="button" className="shrink-0 text-primary underline underline-offset-2" onClick={() => onFocusNode(nodeId)}>
                  ver nó
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
