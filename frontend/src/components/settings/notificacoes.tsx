"use client";

import { useEffect, useState } from "react";
import { BellRing, MailX } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { DESCRICOES, ENVIO, type PreferenciaDeAvisos } from "@/lib/notificacoes";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

/** Configurações > Notificações: cada pessoa liga o que quer receber (nada vem ligado). */
export function NotificacoesPreferencias() {
  const { token } = useAuth();
  const { toast } = useToast();
  const pref = useApi<PreferenciaDeAvisos>("/notificacoes/preferencias");
  const [tipos, setTipos] = useState<Set<string>>(new Set());
  const [minutos, setMinutos] = useState("30");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // Resposta fora do formato (API antiga, erro de proxy) não pode derrubar as Configurações.
  const valida = Array.isArray(pref.data?.disponiveis) && Array.isArray(pref.data?.tipos);

  useEffect(() => {
    if (!pref.data || !Array.isArray(pref.data.tipos)) return;
    setTipos(new Set(pref.data.tipos));
    setMinutos(String(pref.data.fila_minutos));
  }, [pref.data]);

  if (!pref.data || !valida) {
    if (pref.error || pref.data) {
      return <p className="text-destructive">Não foi possível carregar as notificações{pref.error ? `: ${pref.error}` : "."}</p>;
    }
    return <div className="skeleton h-48 rounded-xl" />;
  }
  const [minimo, maximo] = pref.data.fila_minutos_limites;
  const mudou = [...tipos].sort().join() !== [...pref.data.tipos].sort().join() || Number(minutos) !== pref.data.fila_minutos;

  async function salvar() {
    setSalvando(true);
    setErro(null);
    try {
      await apiRequest("/notificacoes/preferencias", { method: "PUT", token, body: JSON.stringify({ tipos: [...tipos], fila_minutos: Number(minutos) }) });
      await pref.refetch();
      toast({ title: "Notificações salvas", kind: "success" });
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível salvar.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <section id="notificacoes" className="scroll-mt-20 space-y-4">
      <div>
        <h2 className="titulo-condensado text-2xl">Notificações</h2>
        <p className="text-muted-foreground">Escolha o que quer receber. Erro, atenção e término só das automações que você pode ver.</p>
      </div>
      <div className="rounded-xl border border-border bg-card p-5 shadow-sm" data-testid="notificacoes">
        <div className="mb-4 flex items-start gap-3 rounded-lg border border-border bg-muted/40 p-3 text-sm">
          {pref.data.envio_por_email === "ligado" ? <BellRing className="mt-0.5 h-4 w-4 shrink-0 text-primary" /> : <MailX className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />}
          <p>{ENVIO[pref.data.envio_por_email]}{pref.data.email ? <> E-mail: <span className="font-medium">{pref.data.email}</span>.</> : null}</p>
        </div>
        <div className="grid gap-2 md:grid-cols-2">
          {pref.data.disponiveis.map((d) => (
            <label key={d.tipo} className="flex cursor-pointer items-start gap-3 rounded-lg border border-border p-3 hover:bg-muted/50">
              <input type="checkbox" className="mt-1 h-4 w-4 accent-[hsl(var(--primary))]" checked={tipos.has(d.tipo)} aria-label={d.rotulo}
                onChange={(e) => { const novo = new Set(tipos); if (e.target.checked) novo.add(d.tipo); else novo.delete(d.tipo); setTipos(novo); }} />
              <span>
                <span className="font-medium text-titulo">{d.rotulo}</span>
                {d.so_gestores && <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">gestores</span>}
                <span className="block text-sm text-muted-foreground">{DESCRICOES[d.tipo]}</span>
                {d.tipo === "fila_parada" && tipos.has("fila_parada") && (
                  <span className="mt-2 flex items-center gap-2 text-sm">
                    Avisar depois de
                    <input type="number" min={minimo} max={maximo} value={minutos} onChange={(e) => setMinutos(e.target.value)}
                      className="h-8 w-20 rounded-md border border-input bg-background px-2" aria-label="Minutos da fila parada" />
                    minutos
                  </span>
                )}
              </span>
            </label>
          ))}
        </div>
        {erro && <p role="alert" className="mt-3 text-sm text-destructive">{erro}</p>}
        <div className="mt-4 flex justify-end">
          <Button onClick={() => void salvar()} disabled={!mudou || salvando}>{salvando ? "Salvando…" : "Salvar notificações"}</Button>
        </div>
      </div>
    </section>
  );
}
