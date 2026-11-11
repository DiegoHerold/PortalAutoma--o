"use client";

import { useState } from "react";
import { FileDown, ImageOff, ScrollText } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";

type Linha = { automation_id: number; automacao: string; imagens_dias: number | null; logs_dias: number | null; arquivos_dias: number | null };
type Resposta = { limites: { minimo: number; maximo: number }; automacoes: Linha[] };

function prazo(dias: number | null): string {
  return dias == null ? "Sem prazo" : `${dias} ${dias === 1 ? "dia" : "dias"}`;
}

/**
 * Imagens, logs e (Fase 8) arquivos entregues por automação. Sem prazo, nada é apagado. Com prazo, a limpeza
 * roda a cada hora e não tem volta: por isso a confirmação mostra o que muda.
 */
export function RetencaoPorAutomacao() {
  const lista = useApi<Resposta>("/governance/retencao-por-automacao");
  const [editando, setEditando] = useState<Linha | null>(null);
  const [busca, setBusca] = useState("");

  if (lista.error) return <ErrorState message={lista.error} onRetry={lista.refetch} />;
  const linhas = (lista.data?.automacoes ?? []).filter((l) => l.automacao.toLowerCase().includes(busca.trim().toLowerCase()));
  const comPrazo = (lista.data?.automacoes ?? []).filter((l) => l.imagens_dias != null || l.logs_dias != null || l.arquivos_dias != null).length;

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="titulo-condensado text-2xl">Imagens, logs e arquivos por automação</h2>
          <p className="max-w-3xl text-muted-foreground">
            As telas e os arquivos entregues (planilhas, TXT) têm dados de folha e dados pessoais (LGPD). Defina por quantos dias guardar. Sem prazo, nada é
            apagado. Com prazo, a limpeza roda a cada hora, apaga de vez e fica na auditoria. Etapas, progresso e o
            histórico de tempos ficam: as estimativas não mudam.
          </p>
        </div>
        <p className="text-sm text-muted-foreground">{comPrazo} de {lista.data?.automacoes.length ?? 0} com prazo</p>
      </div>
      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm" data-testid="retencao-por-automacao">
        {(lista.data?.automacoes.length ?? 0) > 8 && (
          <div className="border-b border-border p-3">
            <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar automação"
              className="h-9 w-full max-w-sm rounded-md border border-input bg-background px-3 text-sm" aria-label="Buscar automação" />
          </div>
        )}
        {!lista.data ? (
          <div className="skeleton m-4 h-40 rounded-lg" />
        ) : linhas.length === 0 ? (
          <p className="px-5 py-10 text-center text-muted-foreground">Nenhuma automação.</p>
        ) : (
          <ul className="divide-y divide-border">
            {linhas.map((l) => (
              <li key={l.automation_id} className="flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3">
                <p className="min-w-0 flex-1 truncate font-medium text-titulo">{l.automacao}</p>
                <p className="flex w-40 items-center gap-2 text-sm"><ImageOff className="h-4 w-4 text-muted-foreground" />
                  <span className={l.imagens_dias == null ? "text-muted-foreground" : "font-medium"}>Imagens: {prazo(l.imagens_dias)}</span></p>
                <p className="flex w-40 items-center gap-2 text-sm"><ScrollText className="h-4 w-4 text-muted-foreground" />
                  <span className={l.logs_dias == null ? "text-muted-foreground" : "font-medium"}>Logs: {prazo(l.logs_dias)}</span></p>
                <p className="flex w-40 items-center gap-2 text-sm"><FileDown className="h-4 w-4 text-muted-foreground" />
                  <span className={l.arquivos_dias == null ? "text-muted-foreground" : "font-medium"}>Arquivos: {prazo(l.arquivos_dias)}</span></p>
                <Button variant="outline" size="sm" onClick={() => setEditando(l)} aria-label={`Definir prazos de ${l.automacao}`}>Definir prazos</Button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {editando && lista.data && (
        <Editar linha={editando} limites={lista.data.limites} onClose={() => setEditando(null)} onSaved={lista.refetch} />
      )}
    </section>
  );
}

function Editar({ linha, limites, onClose, onSaved }: { linha: Linha; limites: Resposta["limites"]; onClose: () => void; onSaved: () => Promise<void> }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [imagens, setImagens] = useState(linha.imagens_dias?.toString() ?? "");
  const [logs, setLogs] = useState(linha.logs_dias?.toString() ?? "");
  const [arquivos, setArquivos] = useState(linha.arquivos_dias?.toString() ?? "");
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  const ler = (v: string) => (v.trim() === "" ? null : Number(v));
  const novos = { imagens_dias: ler(imagens), logs_dias: ler(logs), arquivos_dias: ler(arquivos) };
  const invalido = [novos.imagens_dias, novos.logs_dias, novos.arquivos_dias].some((d) => d != null && (!Number.isInteger(d) || d < limites.minimo || d > limites.maximo));
  const encurta = (antes: number | null, depois: number | null) => depois != null && (antes == null || depois < antes);
  const apagaMais = encurta(linha.imagens_dias, novos.imagens_dias) || encurta(linha.logs_dias, novos.logs_dias)
    || encurta(linha.arquivos_dias, novos.arquivos_dias);

  async function salvar() {
    setSalvando(true);
    setErro(null);
    try {
      await apiRequest(`/governance/retencao-por-automacao/${linha.automation_id}`, { method: "PUT", token, body: JSON.stringify(novos) });
      await onSaved();
      toast({ title: "Prazos salvos", kind: "success" });
      onClose();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível salvar.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Modal open onClose={onClose} title={`Prazos de ${linha.automacao}`} description="Deixe em branco para não apagar nada."
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button>
        <Button variant={apagaMais ? "destructive" : "primary"} onClick={() => void salvar()} disabled={invalido || salvando}>
          {salvando ? "Salvando…" : apagaMais ? "Salvar e apagar o que passar do prazo" : "Salvar"}</Button></>}>
      <div className="space-y-4">
        <div className="space-y-3">
          {([["Imagens das telas", imagens, setImagens, "retencao-imagens"], ["Linhas de log", logs, setLogs, "retencao-logs"],
             ["Arquivos entregues", arquivos, setArquivos, "retencao-arquivos"]] as const).map(([rotulo, valor, mudar, id]) => (
            <label key={id} htmlFor={id} className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-medium">{rotulo}: guardar por</span>
              <span className="flex items-center gap-2">
                <input id={id} type="number" min={limites.minimo} max={limites.maximo} value={valor} placeholder="sem prazo"
                  onChange={(e) => mudar(e.target.value)} className="h-10 w-28 rounded-md border border-input bg-background px-3" />
                <span className="text-sm text-muted-foreground">dias</span>
              </span>
            </label>
          ))}
        </div>
        {invalido && <p className="text-sm text-destructive">Use um número inteiro de {limites.minimo} a {limites.maximo} dias, ou deixe em branco.</p>}
        {apagaMais && !invalido && (
          <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm">
            Na próxima limpeza (em até 1 hora), o que for mais antigo que o novo prazo será apagado de vez. Não tem volta.
          </p>
        )}
        {erro && <p role="alert" className="text-sm text-destructive">{erro}</p>}
      </div>
    </Modal>
  );
}
