"use client";

import { useState } from "react";
import { Lock, Search } from "lucide-react";

import { ErrorState } from "@/components/shared/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { agrupar, prazoLegivel, type Catalogo, type RegraDeLimpeza } from "@/lib/configuracoes";
import { podeGerenciar } from "@/lib/permissions";
import { relativeFromNow } from "@/lib/utils";

/**
 * Limpeza automática do sistema: notificações, medições das máquinas, sessões vencidas etc.
 * Já vem configurada com os padrões; roda a cada 30 minutos, apaga em lotes e vai para a auditoria.
 */
export function LimpezaDoSistema() {
  const { user } = useAuth();
  const lista = useApi<Catalogo<RegraDeLimpeza>>("/governance/limpeza");
  const [busca, setBusca] = useState("");
  const [editando, setEditando] = useState<RegraDeLimpeza | null>(null);
  const pode = podeGerenciar(user, "retencao");

  if (lista.error) return <ErrorState message={lista.error} onRetry={lista.refetch} />;
  const grupos = agrupar(lista.data, busca);

  return (
    <section className="space-y-4" data-testid="limpeza-do-sistema">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="titulo-condensado text-2xl">Limpeza automática do sistema</h2>
          <p className="max-w-3xl text-muted-foreground">
            Registros que o Portal só precisa por um tempo. A limpeza roda a cada 30 minutos, apaga em lotes e fica na
            auditoria. Já vem com prazos padrão; mude só se precisar.
          </p>
        </div>
        <label className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar regra"
            aria-label="Buscar regra de limpeza" className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-3" />
        </label>
      </div>

      {!lista.data ? (
        <div className="skeleton h-64 rounded-xl" />
      ) : grupos.length === 0 ? (
        <p className="rounded-xl border border-border bg-card px-5 py-10 text-center text-muted-foreground">Nenhuma regra encontrada.</p>
      ) : (
        grupos.map(({ grupo, itens }) => (
          <div key={grupo} className="space-y-2">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{grupo}</h3>
            <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-sm">
              {itens.map((item) => (
                <li key={item.chave} className="flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-4" data-testid={`limpeza-${item.chave}`}>
                  <div className="min-w-0 flex-1 basis-80">
                    <p className="font-medium text-titulo">{item.nome}</p>
                    <p className="text-sm text-muted-foreground">{item.descricao}</p>
                    <p className="mt-1 text-xs text-muted-foreground">Sai: {item.o_que_sai}</p>
                  </div>
                  <div className="w-48 text-right">
                    {item.editavel ? (
                      <>
                        <p className={item.dias == null ? "text-lg text-muted-foreground" : "text-lg font-semibold tabular-nums"}>
                          {prazoLegivel(item.dias)}
                        </p>
                        {item.personalizado ? (
                          <Badge tone="info">Padrão: {prazoLegivel(item.padrao_dias)}</Badge>
                        ) : (
                          <span className="text-xs text-muted-foreground">Padrão</span>
                        )}
                      </>
                    ) : (
                      <Badge tone="outline"><Lock className="h-3.5 w-3.5" /> Guardado sempre</Badge>
                    )}
                  </div>
                  <div className="w-44 text-right text-xs text-muted-foreground">
                    {item.editavel && (item.ultima_limpeza_em
                      ? <>Última limpeza {relativeFromNow(item.ultima_limpeza_em)}<br />{item.total_apagados.toLocaleString("pt-BR")} apagados no total</>
                      : "Ainda não rodou")}
                  </div>
                  <div className="w-24 text-right">
                    {pode && item.editavel && (
                      <Button variant="outline" size="sm" onClick={() => setEditando(item)} aria-label={`Mudar prazo de ${item.nome}`}>Mudar</Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ))
      )}
      {editando && <EditarPrazo item={editando} onClose={() => setEditando(null)} onSaved={lista.refetch} />}
    </section>
  );
}

function EditarPrazo({ item, onClose, onSaved }: { item: RegraDeLimpeza; onClose: () => void; onSaved: () => Promise<void> }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [semPrazo, setSemPrazo] = useState(item.dias == null);
  const [texto, setTexto] = useState(String(item.dias ?? item.padrao_dias ?? item.minimo_dias));
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const dias = semPrazo ? null : Number(texto);
  const valido = dias == null || (Number.isInteger(dias) && dias >= item.minimo_dias && dias <= item.maximo_dias);
  const encurta = dias != null && (item.dias == null || dias < item.dias);

  async function salvar(corpo: { dias?: number | null; voltar_ao_padrao?: boolean }, titulo: string) {
    setSalvando(true);
    setErro(null);
    try {
      await apiRequest(`/governance/limpeza/${encodeURIComponent(item.chave)}`, { method: "PUT", token, body: JSON.stringify(corpo) });
      await onSaved();
      toast({ title: titulo, kind: "success" });
      onClose();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível salvar.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Modal open onClose={onClose} title={item.nome} description={`Sai: ${item.o_que_sai}`}
      footer={<>
        {item.personalizado && (
          <Button variant="ghost" className="mr-auto" disabled={salvando}
            onClick={() => void salvar({ voltar_ao_padrao: true }, `${item.nome}: ${prazoLegivel(item.padrao_dias)} (padrão)`)}>
            Voltar ao padrão ({prazoLegivel(item.padrao_dias)})
          </Button>
        )}
        <Button variant="ghost" onClick={onClose}>Cancelar</Button>
        <Button variant={encurta ? "destructive" : "primary"} disabled={!valido || salvando}
          onClick={() => void salvar({ dias }, `${item.nome}: ${prazoLegivel(dias)}`)}>
          {salvando ? "Salvando…" : encurta ? "Salvar e apagar o que passar do prazo" : "Salvar"}
        </Button>
      </>}>
      <div className="space-y-4">
        <label htmlFor="prazo-da-limpeza" className="flex flex-wrap items-center gap-3">
          <span className="font-medium">Guardar por</span>
          <input id="prazo-da-limpeza" type="number" min={item.minimo_dias} max={item.maximo_dias} step={1} value={texto}
            disabled={semPrazo} onChange={(e) => setTexto(e.target.value)} autoFocus
            className="h-11 w-28 rounded-md border border-input bg-background px-3 tabular text-lg disabled:opacity-50" />
          <span className="text-muted-foreground">dias</span>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={semPrazo} onChange={(e) => setSemPrazo(e.target.checked)} />
          Sem prazo: não apagar nada
        </label>
        <p className="text-sm text-muted-foreground">De {item.minimo_dias} a {item.maximo_dias} dias. Padrão: {prazoLegivel(item.padrao_dias)}.</p>
        {!valido && <p className="text-sm text-destructive">Use um número inteiro de {item.minimo_dias} a {item.maximo_dias}.</p>}
        {encurta && valido && (
          <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm">
            Na próxima limpeza (em até 30 minutos), o que for mais antigo que o novo prazo será apagado de vez.
          </p>
        )}
        {erro && <p role="alert" className="text-sm text-destructive">{erro}</p>}
      </div>
    </Modal>
  );
}
