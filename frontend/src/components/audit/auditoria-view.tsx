"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Search, X } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { TIPOS, frase, iniciais, nomeDaTela, nomeDoRecurso, quem, type EventoDeAuditoria } from "@/lib/auditoria";
import { redactSensitiveData } from "@/lib/governance-utils";
import { cn } from "@/lib/utils";
import { JsonDiff } from "@/components/shared/json-diff";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";

type Pagina = { eventos: EventoDeAuditoria[]; cursor: string | null };
type Grupo = { chave: string; total: number; ultimo: string | null; nome?: string | null; email?: string | null; tipo_de_ator?: string };
type Pessoa = { id: string; nome: string; email: string | null };
type Agrupar = "dia" | "usuario" | "acao";

const PERIODOS = [{ dias: 1, rotulo: "Hoje" }, { dias: 7, rotulo: "7 dias" }, { dias: 30, rotulo: "30 dias" }, { dias: 0, rotulo: "Tudo" }];
const AGRUPAR: Array<{ valor: Agrupar; rotulo: string }> = [{ valor: "dia", rotulo: "Dia" }, { valor: "usuario", rotulo: "Pessoa" }, { valor: "acao", rotulo: "Ação" }];
const COR_DO_TIPO: Record<string, string> = {
  alteracao: "bg-primary", acesso: "bg-info", execucao: "bg-success", sistema: "bg-muted-foreground",
};
const NOME_DO_TIPO: Record<string, string> = { alteracao: "Alteração", acesso: "Acesso", execucao: "Execução", sistema: "Sistema" };

const chave = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
function hora(iso: string | null) {
  return iso ? new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—";
}
function dataLonga(iso: string) {
  const d = new Date(`${iso}T12:00:00`);
  const dif = Math.round((new Date(chave(new Date()) + "T12:00:00").getTime() - d.getTime()) / 86_400_000);
  if (dif === 0) return "Hoje";
  if (dif === 1) return "Ontem";
  const t = d.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
  return t.charAt(0).toUpperCase() + t.slice(1);
}

/**
 * Auditoria como linha do tempo (12/11/2026): tudo o que acontece no Portal, agrupado por dia,
 * por pessoa ou por ação. Clique num evento para ver ao lado o que mudou, o que a mesma ação fez,
 * a linha do tempo da pessoa e o histórico do item. Clique no nome de alguém para ver só essa pessoa.
 */
