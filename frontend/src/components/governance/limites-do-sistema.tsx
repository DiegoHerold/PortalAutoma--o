"use client";

import { useState } from "react";
import { FileCog, Search } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { agrupar, itensDe, NOME_DA_UNIDADE, valorLegivel, type Catalogo, type LimiteDoSistema } from "@/lib/configuracoes";
import { podeGerenciar } from "@/lib/permissions";

/**
 * Limites do sistema, por grupo. Cada um diz para que serve e onde vale; mudar vale na hora.
 * Os que vêm do arquivo .env aparecem só para consulta.
 */
export function LimitesDoSistema() {
  const { user } = useAuth();
  const lista = useApi<Catalogo<LimiteDoSistema>>("/governance/limites");
  const [busca, setBusca] = useState("");
  const [editando, setEditando] = useState<LimiteDoSistema | null>(null);
  const pode = podeGerenciar(user, "limites");

  if (lista.error) return <ErrorState message={lista.error} onRetry={lista.refetch} />;
  const grupos = agrupar(lista.data, busca);
  const todos = itensDe(lista.data);
  const alterados = todos.filter((i) => i.personalizado).length;

  return (
    <div className="space-y-6" data-testid="limites-do-sistema">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <label className="relative w-full max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar limite"
            aria-label="Buscar limite" className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-3" />
        </label>
        <p className="text-sm text-muted-foreground">
          {lista.data ? `${todos.length} limites · ${alterados} fora do padrão` : ""}
        </p>
      </div>

      {!lista.data ? (
        <div className="skeleton h-64 rounded-xl" />
      ) : grupos.length === 0 ? (
        <EmptyState icon={Search} title="Nenhum limite encontrado" description="Tente outra palavra na busca." />
      ) : (
        grupos.map(({ grupo, itens }) => (
          <section key={grupo} className="space-y-2">
            <h2 className="titulo-condensado text-xl">{grupo}</h2>
            <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-sm">
              {itens.map((item) => (
                <li key={item.chave} className="flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-4" data-testid={`limite-${item.chave}`}>
                  <div className="min-w-0 flex-1 basis-80">
                    <p className="font-medium text-titulo">{item.nome}</p>
                    <p className="text-sm text-muted-foreground">{item.descricao}</p>
                    <p className="mt-1 text-xs text-muted-foreground">Vale em: {item.onde_vale}</p>
                  </div>
                  <div className="w-44 text-right">
                    <p className="text-lg font-semibold tabular-nums">{valorLegivel(item.valor, item.unidade)}</p>
                    {item.origem === "arquivo" ? (
                      <Badge tone="outline"><FileCog className="h-3.5 w-3.5" /> Arquivo .env</Badge>
                    ) : item.personalizado ? (
                      <Badge tone="info">Padrão: {valorLegivel(item.padrao, item.unidade)}</Badge>
                    ) : (
                      <span className="text-xs text-muted-foreground">Padrão</span>
                    )}
                  </div>
                  <div className="w-24 text-right">
                    {pode && item.origem === "portal" && (
                      <Button variant="outline" size="sm" onClick={() => setEditando(item)} aria-label={`Mudar ${item.nome}`}>Mudar</Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
      {editando && <EditarLimite item={editando} onClose={() => setEditando(null)} onSaved={lista.refetch} />}
    </div>
  );
}

function EditarLimite({ item, onClose, onSaved }: { item: LimiteDoSistema; onClose: () => void; onSaved: () => Promise<void> }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [texto, setTexto] = useState(String(item.valor));
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const valor = Number(texto);
  const valido = texto.trim() !== "" && Number.isInteger(valor) && valor >= item.minimo && valor <= item.maximo;

  async function salvar(novo: number) {
    setSalvando(true);
    setErro(null);
    try {
      await apiRequest(`/governance/limites/${encodeURIComponent(item.chave)}`, { method: "PUT", token, body: JSON.stringify({ valor: novo }) });
      await onSaved();
      toast({ title: `${item.nome}: ${valorLegivel(novo, item.unidade)}`, kind: "success" });
      onClose();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível salvar.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Modal open onClose={onClose} title={item.nome} description={item.descricao}
      footer={<>
        {item.valor !== item.padrao && (
          <Button variant="ghost" className="mr-auto" disabled={salvando} onClick={() => void salvar(item.padrao)}>
            Voltar ao padrão ({valorLegivel(item.padrao, item.unidade)})
          </Button>
        )}
        <Button variant="ghost" onClick={onClose}>Cancelar</Button>
        <Button onClick={() => void salvar(valor)} disabled={!valido || salvando || valor === item.valor}>{salvando ? "Salvando…" : "Salvar"}</Button>
      </>}>
      <div className="space-y-3">
        <label htmlFor="valor-do-limite" className="flex flex-wrap items-center gap-3">
          <input id="valor-do-limite" type="number" min={item.minimo} max={item.maximo} step={1} value={texto} autoFocus
            onChange={(e) => setTexto(e.target.value)} className="h-11 w-40 rounded-md border border-input bg-background px-3 tabular text-lg" />
          <span className="text-muted-foreground">{NOME_DA_UNIDADE[item.unidade]}</span>
          {valido && item.unidade !== "quantidade" && item.unidade !== "mb" && (
            <span className="font-medium">= {valorLegivel(valor, item.unidade)}</span>
          )}
        </label>
        <p className="text-sm text-muted-foreground">
          De {valorLegivel(item.minimo, item.unidade)} a {valorLegivel(item.maximo, item.unidade)}. Vale na hora, em: {item.onde_vale}
        </p>
        {!valido && <p className="text-sm text-destructive">Use um número inteiro dentro da faixa.</p>}
        {erro && <p role="alert" className="text-sm text-destructive">{erro}</p>}
      </div>
    </Modal>
  );
}
