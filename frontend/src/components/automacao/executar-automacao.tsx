"use client";

import { useEffect, useMemo, useState } from "react";
import { CornerDownRight, Play, Search } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { ErroComCampos, enviar, valoresIniciais, type Formulario } from "@/lib/campos";
import { cn } from "@/lib/utils";
import { CampoDeEntrada } from "@/components/campos/campo-de-entrada";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";

type ItemLista = { chave: string; rotulo: string; grupo: string | null; ativo: boolean };
type ListaDeItens = { itens: ItemLista[]; contagem: { ativos: number; total: number } };

/**
 * Acionar a automação: escolher os itens (quando ela tem itens) e preencher as informações
 * do pedido, geradas pelos campos da automação. O Portal confere tudo antes de pôr na fila.
 */
export function ExecutarAutomacao({ id, nome, aberto, fechar, preEscolhidos = [], pedido }: {
  id: string;
  nome: string;
  aberto: boolean;
  fechar: () => void;
  preEscolhidos?: string[];
  pedido?: () => void;
}) {
  const { token } = useAuth();
  const { toast } = useToast();
  const form = useApi<Formulario>(aberto ? `/automations/${id}/formulario` : null);
  const temItens = !!form.data?.item;
  const lista = useApi<ListaDeItens>(aberto && temItens ? `/automations/${id}/itens?ativos=true&limite=500` : null);
  const [escolhidos, setEscolhidos] = useState<Set<string>>(new Set(preEscolhidos));
  const [comFiliais, setComFiliais] = useState(true);
  const [busca, setBusca] = useState("");
  const [valores, setValores] = useState<Record<string, unknown>>({});
  const [erros, setErros] = useState<Record<string, string>>({});
  const [geral, setGeral] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (aberto) {
      setEscolhidos(new Set(preEscolhidos));
      setErros({});
      setGeral(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aberto]);
  useEffect(() => {
    if (form.data) setValores(valoresIniciais(form.data.entrada));
  }, [form.data]);

  const nomeItem = form.data?.item?.nome ?? "Item";
  const itens = lista.data?.itens ?? [];
  const visiveis = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    return termo ? itens.filter((i) => i.chave.toLowerCase().includes(termo) || i.rotulo.toLowerCase().includes(termo)) : itens;
  }, [itens, busca]);
  const filiaisDe = (chave: string) => itens.filter((i) => i.grupo === chave).length;
  const comAsFiliais = comFiliais ? [...escolhidos].reduce((n, c) => n + filiaisDe(c), 0) : 0;

  function alternar(chave: string) {
    setEscolhidos((atual) => {
      const novo = new Set(atual);
      if (novo.has(chave)) novo.delete(chave);
      else novo.add(chave);
      return novo;
    });
  }

  async function acionar() {
    setEnviando(true);
    setErros({});
    setGeral(null);
    try {
      const r = await enviar<{ jobs: Array<{ existente: boolean }> }>(`/automations/${id}/itens/pedir-execucao`, "POST", {
        chaves: [...escolhidos], com_filiais: comFiliais, parametros: valores }, token);
      const repetidos = r.jobs.filter((j) => j.existente).length;
      toast({ title: `${nome}: na fila`, kind: "success",
        description: repetidos ? `${repetidos} pedido(s) igual(is) já estava(m) na fila e não foi(ram) repetido(s).` : undefined });
      fechar();
      pedido?.();
    } catch (err) {
      if (err instanceof ErroComCampos) {
        setErros(err.campos);
        setGeral(err.message);
      } else {
        setGeral(err instanceof Error ? err.message : "Não foi possível pedir.");
      }
    } finally {
      setEnviando(false);
    }
  }

  const faltaItem = temItens && escolhidos.size === 0;
  return (
    <Modal open={aberto} onClose={fechar} title={`Executar ${nome}`} className="max-w-3xl"
      description={temItens ? `Escolha ${nomeItem.toLowerCase()}s e confira as informações do pedido.` : "Confira as informações do pedido."}
      footer={<>
        <Button variant="ghost" onClick={fechar}>Cancelar</Button>
        <Button onClick={() => void acionar()} disabled={enviando || faltaItem || !form.data}>
          <Play className="h-4 w-4" /> {enviando ? "Pedindo…" : temItens ? `Executar ${escolhidos.size + comAsFiliais} ${nomeItem.toLowerCase()}(s)` : "Executar"}
        </Button>
      </>}>
      {!form.data ? (
        <div className="skeleton h-48 rounded-xl" />
      ) : (
        <div className="space-y-6" data-testid="executar">
          {temItens && (
            <section className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="titulo-condensado text-xl">1. {nomeItem}s</h3>
                <span className="text-sm text-muted-foreground">{escolhidos.size} escolhido(s){comAsFiliais ? ` + ${comAsFiliais} filial(is)` : ""}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                <label className="relative min-w-[14rem] flex-1">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar por código ou nome"
                    className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-3" aria-label={`Buscar ${nomeItem.toLowerCase()}`} />
                </label>
                <Button variant="outline" onClick={() => setEscolhidos(new Set([...escolhidos, ...visiveis.filter((i) => !i.grupo || !comFiliais).map((i) => i.chave)]))}>
                  Marcar {busca ? "os achados" : "todos"}
                </Button>
                {escolhidos.size > 0 && <Button variant="ghost" onClick={() => setEscolhidos(new Set())}>Limpar</Button>}
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="h-4 w-4 accent-[hsl(var(--primary))]" checked={comFiliais} onChange={(e) => setComFiliais(e.target.checked)} />
                Incluir as filiais de cada matriz escolhida
              </label>
              {lista.data && itens.length === 0 ? (
                <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-muted-foreground">
                  Nenhum {nomeItem.toLowerCase()} ativo. Cadastre ou importe na aba Itens.
                </p>
              ) : (
                <ul className="max-h-72 divide-y divide-border overflow-y-auto rounded-lg border border-border">
                  {visiveis.map((i) => {
                    const vaiJunto = comFiliais && !!i.grupo && escolhidos.has(i.grupo);  // filial da matriz escolhida
                    return (
                    <li key={i.chave}>
                      <label className={cn("flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-muted", i.grupo && "pl-8")}
                        title={vaiJunto ? "Vai junto com a matriz" : undefined}>
                        <input type="checkbox" className="h-4 w-4 accent-[hsl(var(--primary))]" checked={escolhidos.has(i.chave) || vaiJunto}
                          disabled={vaiJunto} onChange={() => alternar(i.chave)} aria-label={`Escolher ${i.rotulo}`} />
                        {i.grupo && <CornerDownRight className="h-4 w-4 text-muted-foreground" />}
                        <span className="tabular w-16 shrink-0 text-muted-foreground">{i.chave}</span>
                        <span className="truncate">{i.rotulo}</span>
                        {!i.grupo && filiaisDe(i.chave) > 0 && <span className="ml-auto text-xs text-muted-foreground">{filiaisDe(i.chave)} filial(is)</span>}
                        {vaiJunto && <span className="ml-auto text-xs text-muted-foreground">vai com a matriz</span>}
                      </label>
                    </li>
                    );
                  })}
                </ul>
              )}
            </section>
          )}
          <section className="space-y-3">
            <h3 className="titulo-condensado text-xl">{temItens ? "2. " : ""}Informações do pedido</h3>
            {form.data.entrada.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Esta automação não pede nenhuma informação. Para criar campos (ex.: competência), use a aba Campos.
              </p>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {form.data.entrada.map((c) => (
                  <CampoDeEntrada key={c.chave} campo={c} valor={valores[c.chave]} erro={erros[c.chave]}
                    mudar={(v) => {
                      setValores((atual) => ({ ...atual, [c.chave]: v }));
                      setErros((atuais) => { const resto = { ...atuais }; delete resto[c.chave]; return resto; });
                    }} />
                ))}
              </div>
            )}
          </section>
          {geral && <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{geral}</p>}
        </div>
      )}
    </Modal>
  );
}
