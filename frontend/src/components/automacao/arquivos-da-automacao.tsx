"use client";

import { useEffect, useState } from "react";
import { Download, FileSpreadsheet, FileText, File as Arquivo, Search } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiDownload } from "@/lib/api";
import { relativo } from "@/lib/fila";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

type ArquivoEntregue = {
  id: string;
  nome: string;
  tipo: string;
  bytes: number | null;
  execucao_id: string;
  item: string | null;
  quando: string | null;
};
type Pagina = { arquivos: ArquivoEntregue[]; cursor: string | null };

function tamanho(bytes: number | null): string {
  if (bytes == null) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} MB`;
}

function Icone({ nome }: { nome: string }) {
  const ext = nome.split(".").pop()?.toLowerCase() ?? "";
  const classe = "h-5 w-5 shrink-0 text-muted-foreground";
  if (["xlsx", "xls", "csv"].includes(ext)) return <FileSpreadsheet className={classe} />;
  if (["txt", "log"].includes(ext)) return <FileText className={classe} />;
  return <Arquivo className={classe} />;
}

/**
 * Arquivos que a automação entregou (Fase 8): planilhas, TXT, o resultado do lote. Ver e baixar
 * exige "ver telas e logs" nesta automação; cada download fica na auditoria.
 */
export function ArquivosDaAutomacao({ id }: { id: string }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [busca, setBusca] = useState("");
  const [aplicada, setAplicada] = useState("");
  const [antes, setAntes] = useState<string | null>(null);
  const [linhas, setLinhas] = useState<ArquivoEntregue[]>([]);
  const [baixando, setBaixando] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => { setAplicada(busca.trim()); setAntes(null); }, 300);
    return () => clearTimeout(t);
  }, [busca]);

  const params = new URLSearchParams({ limite: "50" });
  if (aplicada) params.set("busca", aplicada);
  if (antes) params.set("antes", antes);
  const pagina = useApi<Pagina>(`/automations/${id}/arquivos?${params}`);
  useEffect(() => {
    if (pagina.data) setLinhas((atuais) => (antes ? [...atuais, ...pagina.data!.arquivos] : pagina.data!.arquivos));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pagina.data]);

  async function baixar(a: ArquivoEntregue) {
    setBaixando(a.id);
    try {
      await apiDownload(`/automations/${id}/arquivos/${encodeURIComponent(a.id)}/baixar`, token, a.nome);
    } catch (err) {
      toast({ title: "Não foi possível baixar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setBaixando(null);
    }
  }

  if (pagina.error && linhas.length === 0) return <ErrorState message={pagina.error} onRetry={() => void pagina.refetch()} />;
  return (
    <section className="space-y-4">
      <div>
        <h2 className="titulo-condensado text-2xl">Arquivos</h2>
        <p className="max-w-3xl text-muted-foreground">
          O que a automação entregou: planilhas, TXT e o resultado de cada lote. Têm dados da folha: só quem pode ver telas
          e logs desta automação vê, e cada download fica registrado.
        </p>
      </div>
      <label className="relative block max-w-xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
        <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar pelo nome ou pelo código do item"
          className="h-12 w-full rounded-lg border border-input bg-card pl-11 pr-3 text-base" aria-label="Buscar arquivo" />
      </label>
      {!pagina.data && linhas.length === 0 ? (
        <div className="skeleton h-48 rounded-xl" />
      ) : linhas.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border px-6 py-12 text-center text-muted-foreground">
          {aplicada ? "Nada encontrado com essa busca." : "A automação ainda não entregou nenhum arquivo."}
        </p>
      ) : (
        <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-sm" data-testid="arquivos">
          {linhas.map((a) => (
            <li key={a.id} className="flex items-center gap-4 px-5 py-3.5">
              <Icone nome={a.nome} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-base font-medium text-titulo">{a.nome}</p>
                <p className="text-sm text-muted-foreground">
                  {[a.item ? `item ${a.item}` : "do lote", a.quando ? relativo(a.quando) : null, tamanho(a.bytes)].filter(Boolean).join(" · ")}
                </p>
              </div>
              <Button variant="outline" onClick={() => void baixar(a)} disabled={baixando === a.id} aria-label={`Baixar ${a.nome}`}>
                <Download className="h-4 w-4" /> {baixando === a.id ? "Baixando…" : "Baixar"}
              </Button>
            </li>
          ))}
        </ul>
      )}
      {pagina.data?.cursor && <Button variant="outline" onClick={() => setAntes(pagina.data!.cursor)}>Carregar mais</Button>}
    </section>
  );
}