export function AuditoriaView() {
  const router = useRouter();
  const pathname = usePathname();
  const url = useSearchParams();
  const { token } = useAuth();
  const dias = Number(url.get("dias") ?? 7);
  const usuario = url.get("usuario") ?? "";
  const tipo = url.get("tipo") ?? "";
  const acao = url.get("acao") ?? "";
  const agrupar = (["dia", "usuario", "acao"] as const).find((a) => a === url.get("por")) ?? "dia";
  const [busca, setBusca] = useState(url.get("busca") ?? "");
  const [selecionado, setSelecionado] = useState<EventoDeAuditoria | null>(null);
  const [mais, setMais] = useState<EventoDeAuditoria[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);

  function mudar(campos: Record<string, string | number | null>) {
    const p = new URLSearchParams(url.toString());
    for (const [k, v] of Object.entries(campos)) {
      if (v === null || v === "") p.delete(k);
      else p.set(k, String(v));
    }
    router.replace(p.size ? `${pathname}?${p}` : pathname);
  }
  useEffect(() => {
    const t = setTimeout(() => { if ((url.get("busca") ?? "") !== busca.trim()) mudar({ busca: busca.trim() || null }); }, 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busca]);

  const filtros = new URLSearchParams();
  if (dias) {
    const de = new Date();
    de.setDate(de.getDate() - (dias - 1));
    filtros.set("de", chave(de));
    filtros.set("ate", chave(new Date()));
  }
  if (usuario) filtros.set("usuario", usuario);
  if (tipo) filtros.set("tipo", tipo);
  if (acao) filtros.set("acao", acao);
  if (url.get("busca")) filtros.set("busca", url.get("busca")!);
  const pagina = useApi<Pagina>(`/governance/auditoria/eventos?${filtros}&limite=80`, { pollMs: 30000 });
  const grupos = useApi<{ grupos: Grupo[] }>(`/governance/auditoria/grupos?por=${agrupar}&${filtros}`, { pollMs: 30000 });
  const pessoas = useApi<{ pessoas: Pessoa[] }>("/governance/auditoria/pessoas");

  useEffect(() => { setMais([]); setCursor(pagina.data?.cursor ?? null); }, [pagina.data]);
  const eventos = useMemo(() => [...(pagina.data?.eventos ?? []), ...mais], [pagina.data, mais]);

  async function carregarMais() {
    if (!cursor || !token) return;
    const p = new URLSearchParams(filtros);
    p.set("antes", cursor);
    const r = await apiRequest<Pagina>(`/governance/auditoria/eventos?${p}&limite=80`, { token });
    setMais((m) => [...m, ...r.eventos]);
    setCursor(r.cursor);
  }

  // Agrupa a linha do tempo pelo que a pessoa escolheu.
  const blocos = useMemo(() => {
    const mapa = new Map<string, EventoDeAuditoria[]>();
    for (const e of eventos) {
      const k = agrupar === "dia" ? (e.quando ? chave(new Date(e.quando)) : "-") : agrupar === "usuario" ? (e.ator_id ?? "-") : e.acao;
      mapa.set(k, [...(mapa.get(k) ?? []), e]);
    }
    return [...mapa.entries()];
  }, [eventos, agrupar]);
  const totalDe = (k: string) => grupos.data?.grupos.find((g) => g.chave === k)?.total;
  const tituloDoBloco = (k: string, lista: EventoDeAuditoria[]) => {
    if (agrupar === "dia") return k === "-" ? "Sem data" : dataLonga(k);
    if (agrupar === "usuario") return quem(lista[0]);
    const f = frase(lista[0]);
    return f.verbo.charAt(0).toUpperCase() + f.verbo.slice(1);
  };
  const pessoaFiltrada = pessoas.data?.pessoas.find((p) => p.id === usuario);
  const nomes = useMemo(() => Object.fromEntries((pessoas.data?.pessoas ?? []).map((p) => [p.id, p.nome])), [pessoas.data]);
  const chip = (ativo: boolean) => cn("rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
    ativo ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground");

  return (
    <div className="space-y-6" data-testid="auditoria">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex rounded-lg border border-border bg-card p-1" role="group" aria-label="Período">
          {PERIODOS.map((p) => <button key={p.rotulo} onClick={() => mudar({ dias: p.dias === 7 ? null : p.dias })} aria-pressed={dias === p.dias} className={chip(dias === p.dias)}>{p.rotulo}</button>)}
        </div>
        <div className="flex rounded-lg border border-border bg-card p-1" role="group" aria-label="Tipo">
          {TIPOS.map((t) => <button key={t.rotulo} onClick={() => mudar({ tipo: t.valor || null })} aria-pressed={tipo === t.valor} className={chip(tipo === t.valor)}>{t.rotulo}</button>)}
        </div>
        <select value={usuario} onChange={(e) => mudar({ usuario: e.target.value || null })} aria-label="Pessoa"
          className="h-11 min-w-[13rem] rounded-lg border border-input bg-card px-3 text-sm">
          <option value="">Todas as pessoas</option>
          {(pessoas.data?.pessoas ?? []).map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
        </select>
        <label className="relative min-w-[14rem] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
          <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar ação, item ou recurso"
            className="h-11 w-full rounded-lg border border-input bg-card pl-11 pr-3" aria-label="Buscar na auditoria" />
        </label>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          Agrupar por
          <div className="flex rounded-lg border border-border bg-card p-1" role="group" aria-label="Agrupar por">
            {AGRUPAR.map((a) => <button key={a.valor} onClick={() => mudar({ por: a.valor === "dia" ? null : a.valor })} aria-pressed={agrupar === a.valor} className={chip(agrupar === a.valor)}>{a.rotulo}</button>)}
          </div>
        </div>
      </div>

      {(usuario || acao) && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {usuario && (
            <span className="flex items-center gap-2 rounded-full bg-primary/10 py-1 pl-3 pr-1 text-primary" data-testid="filtro-pessoa">
              Linha do tempo de <strong>{pessoaFiltrada?.nome ?? `Usuário ${usuario}`}</strong>
              <button onClick={() => mudar({ usuario: null })} aria-label="Tirar o filtro de pessoa" className="rounded-full p-1 hover:bg-primary/15"><X className="h-3.5 w-3.5" /></button>
            </span>
          )}
          {acao && (
            <span className="flex items-center gap-2 rounded-full bg-primary/10 py-1 pl-3 pr-1 text-primary">
              Só a ação <strong>{acao}</strong>
              <button onClick={() => mudar({ acao: null })} aria-label="Tirar o filtro de ação" className="rounded-full p-1 hover:bg-primary/15"><X className="h-3.5 w-3.5" /></button>
            </span>
          )}
        </div>
      )}

      <div className={cn("grid gap-6", selecionado && "xl:grid-cols-[minmax(0,1fr)_34rem]")}>
        <div className="min-w-0 space-y-6">
          {pagina.error && !pagina.data ? (
            <ErrorState message={pagina.error} onRetry={() => void pagina.refetch()} />
          ) : !pagina.data ? (
            <div className="skeleton h-96 rounded-xl" />
          ) : eventos.length === 0 ? (
            <p className="rounded-xl border border-dashed border-border px-6 py-12 text-center text-muted-foreground">Nada registrado com esses filtros.</p>
          ) : blocos.map(([k, lista]) => (
            <section key={k} className="space-y-2" data-grupo-auditoria={k}>
              <h2 className="flex items-baseline gap-3 text-lg font-semibold text-titulo">
                {tituloDoBloco(k, lista)}
                <span className="text-sm font-normal text-muted-foreground">{totalDe(k) ?? lista.length} evento(s)</span>
                {agrupar === "usuario" && k !== "-" && lista[0].tipo_de_ator === "user" && k !== usuario && (
                  <button onClick={() => mudar({ usuario: k, por: null })} className="text-sm font-medium text-primary hover:underline">ver só esta pessoa</button>
                )}
                {agrupar === "acao" && k !== acao && (
                  <button onClick={() => mudar({ acao: k, por: null })} className="text-sm font-medium text-primary hover:underline">ver só esta ação</button>
                )}
              </h2>
              <ol className="relative space-y-0 border-l-2 border-border pl-6">
                {lista.map((e) => (
                  <LinhaDoEvento key={e.id} e={e} nomes={nomes} ativo={selecionado?.id === e.id} mostrarData={agrupar !== "dia"}
                    abrir={() => setSelecionado(e)} verPessoa={(id) => mudar({ usuario: id, por: null })} />
                ))}
              </ol>
            </section>
          ))}
          {cursor && eventos.length > 0 && <div className="text-center"><Button variant="outline" onClick={() => void carregarMais()}>Carregar mais</Button></div>}
        </div>

        {selecionado && (
          <Detalhe e={selecionado} nomes={nomes} fechar={() => setSelecionado(null)} abrir={setSelecionado}
            verPessoa={(id) => mudar({ usuario: id, por: null })} />
        )}
      </div>
    </div>
  );
}

function LinhaDoEvento({ e, nomes, ativo, mostrarData, abrir, verPessoa }: {
  e: EventoDeAuditoria; nomes: Record<string, string>; ativo: boolean; mostrarData: boolean; abrir: () => void; verPessoa: (id: string) => void;
}) {
  const f = frase(e, nomes);
  const nome = quem(e);
  const falhou = typeof e.detalhes.status === "number" && (e.detalhes.status as number) >= 400 || e.acao === "login_failed";
  return (
    <li className="relative" data-evento={e.acao}>
      <span className={cn("absolute -left-[1.95rem] top-4 h-3 w-3 rounded-full ring-4 ring-background", falhou ? "bg-destructive" : COR_DO_TIPO[e.tipo])} />
      <div role="button" tabIndex={0} onClick={abrir} onKeyDown={(ev) => { if (ev.key === "Enter") abrir(); }}
        className={cn("flex cursor-pointer items-start gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-muted",
          ativo && "bg-primary/10 ring-1 ring-primary/40")}>
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-bold text-secondary-foreground">{iniciais(nome)}</span>
        <div className="min-w-0 flex-1">
          <p className="text-base leading-snug">
            {e.tipo_de_ator === "user" && e.ator_id ? (
              <button onClick={(ev) => { ev.stopPropagation(); verPessoa(e.ator_id!); }} className="font-semibold text-titulo hover:underline"
                title="Ver a linha do tempo desta pessoa">{nome}</button>
            ) : <span className="font-semibold text-titulo">{nome}</span>}
            {" "}<span className={cn(falhou && "text-destructive")}>{f.verbo}</span>
            {f.objeto && <> <span className="font-medium text-titulo">{f.objeto}</span></>}
          </p>
          <p className="text-sm text-muted-foreground">
            {mostrarData && e.quando ? `${new Date(e.quando).toLocaleDateString("pt-BR")} · ` : ""}{hora(e.quando)}
            {" · "}{NOME_DO_TIPO[e.tipo]}
            {typeof e.detalhes.status === "number" && <> · resposta {String(e.detalhes.status)}</>}
          </p>
        </div>
      </div>
    </li>
  );
}

/** O painel ao lado: o que mudou, a mesma ação, a linha do tempo da pessoa e o histórico do item. */
function Detalhe({ e, nomes, fechar, abrir, verPessoa }: {
  e: EventoDeAuditoria; nomes: Record<string, string>; fechar: () => void; abrir: (e: EventoDeAuditoria) => void; verPessoa: (id: string) => void;
}) {
  const [aba, setAba] = useState<"mudou" | "acao" | "pessoa" | "item">("mudou");
  useEffect(() => setAba("mudou"), [e.id]);
  const dia = e.quando ? new Date(e.quando) : new Date();
  const de = new Date(dia); de.setDate(de.getDate() - 1);
  const ate = new Date(dia); ate.setDate(ate.getDate() + 1);
  const caminho = aba === "acao" && e.correlacao ? `/governance/auditoria/eventos?correlacao=${encodeURIComponent(e.correlacao)}&limite=50`
    : aba === "pessoa" && e.ator_id ? `/governance/auditoria/eventos?usuario=${encodeURIComponent(e.ator_id)}&de=${chave(de)}&ate=${chave(ate)}&limite=100`
    : aba === "item" ? `/governance/auditoria/eventos?recurso_tipo=${encodeURIComponent(e.recurso_tipo)}&recurso_id=${encodeURIComponent(e.recurso_id)}&tecnicos=true&limite=100`
    : null;
  const relacionados = useApi<Pagina>(caminho);
  const f = frase(e, nomes);
  const curto = (d: Date) => d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  const doItem = e.acao === "tela.aberta" ? `a tela ${nomeDaTela(e.recurso_id)}`
    : `${nomeDoRecurso(e.recurso_tipo)} ${e.recurso_tipo === "user" && nomes[e.recurso_id] ? nomes[e.recurso_id] : e.recurso_id}`;
  const abas = [
    { id: "mudou" as const, rotulo: "O que foi", explica: "" },
    { id: "acao" as const, rotulo: "Na mesma ação", some: !e.correlacao,
      explica: "Tudo o que este mesmo clique fez no Portal, incluindo os registros técnicos." },
    { id: "pessoa" as const, rotulo: e.tipo_de_ator === "user" ? "Da pessoa" : "Do autor", some: !e.ator_id,
      explica: `Tudo o que ${quem(e)} fez de ${curto(de)} a ${curto(ate)}.` },
    { id: "item" as const, rotulo: "Do item", some: !e.recurso_id || e.recurso_id === "-",
      explica: `Tudo o que já aconteceu com ${doItem}.` },
  ].filter((a) => !a.some);
  const explica = abas.find((a) => a.id === aba)?.explica;

  return (
    <aside className="h-fit space-y-4 rounded-xl border border-border bg-card p-5 shadow-sm xl:sticky xl:top-24" data-testid="detalhe-auditoria">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-muted-foreground">{e.quando ? new Date(e.quando).toLocaleString("pt-BR") : ""}</p>
          <p className="text-lg font-semibold leading-snug text-titulo">{quem(e)} {f.verbo}{f.objeto ? ` ${f.objeto}` : ""}</p>
        </div>
        <button onClick={fechar} aria-label="Fechar o detalhe" className="rounded-md p-1 text-muted-foreground hover:bg-accent"><X className="h-4 w-4" /></button>
      </div>
      <div className="flex flex-wrap gap-1 border-b border-border" role="tablist">
        {abas.map((a) => (
          <button key={a.id} role="tab" aria-selected={aba === a.id} onClick={() => setAba(a.id)}
            className={cn("-mb-px border-b-2 px-3 py-2 text-sm font-medium", aba === a.id ? "border-primary text-titulo" : "border-transparent text-muted-foreground hover:text-foreground")}>
            {a.rotulo}
          </button>
        ))}
      </div>

      {aba === "mudou" ? (
        <div className="space-y-4">
          <dl className="grid grid-cols-[8rem_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-sm">
            <dt className="text-muted-foreground">Quem</dt>
            <dd>{e.tipo_de_ator === "user" && e.ator_id
              ? <button onClick={() => verPessoa(e.ator_id!)} className="font-medium text-primary hover:underline">{quem(e)}</button> : quem(e)}
              {e.ator_email && <span className="text-muted-foreground"> · {e.ator_email}</span>}</dd>
            <dt className="text-muted-foreground">Ação</dt><dd className="break-all font-mono text-xs leading-6">{e.acao}</dd>
            <dt className="text-muted-foreground">Recurso</dt>
            <dd className="break-all">{e.acao === "tela.aberta" ? nomeDaTela(e.recurso_id) : `${nomeDoRecurso(e.recurso_tipo)} · ${e.recurso_id}`}</dd>
            {typeof e.detalhes.rota === "string" && <><dt className="text-muted-foreground">Endereço</dt><dd className="break-all font-mono text-xs leading-6">{String(e.detalhes.metodo)} {String(e.detalhes.caminho)}</dd></>}
            {typeof e.detalhes.status === "number" && <><dt className="text-muted-foreground">Resposta</dt><dd>{String(e.detalhes.status)} em {String(e.detalhes.duracao_ms)} ms</dd></>}
            {e.ip && <><dt className="text-muted-foreground">De onde</dt><dd>{e.ip}</dd></>}
          </dl>
          {e.antes && e.depois ? (
            <div>
              <p className="mb-2 text-sm font-semibold text-titulo">O que mudou</p>
              <JsonDiff before={redactSensitiveData(e.antes)} after={redactSensitiveData(e.depois)} />
            </div>
          ) : e.depois || e.antes ? (
            <div>
              <p className="mb-2 text-sm font-semibold text-titulo">{e.depois ? "Criado com" : "Como estava antes de apagar"}</p>
              <Campos valor={redactSensitiveData(e.depois ?? e.antes)} />
            </div>
          ) : Object.keys(e.detalhes).length > 0 && !e.acao.startsWith("api.") ? (
            <pre className="max-h-64 overflow-auto rounded-lg bg-muted p-3 text-xs">{JSON.stringify(redactSensitiveData(e.detalhes), null, 2)}</pre>
          ) : null}
        </div>
      ) : !relacionados.data ? (
        <div className="skeleton h-40 rounded-lg" />
      ) : relacionados.data.eventos.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nada mais registrado.</p>
      ) : (
        <div className="space-y-2">
          {explica && <p className="text-sm text-muted-foreground">{explica}</p>}
          <Relacionados lista={relacionados.data.eventos} atual={e.id} nomes={nomes} semAutor={aba === "pessoa"} abrir={abrir} />
        </div>
      )}
    </aside>
  );
}

/** Os campos de algo criado (ou apagado), um por linha, sem comparar com "nada". */
function Campos({ valor }: { valor: unknown }) {
  if (!valor || typeof valor !== "object" || Array.isArray(valor)) {
    return <pre className="max-h-64 overflow-auto rounded-lg bg-muted p-3 text-xs">{JSON.stringify(valor, null, 2)}</pre>;
  }
  return (
    <dl className="grid grid-cols-[10rem_minmax(0,1fr)] gap-x-3 gap-y-1 rounded-lg border border-border p-3 text-sm" data-testid="campos-criados">
      {Object.entries(valor as Record<string, unknown>).map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="truncate text-muted-foreground">{k}</dt>
          <dd className="break-all">{typeof v === "object" && v !== null ? JSON.stringify(v) : String(v ?? "—")}</dd>
        </div>
      ))}
    </dl>
  );
}

function Relacionados({ lista, atual, nomes, semAutor, abrir }: {
  lista: EventoDeAuditoria[]; atual: string; nomes: Record<string, string>; semAutor: boolean; abrir: (e: EventoDeAuditoria) => void;
}) {
  return (
    <ol className="max-h-[60vh] space-y-1 overflow-y-auto" data-testid="relacionados">
      {lista.map((r) => {
        const fr = frase(r, nomes);
        return (
          <li key={r.id}>
            <button onClick={() => abrir(r)} className={cn("w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted", r.id === atual && "bg-primary/10 font-semibold")}>
              <span className="tabular-nums text-muted-foreground">
                {r.quando ? new Date(r.quando).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—"}
              </span>{" "}
              {!semAutor && <span className="font-medium">{quem(r)} </span>}{fr.verbo}{fr.objeto ? ` ${fr.objeto}` : ""}
            </button>
          </li>
        );
      })}
    </ol>
  );
}
