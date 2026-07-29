"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Trash2 } from "lucide-react";

import { Sheet } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Label, Select } from "@/components/ui/input";
import { ConditionEditor } from "@/components/flows/editor/condition-editor";
import type { FlowCanvasEdge } from "@/components/flows/editor/types";
import type { FlowEdgeType } from "@/types/flow";

export function EdgePanel({
  edge,
  sourceName,
  targetName,
  upstreamNodes,
  readOnly,
  onClose,
  onSave,
  onDelete,
}: {
  edge: FlowCanvasEdge | null;
  sourceName: string;
  targetName: string;
  upstreamNodes: { key: string; name: string }[];
  readOnly: boolean;
  onClose: () => void;
  onSave: (patch: { edge_type: FlowEdgeType; condition: Record<string, unknown> | null }) => void;
  onDelete: () => void;
}) {
  const [edgeType, setEdgeType] = useState<FlowEdgeType>((edge?.data?.edgeType as FlowEdgeType) ?? "success");
  const [condition, setCondition] = useState<Record<string, unknown> | null>(edge?.data?.condition ?? null);

  // Sempre que uma conexão diferente é selecionada, resincroniza o formulário com seus dados reais.
  useEffect(() => {
    if (!edge) return;
    setEdgeType((edge.data?.edgeType as FlowEdgeType) ?? "success");
    setCondition(edge.data?.condition ?? null);
  }, [edge]);

  if (!edge) return null;

  const issues = edge.data?.issues ?? [];

  function save() {
    onSave({ edge_type: edgeType, condition: edgeType === "conditional" ? condition : null });
  }

  return (
    <Sheet
      open={Boolean(edge)}
      onClose={onClose}
      title="Conexão"
      description={`${sourceName} → ${targetName}`}
      widthClassName="w-full sm:max-w-md"
      footer={
        !readOnly && (
          <>
            <Button variant="outline" className="mr-auto text-destructive hover:bg-destructive/10" onClick={onDelete}>
              <Trash2 className="h-4 w-4" /> Remover conexão
            </Button>
            <Button onClick={save}>Salvar</Button>
          </>
        )
      }
    >
      <div className="space-y-4">
        {issues.length > 0 && (
          <div className="space-y-1.5 rounded-md border border-destructive/30 bg-destructive/5 p-3">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-destructive">
              <AlertTriangle className="h-3.5 w-3.5" /> {issues.length} problema(s) nesta conexão
            </p>
            <ul className="space-y-1">
              {issues.map((issue, i) => (
                <li key={i} className="text-xs text-muted-foreground">
                  <Badge tone="destructive" className="mr-1.5 text-[10px]">
                    {issue.code}
                  </Badge>
                  {issue.message}
                </li>
              ))}
            </ul>
          </div>
        )}

        <Field>
          <Label htmlFor="edge-type">Tipo de conexão</Label>
          <Select id="edge-type" value={edgeType} disabled={readOnly} onChange={(e) => setEdgeType(e.target.value as FlowEdgeType)}>
            <option value="success">Sucesso — segue se a origem for bem-sucedida</option>
            <option value="failure">Falha — segue se a origem falhar</option>
            <option value="always">Sempre — segue independente do resultado</option>
            <option value="conditional">Condicional — segue se a condição for verdadeira</option>
          </Select>
        </Field>

        {edgeType === "conditional" && (
          <Field>
            <Label>Condição para seguir por esta conexão</Label>
            <ConditionEditor
              value={condition}
              onChange={setCondition}
              upstreamNodes={upstreamNodes}
              readOnly={readOnly}
              emptyHint={`Adicione uma regra usando a saída de "${sourceName}" ou de um nó anterior.`}
            />
          </Field>
        )}
      </div>
    </Sheet>
  );
}
