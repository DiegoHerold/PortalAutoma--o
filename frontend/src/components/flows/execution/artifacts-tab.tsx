"use client";

import { useState } from "react";
import { Download } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { apiDownload } from "@/lib/api";
import { jobStatusMeta } from "@/lib/status";
import { formatDateTime } from "@/lib/utils";
import type { ExecutionArtifact } from "@/types/execution";

function formatBytes(bytes: number | null): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ArtifactsTab({
  artifacts,
  loading,
  error,
  onRetry,
  nodeLabelByTask,
}: {
  artifacts: ExecutionArtifact[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  nodeLabelByTask: Map<string, string>;
}) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (loading) return <Skeleton className="h-40 rounded-lg" />;
  if (artifacts.length === 0) {
    return <EmptyState title="Sem artefatos" description="Nenhuma automação deste Fluxo gerou artefatos até agora." />;
  }

  async function download(artifact: ExecutionArtifact) {
    setDownloadingId(artifact.id);
    try {
      await apiDownload(`/artifacts/${artifact.id}/download`, token, artifact.name);
    } catch (err) {
      toast({ title: "Falha ao baixar artefato", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setDownloadingId(null);
    }
  }

  const sorted = [...artifacts].sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <Table>
        <THead>
          <TR>
            <TH>Nome</TH>
            <TH>Nó</TH>
            <TH>Tipo</TH>
            <TH>Tamanho</TH>
            <TH>Status</TH>
            <TH>Criado em</TH>
            <TH className="text-right">Ações</TH>
          </TR>
        </THead>
        <TBody>
          {sorted.map((artifact) => {
            const meta = jobStatusMeta(artifact.status === "available" ? "succeeded" : artifact.status);
            return (
              <TR key={artifact.id}>
                <TD className="font-medium">{artifact.name}</TD>
                <TD className="text-sm text-muted-foreground">{nodeLabelByTask.get(artifact.task_execution_id) ?? "—"}</TD>
                <TD className="text-sm text-muted-foreground">{artifact.content_type}</TD>
                <TD className="tabular text-sm text-muted-foreground">{formatBytes(artifact.size_bytes)}</TD>
                <TD>
                  <Badge tone={meta.tone}>{artifact.status}</Badge>
                </TD>
                <TD className="text-sm text-muted-foreground">{formatDateTime(artifact.created_at)}</TD>
                <TD>
                  <div className="flex justify-end">
                    <Button
                      size="icon"
                      variant="ghost"
                      title="Baixar"
                      disabled={artifact.status !== "available" || downloadingId === artifact.id}
                      onClick={() => download(artifact)}
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                  </div>
                </TD>
              </TR>
            );
          })}
        </TBody>
      </Table>
    </div>
  );
}
