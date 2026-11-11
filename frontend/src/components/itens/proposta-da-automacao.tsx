"use client";

import { useEffect, useState } from "react";
import { Inbox } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { relativo } from "@/lib/fila";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";

type Linha = { chave: string; rotulo: string; grupo: string | null };
type Proposta = {
  recebida_em: string;
  instancia_id: string | null;
  total: number;
  novos: Linha[];
  alterados: Array<Linha & { mudancas: string[] }>;
  iguais: number;
  erros: Array<{ linha: number | null; chave: string; campos: Record<string, string> }>;
};

const NOMES: Record<string, string> = { rotulo: "nome", grupo: "grupo", ativo: "situação" };

/** "atributos.caminho_saida" → "caminho saida": o que mudou, em palavras. */
function mudanca(m: string): string {
  return NOMES[m] ?? m.replace(/^atributos\./, "").replaceAll("_", " ");
}

/**
 * A tabela de itens que a automação mandou ao conectar (Fase 8): nada entra no cadastro sem
 * alguém aprovar. Só aparece para quem edita os itens.
 */
export function PropostaDaAutomacao({ id, nomeItem, aprovada }: { id: string; nomeItem: string; aprovada: () => void }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const proposta = useApi<Proposta | null>(`/automations/${id}/itens/proposta`);
  const [aberta, setAberta] = useState(false);
  const [escolhidos, setEscolhidos] = useState<Set<string>>(new Set());
  const [erro, setErro] = useState<string | null>(null);
  const [gravando, setGravando] = useState(false);
  const dados = proposta.data;

  useEffect(() => {
    if (dados?.novos) setEscolhidos(new Set([...dados.novos, ...dados.alterados].map((l) => l.chave)));
  }, [dados]);

  if (!dados?.novos || dados.novos.length + dados.alterados.length + dados.erros.length === 0) return null;
  const plural = `${nomeItem.toLowerCase()}s`;

  function alternar(chave: string) {
    setEscolhidos((atual) => {
      const novo = new Set(atual);
      if (novo.has(chave)) novo.delete(chave);
      else novo.add(chave);
      return novo;
    });
  }

  async function aprovar() {
    setGravando(true);
    setErro(null);
    try {
      const r = await apiRequest<{ criados: number; alterados: number }>(`/automations/${id}/itens/proposta/aprovar`, {
        method: "POST", token, body: JSON.stringify({ chaves: [...escolhidos] }) });
      toast({ title: `${r.criados} criado(s), ${r.alterados} alterado(s)`, kind: "success" });
      setAberta(false);
      aprovada();
      await proposta.refetch();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível aprovar.");
    } finally {
      setGravando(false);
    }
  }

  async function descartar() {
    setErro(null);
    try {
      await apiRequest(`/automations/${id}/itens/proposta`, { method: "DELETE", token });
      toast({ title: "Tabela da automação descartada", kind: "info" });
      setAberta(false);
      await proposta.refetch();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível descartar.");
    }
  }

  const resumo = [dados.novos.length && `${dados.novos.length} novo(s)`, dados.alterados.length && `${dados.alterados.length} alterado(s)`,
    dados.erros.length && `${dados.erros.length} com erro`].filter(Boolean).join(", ");
  return (
    <>
      <div role="status" data-testid="proposta-da-automacao"
        className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary/30 bg-primary/5 px-5 py-4">
        <p className="flex items-start gap-3">
          <Inbox className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
          <span><span className="font-semibold">A automação mandou o cadastro de {plural} dela</span> ({relativo(dados.recebida_em)}): {resumo}.
            Nada muda aqui até alguém aprovar.</span>
        </p>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => void descartar()}>Descartar</Button>
          <Button onClick={() => setAberta(true)}>Ver e aprovar</Button>
        </div>
      </div>
      <Modal open={aberta} onClose={() => setAberta(false)} title={`Cadastro de ${plural} da automação`} className="max-w-2xl"
        description={`Escolha o que entra no cadastro do Portal. ${dados.iguais} já igual(is).`}
        footer={<>
          <Button variant="ghost" onClick={() => void descartar()}>Descartar tudo</Button>
          <Button onClick={() => void aprovar()} disabled={escolhidos.size === 0 || gravando}>
            {gravando ? "Gravando…" : `Aprovar ${escolhidos.size}`}
          </Button>
        </>}>
        <div className="space-y-4" data-testid="proposta-detalhe">
          {([["Novos", dados.novos], ["Alterados", dados.alterados]] as const).filter(([, l]) => l.length > 0).map(([titulo, lista]) => (
            <section key={titulo} className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">{titulo} ({lista.length})</h3>
                <button className="text-sm font-medium text-primary hover:underline" onClick={() => setEscolhidos((atual) => {
                  const novo = new Set(atual);
                  const todos = lista.every((l) => novo.has(l.chave));
                  lista.forEach((l) => (todos ? novo.delete(l.chave) : novo.add(l.chave)));
                  return novo;
                })}>{lista.every((l) => escolhidos.has(l.chave)) ? "Desmarcar todos" : "Marcar todos"}</button>
              </div>
              <ul className="max-h-56 divide-y divide-border overflow-y-auto rounded-lg border border-border">
                {lista.map((l) => (
                  <li key={l.chave}>
                    <label className="flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-muted">
                      <input type="checkbox" className="h-4 w-4 accent-[hsl(var(--primary))]" checked={escolhidos.has(l.chave)}
                        onChange={() => alternar(l.chave)} aria-label={`Escolher ${l.rotulo}`} />
                      <span className="tabular w-16 shrink-0 text-muted-foreground">{l.chave}</span>
                      <span className="truncate">{l.rotulo}</span>
                      {"mudancas" in l && <span className="ml-auto truncate text-xs text-muted-foreground">{l.mudancas.map(mudanca).join(", ")}</span>}
                    </label>
                  </li>
                ))}
              </ul>
            </section>
          ))}
          {dados.erros.length > 0 && (
            <section className="space-y-2">
              <h3 className="font-semibold text-destructive">Com erro ({dados.erros.length}): não entram</h3>
              <ul className="max-h-40 space-y-1 overflow-y-auto rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
                {dados.erros.map((e, i) => <li key={i}>{e.chave || `linha ${e.linha}`}: {Object.entries(e.campos).map(([k, v]) => `${k}: ${v}`).join("; ")}</li>)}
              </ul>
            </section>
          )}
          {erro && <p role="alert" className="text-sm text-destructive">{erro}</p>}
        </div>
      </Modal>
    </>
  );
}
