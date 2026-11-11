"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CornerDownRight, Pencil, Play, Search, SlidersHorizontal, Upload } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { API_BASE_URL } from "@/lib/constants";
import { apiRequest } from "@/lib/api";
import { ErroComCampos, enviar, mostrarValor, valoresIniciais, type Formulario } from "@/lib/campos";
import { cn } from "@/lib/utils";
import { ExecutarAutomacao } from "@/components/automacao/executar-automacao";
import { PropostaDaAutomacao } from "@/components/itens/proposta-da-automacao";
import { CampoDeEntrada } from "@/components/campos/campo-de-entrada";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";

type Definicao = { nome: string; chave: string; grupo: string | null; afetam_trabalho: string[] };
type Item = { chave: string; rotulo: string; grupo: string | null; atributos: Record<string, unknown>; ativo: boolean };
type Lista = { definicao: Definicao | null; pode_editar: boolean; contagem: { ativos: number; total: number }; itens: Item[]; proximo: number | null };
type Previa = { novos: Item[]; alterados: Array<Item & { mudancas: string[] }>; iguais: number; erros: Array<{ linha: number | null; chave: string; campos: Record<string, string> }> };

export function ItensDaAutomacao({ id, embutido = false, nome = "Automação" }: { id: string; embutido?: boolean; nome?: string }) {
  const [busca, setBusca] = useState("");
  const [aplicada, setAplicada] = useState("");
  const [filtros, setFiltros] = useState(false);
  const [ativos, setAtivos] = useState<"" | "true" | "false">("true");
  const [marcados, setMarcados] = useState<Set<string>>(new Set());
  const [editando, setEditando] = useState<Item | null>(null);
  const [importando, setImportando] = useState(false);
  const [executando, setExecutando] = useState(false);
  const form = useApi<Formulario>(`/automations/${id}/formulario`);
  const colunas = form.data?.colunas ?? [];

  useEffect(() => {
    const t = setTimeout(() => setAplicada(busca.trim()), 300);
    return () => clearTimeout(t);
  }, [busca]);

  const params = new URLSearchParams({ limite: "500" });
  if (aplicada) params.set("busca", aplicada);
  if (ativos) params.set("ativos", ativos);
  const lista = useApi<Lista>(`/automations/${id}/itens?${params}`);
  const dados = lista.data;
  const nomeItem = dados?.definicao?.nome ?? "Item";

  function alternar(chave: string) {
    setMarcados((m) => {
      const novo = new Set(m);
      if (novo.has(chave)) novo.delete(chave);
      else novo.add(chave);
      return novo;
    });
  }

  return (
    <div className="space-y-6 pb-28">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          {!embutido && <p className="eyebrow"><Link href={`/automations/${id}`} className="hover:underline">Automação</Link></p>}
          {embutido
            ? <h2 className="titulo-condensado text-2xl">{nomeItem === "Item" ? "Itens" : `${nomeItem}s`}</h2>
            : <h1 className="titulo-condensado text-4xl">{nomeItem === "Item" ? "Itens" : `${nomeItem}s`}</h1>}
          {dados && <p className="mt-1 text-muted-foreground">{dados.contagem.ativos} ativos de {dados.contagem.total}</p>}
        </div>
        {dados?.pode_editar && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setImportando(true)}><Upload className="h-4 w-4" /> Importar</Button>
            <Button onClick={() => setEditando({ chave: "", rotulo: "", grupo: null, atributos: {}, ativo: true })}>Novo</Button>
          </div>
        )}
      </div>

      {dados?.pode_editar && <PropostaDaAutomacao id={id} nomeItem={nomeItem} aprovada={() => void lista.refetch()} />}

      <div className="flex flex-wrap gap-3">
        <label className="relative min-w-[16rem] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
          <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder={`Buscar ${nomeItem.toLowerCase()} por código ou nome`}
            className="h-12 w-full rounded-lg border border-input bg-card pl-11 pr-3 text-base" aria-label="Buscar" />
        </label>
        <Button variant="outline" className="h-12" onClick={() => setFiltros((v) => !v)} aria-expanded={filtros}>
          <SlidersHorizontal className="h-4 w-4" /> Filtros
        </Button>
      </div>
      {filtros && (
        <div className="flex gap-2 rounded-lg border border-border bg-card p-3">
          {([["true", "Ativos"], ["false", "Inativos"], ["", "Todos"]] as const).map(([v, r]) => (
            <button key={r} onClick={() => setAtivos(v)} aria-pressed={ativos === v}
              className={cn("rounded-md px-3 py-1.5 text-sm font-medium", ativos === v ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted")}>
              {r}
            </button>
          ))}
        </div>
      )}

      {lista.error && !dados ? (
        <ErrorState message={lista.error} onRetry={() => void lista.refetch()} />
      ) : !dados ? (
        <div className="skeleton h-64 w-full rounded-xl" />
      ) : dados.itens.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border px-6 py-12 text-center text-muted-foreground">
          {dados.contagem.total === 0 ? "Nenhum item cadastrado. Importe o cadastro ou crie o primeiro." : "Nada encontrado com essa busca."}
        </p>
      ) : (
        <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-sm" data-testid="itens">
          {dados.itens.map((item) => (
            <li key={item.chave} className={cn("flex items-center gap-4 px-5 py-3.5", !item.ativo && "opacity-60")}>
              <input type="checkbox" className="h-5 w-5 accent-[hsl(var(--primary))]" checked={marcados.has(item.chave)}
                onChange={() => alternar(item.chave)} aria-label={`Escolher ${item.rotulo}`} disabled={!item.ativo} />
              {item.grupo && <CornerDownRight className="h-4 w-4 shrink-0 text-muted-foreground" />}
              <div className="min-w-0 flex-1">
                <p className="truncate text-base font-medium text-titulo">
                  <span className="tabular mr-2 text-muted-foreground">{item.chave}</span>{item.rotulo}
                </p>
                {item.grupo && <p className="text-sm text-muted-foreground">filial de {item.grupo}</p>}
              </div>
              {colunas.filter((c) => c.afeta_trabalho && item.atributos[c.chave] === true).map((c) => (
                <span key={c.chave} className="hidden rounded-md bg-secondary px-2 py-0.5 text-sm text-secondary-foreground sm:inline">{c.rotulo}</span>
              ))}
              {dados.pode_editar && (
                <Button variant="ghost" size="icon" onClick={() => setEditando(item)} aria-label={`Editar ${item.rotulo}`}>
                  <Pencil className="h-4 w-4" />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      {marcados.size > 0 && (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card/95 px-6 py-4 shadow-[0_-8px_24px_rgba(20,30,55,0.12)] backdrop-blur lg:left-[16.5rem]">
          <div className="mx-auto flex max-w-[110rem] flex-wrap items-center gap-4">
            <p className="text-base font-semibold text-titulo">{marcados.size} escolhido(s)</p>
            <div className="ml-auto flex gap-2">
              <Button variant="ghost" onClick={() => setMarcados(new Set())}>Cancelar</Button>
              <Button onClick={() => setExecutando(true)}><Play className="h-4 w-4" /> Executar</Button>
            </div>
          </div>
        </div>
      )}
      <ExecutarAutomacao id={id} nome={nome} aberto={executando} fechar={() => setExecutando(false)} preEscolhidos={[...marcados]}
        pedido={() => setMarcados(new Set())} />
      {editando && dados && form.data && (
        <Editar id={id} item={editando} formulario={form.data} fechar={() => setEditando(null)} salvo={() => void lista.refetch()} />
      )}
      <Importar id={id} aberto={importando} fechar={() => setImportando(false)} importado={() => void lista.refetch()} />
    </div>
  );
}

function Editar({ id, item, formulario, fechar, salvo }: { id: string; item: Item; formulario: Formulario; fechar: () => void; salvo: () => void }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const novo = !item.chave;
  const [dados, setDados] = useState<Item>(novo ? { ...item, atributos: valoresIniciais(formulario.colunas) } : item);
  const [erros, setErros] = useState<Record<string, string>>({});
  const [geral, setGeral] = useState<string | null>(null);
  const nomeItem = formulario.item?.nome ?? "item";

  async function salvar() {
    setErros({});
    setGeral(null);
    try {
      await enviar(novo ? `/automations/${id}/itens` : `/automations/${id}/itens/${encodeURIComponent(item.chave)}`,
        novo ? "POST" : "PUT", dados, token);
      toast({ title: "Salvo", kind: "success" });
      salvo();
      fechar();
    } catch (err) {
      if (err instanceof ErroComCampos) {
        setErros(Object.fromEntries(Object.entries(err.campos).map(([k, v]) => [k.replace(/^atributos\./, ""), v])));
      }
      setGeral(err instanceof Error ? err.message : "Não foi possível salvar");
    }
  }

  const caixa = "h-11 w-full rounded-md border border-input bg-background px-3";
  const extras = Object.keys(dados.atributos).filter((k) => !formulario.colunas.some((c) => c.chave === k));
  return (
    <Modal open onClose={fechar} title={novo ? `Novo ${nomeItem.toLowerCase()}` : dados.rotulo} className="max-w-2xl"
      footer={<><Button variant="ghost" onClick={fechar}>Cancelar</Button><Button onClick={() => void salvar()}>Salvar</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2" data-testid="editar-item">
        <label className="space-y-1.5"><span className="text-sm font-medium">Código</span>
          <input className={caixa} value={dados.chave} disabled={!novo} aria-label="Código" onChange={(e) => setDados({ ...dados, chave: e.target.value })} />
          {erros.chave && <span className="block text-sm text-destructive">{erros.chave}</span>}</label>
        {formulario.item?.grupo && (
          <label className="space-y-1.5"><span className="text-sm font-medium">Grupo (matriz)</span>
            <input className={caixa} value={dados.grupo ?? ""} aria-label="Grupo" onChange={(e) => setDados({ ...dados, grupo: e.target.value || null })} />
            {erros.grupo && <span className="block text-sm text-destructive">{erros.grupo}</span>}</label>
        )}
        <label className="space-y-1.5 sm:col-span-2"><span className="text-sm font-medium">Nome</span>
          <input className={caixa} value={dados.rotulo} aria-label="Nome" onChange={(e) => setDados({ ...dados, rotulo: e.target.value })} />
          {erros.rotulo && <span className="block text-sm text-destructive">{erros.rotulo}</span>}</label>
        {formulario.colunas.map((c) => (
          <CampoDeEntrada key={c.chave} campo={c} valor={dados.atributos[c.chave]} erro={erros[c.chave]}
            mudar={(v) => setDados({ ...dados, atributos: { ...dados.atributos, [c.chave]: v } })} />
        ))}
        {extras.length > 0 && (
          <p className="text-sm text-muted-foreground sm:col-span-2">
            Também guardado (sem coluna): {extras.map((k) => `${k}: ${mostrarValor(undefined, dados.atributos[k])}`).join(" · ")}
          </p>
        )}
        {!novo && (
          <label className="flex items-center gap-2 sm:col-span-2">
            <input type="checkbox" className="h-5 w-5" checked={dados.ativo} onChange={(e) => setDados({ ...dados, ativo: e.target.checked })} />
            <span>Ativo (inativo não aparece para executar)</span>
          </label>
        )}
      </div>
      {geral && <p role="alert" className="mt-4 text-sm text-destructive">{geral}</p>}
    </Modal>
  );
}

function Importar({ id, aberto, fechar, importado }: { id: string; aberto: boolean; fechar: () => void; importado: () => void }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [previa, setPrevia] = useState<Previa | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [lendo, setLendo] = useState(false);

  async function ler(arquivo: File) {
    setLendo(true);
    setErro(null);
    try {
      const corpo = new FormData();
      corpo.append("arquivo", arquivo);
      const resposta = await fetch(`${API_BASE_URL}/automations/${id}/itens/importar/previa`, {
        method: "POST", body: corpo, headers: token ? { Authorization: `Bearer ${token}` } : {} });
      const json = await resposta.json();
      if (!resposta.ok) throw new Error(json?.error?.message ?? "Arquivo recusado");
      setPrevia(json);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível ler o arquivo");
    } finally {
      setLendo(false);
    }
  }

  async function gravar() {
    if (!previa) return;
    try {
      const r = await apiRequest<{ criados: number; alterados: number }>(`/automations/${id}/itens/importar`, {
        method: "POST", token, body: JSON.stringify({ itens: [...previa.novos, ...previa.alterados] }) });
      toast({ title: `${r.criados} criado(s), ${r.alterados} alterado(s)`, kind: "success" });
      setPrevia(null);
      importado();
      fechar();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível gravar");
    }
  }

  const mudancas = previa ? previa.novos.length + previa.alterados.length : 0;
  return (
    <Modal open={aberto} onClose={() => { setPrevia(null); fechar(); }} title="Importar cadastro" className="max-w-2xl"
      description="Escolha o empresas.db da Integração Contábil (pasta dados). Nada é gravado antes de você confirmar."
      footer={previa ? <><Button variant="ghost" onClick={() => setPrevia(null)}>Trocar arquivo</Button>
        <Button onClick={() => void gravar()} disabled={mudancas === 0 || previa.erros.length > 0}>Gravar {mudancas}</Button></> : undefined}>
      {!previa ? (
        <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-border px-6 py-10 text-center hover:bg-muted">
          <Upload className="h-8 w-8 text-muted-foreground" />
          <span className="font-medium">{lendo ? "Lendo…" : "Escolher empresas.db"}</span>
          <input type="file" accept=".db,.sqlite" className="sr-only" onChange={(e) => e.target.files?.[0] && void ler(e.target.files[0])} />
        </label>
      ) : (
        <div className="space-y-4">
          <dl className="grid grid-cols-3 gap-3 text-center">
            {[["Novos", previa.novos.length], ["Alterados", previa.alterados.length], ["Iguais", previa.iguais]].map(([r, v]) => (
              <div key={r as string} className="rounded-lg bg-muted px-3 py-3"><dt className="text-sm text-muted-foreground">{r}</dt><dd className="titulo-condensado text-3xl">{v}</dd></div>
            ))}
          </dl>
          {previa.alterados.length > 0 && (
            <ul className="max-h-48 space-y-1 overflow-y-auto text-sm">
              {previa.alterados.map((a) => <li key={a.chave}><span className="tabular">{a.chave}</span> {a.rotulo}: <span className="text-muted-foreground">{a.mudancas.join(", ")}</span></li>)}
            </ul>
          )}
          {previa.erros.length > 0 && (
            <ul className="space-y-1 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
              {previa.erros.map((e, i) => <li key={i}>{e.chave || `linha ${e.linha}`}: {Object.values(e.campos).join("; ")}</li>)}
            </ul>
          )}
        </div>
      )}
      {erro && <p className="mt-3 text-sm text-destructive">{erro}</p>}
    </Modal>
  );
}
