"use client";

import { useState } from "react";
import { CheckSquare, GitCompare, Lock, Rocket, ShieldOff } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { EmptyState } from "@/components/shared/empty-state";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { flowVersionStatusMeta } from "@/lib/status";
import {
  blockFlowVersion,
  cloneFlowVersionInto,
  createFlowVersion,
  deprecateFlowVersion,
  listFlowEdges,
  listFlowNodes,
  nextSemver,
  publishFlowVersion,
  validateFlowVersion,
} from "@/lib/flow-api";
import type { Flow, FlowVersion } from "@/types/flow";

export function VersionsPanel({
  flow,
  versions,
  onOpenEditor,
  onRefetch,
}: {
  flow: Flow;
  versions: FlowVersion[];
  onOpenEditor: (versionId: string) => void;
  onRefetch: () => void;
}) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);
  const [compareData, setCompareData] = useState<Record<string, { nodeKeys: string[]; edgeCount: number }>>({});

  const sorted = [...versions].sort((a, b) => b.created_at.localeCompare(a.created_at));
  const hasDraft = versions.some((v) => v.status === "draft");

  async function createDraftFrom(source: FlowVersion) {
    if (!token) return;
    try {
      const [nodes, edges] = await Promise.all([listFlowNodes(token, source.id), listFlowEdges(token, source.id)]);
      await cloneFlowVersionInto(token, flow.id, source, nodes, edges, nextSemver(versions));
      toast({ title: "Novo rascunho criado a partir da versão publicada", kind: "success" });
      onRefetch();
    } catch (err) {
      toast({ title: "Falha ao criar versão", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function createFirstVersion() {
    if (!token) return;
    try {
      await createFlowVersion(token, flow.id, { version: "1.0.0" });
      toast({ title: "Versão 1.0.0 criada", kind: "success" });
      onRefetch();
    } catch (err) {
      toast({ title: "Falha ao criar versão", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function publish(version: FlowVersion) {
    if (!token) return;
    try {
      const result = await validateFlowVersion(token, version.id);
      if (!result.valid) {
        toast({ title: `Não é possível publicar — ${result.issues.length} problema(s)`, description: "Abra o editor para corrigir.", kind: "error" });
        return;
      }
      await publishFlowVersion(token, version.id);
      toast({ title: "Versão publicada", kind: "success" });
      onRefetch();
    } catch (err) {
      toast({ title: "Falha ao publicar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function deprecate(version: FlowVersion) {
    if (!token) return;
    try {
      await deprecateFlowVersion(token, version.id);
      toast({ title: "Versão depreciada", kind: "success" });
      onRefetch();
    } catch (err) {
      toast({ title: "Falha ao depreciar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function block(version: FlowVersion) {
    if (!token) return;
    if (!window.confirm("Bloquear esta versão? Ela deixa de poder ser executada.")) return;
    try {
      await blockFlowVersion(token, version.id);
      toast({ title: "Versão bloqueada", kind: "success" });
      onRefetch();
    } catch (err) {
      toast({ title: "Falha ao bloquear", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  function toggleCompare(id: string) {
    setCompareIds((prev) => (prev.includes(id) ? prev.filter((i) => i !== id) : prev.length < 2 ? [...prev, id] : [prev[1], id]));
  }

  async function openCompare() {
    if (!token || compareIds.length !== 2) return;
    const data: Record<string, { nodeKeys: string[]; edgeCount: number }> = {};
    await Promise.all(
      compareIds.map(async (id) => {
        const [nodes, edges] = await Promise.all([listFlowNodes(token, id), listFlowEdges(token, id)]);
        data[id] = { nodeKeys: nodes.map((n) => `${n.key} (${n.node_type})`), edgeCount: edges.length };
      }),
    );
    setCompareData(data);
    setCompareOpen(true);
  }

  if (versions.length === 0) {
    return (
      <EmptyState
        title="Sem versões"
        description="Crie a primeira versão (rascunho) para começar a montar o Fluxo no editor visual."
        action={<Button onClick={createFirstVersion}>Criar versão 1.0.0</Button>}
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">Selecione duas versões para comparar.</p>
        <div className="flex gap-2">
          {compareIds.length === 2 && (
            <Button size="sm" variant="outline" onClick={openCompare}>
              <GitCompare className="h-3.5 w-3.5" /> Comparar selecionadas
            </Button>
          )}
          {!hasDraft && (
            <Button size="sm" variant="outline" onClick={() => createDraftFrom(sorted.find((v) => v.status === "published") ?? sorted[0])}>
              Nova versão (rascunho)
            </Button>
          )}
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <Table>
          <THead>
            <TR>
              <TH></TH>
              <TH>Versão</TH>
              <TH>Status</TH>
              <TH>Criada em</TH>
              <TH>Publicada em</TH>
              <TH>Notas</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {sorted.map((version) => {
              const meta = flowVersionStatusMeta(version.status);
              return (
                <TR key={version.id}>
                  <TD>
                    <button onClick={() => toggleCompare(version.id)} className="text-muted-foreground hover:text-foreground">
                      <CheckSquare className={`h-4 w-4 ${compareIds.includes(version.id) ? "text-primary" : ""}`} />
                    </button>
                  </TD>
                  <TD className="font-medium">v{version.version}</TD>
                  <TD>
                    <Badge tone={meta.tone}>{meta.label}</Badge>
                  </TD>
                  <TD className="text-sm text-muted-foreground">{formatDate(version.created_at)}</TD>
                  <TD className="text-sm text-muted-foreground">{version.published_at ? formatDate(version.published_at) : "—"}</TD>
                  <TD className="max-w-[200px] truncate text-sm text-muted-foreground">{version.release_notes || "—"}</TD>
                  <TD>
                    <div className="flex justify-end gap-1.5">
                      <Button size="sm" variant="outline" onClick={() => onOpenEditor(version.id)}>
                        {version.status === "draft" ? "Editar" : "Ver"}
                      </Button>
                      {version.status === "draft" && (
                        <Button size="sm" onClick={() => publish(version)}>
                          <Rocket className="h-3.5 w-3.5" /> Publicar
                        </Button>
                      )}
                      {version.status === "published" && (
                        <Button size="sm" variant="outline" onClick={() => deprecate(version)}>
                          Depreciar
                        </Button>
                      )}
                      {(version.status === "published" || version.status === "deprecated") && (
                        <Button size="sm" variant="outline" className="text-destructive" onClick={() => block(version)}>
                          <ShieldOff className="h-3.5 w-3.5" /> Bloquear
                        </Button>
                      )}
                      {version.status === "blocked" && <Lock className="h-4 w-4 self-center text-muted-foreground" />}
                    </div>
                  </TD>
                </TR>
              );
            })}
          </TBody>
        </Table>
      </div>

      <Modal open={compareOpen} onClose={() => setCompareOpen(false)} title="Comparar versões" className="max-w-3xl">
        <div className="grid grid-cols-2 gap-4">
          {compareIds.map((id) => {
            const version = versions.find((v) => v.id === id);
            const data = compareData[id];
            return (
              <div key={id} className="space-y-2 rounded-md border border-border p-3">
                <p className="font-medium">v{version?.version}</p>
                <p className="text-xs text-muted-foreground">{data?.nodeKeys.length ?? 0} nó(s) · {data?.edgeCount ?? 0} conexão(ões)</p>
                <ul className="space-y-1 text-xs">
                  {data?.nodeKeys.map((key) => (
                    <li key={key} className="rounded bg-muted px-2 py-1">
                      {key}
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      </Modal>
    </div>
  );
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" });
}
