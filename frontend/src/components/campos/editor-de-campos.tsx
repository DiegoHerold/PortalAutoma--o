"use client";

import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Info, Plus, Trash2 } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { ErroComCampos, chaveDe, enviar, type Campo, type Formulario, type TipoDeCampo } from "@/lib/campos";
import { cn } from "@/lib/utils";
import { CampoDeEntrada } from "@/components/campos/campo-de-entrada";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

type Lista = "entrada" | "colunas";
type Rascunho = Campo & { novo?: boolean };

/**
 * Entradas da automação, editadas livremente no Portal (Fase 7). Desde a Fase 8 a automação
 * manda as dela ao conectar: o Portal só acrescenta, o que foi editado aqui fica, e o que ela
 * deixou de mandar fica "fora de uso". Campo novo criado aqui chega à automação no pedido; ela
 * só faz algo com ele se o código dela ler esse campo.
 */
export function EditorDeCampos({ id }: { id: string }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const form = useApi<Formulario>(`/automations/${id}/formulario`);
  const [listas, setListas] = useState<Record<Lista, Rascunho[]>>({ entrada: [], colunas: [] });
  const [erros, setErros] = useState<Record<string, string>>({});
  const [geral, setGeral] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (form.data) setListas({ entrada: form.data.entrada, colunas: form.data.colunas });
  }, [form.data]);

  if (form.error && !form.data) return <ErrorState message={form.error} onRetry={() => void form.refetch()} />;
  if (!form.data) return <div className="skeleton h-80 rounded-xl" />;
  const dados = form.data;
  const mudou = JSON.stringify({ entrada: dados.entrada.map(limpo), colunas: dados.colunas.map(limpo) }) !==
    JSON.stringify({ entrada: listas.entrada.map(limpo), colunas: listas.colunas.map(limpo) });

  function mudar(lista: Lista, i: number, campo: Partial<Rascunho>) {
    setListas((atual) => ({ ...atual, [lista]: atual[lista].map((c, j) => (j === i ? { ...c, ...campo } : c)) }));
  }
  function mover(lista: Lista, i: number, para: number) {
    setListas((atual) => {
      const nova = [...atual[lista]];
      const [c] = nova.splice(i, 1);
      nova.splice(para, 0, c);
      return { ...atual, [lista]: nova };
    });
  }
  function novo(lista: Lista) {
    setListas((atual) => ({ ...atual, [lista]: [...atual[lista], {
      chave: "", rotulo: "", tipo: "texto", obrigatorio: false, padrao: null, opcoes: [], ajuda: null, afeta_trabalho: false,
      origem: "portal", fora_de_uso: false, novo: true }] }));
  }

  async function salvar() {
    setSalvando(true);
    setErros({});
    setGeral(null);
    try {
      await enviar(`/automations/${id}/formulario`, "PUT", {
        entrada: listas.entrada.map(limpo), colunas: listas.colunas.map(limpo), versao: dados.versao }, token);
      toast({ title: "Campos salvos", kind: "success" });
      await form.refetch();
    } catch (err) {
      if (err instanceof ErroComCampos) setErros(err.campos);
      setGeral(err instanceof Error ? err.message : "Não foi possível salvar.");
    } finally {
      setSalvando(false);
    }
  }

  const nomeItem = dados.item?.nome ?? "item";
  return (
    <div className="space-y-6" data-testid="editor-de-campos">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="titulo-condensado text-2xl">Entradas da automação</h2>
          <p className="max-w-3xl text-muted-foreground">
            O que se informa ao executar e o que cada {nomeItem.toLowerCase()} guarda. {dados.origem === "manifesto"
              ? "Hoje valem os campos sugeridos pela automação; ao salvar, passam a valer os daqui."
              : "A automação manda os campos dela ao conectar; o que você muda aqui continua valendo."}
          </p>
        </div>
        {dados.pode_editar && (
          <Button onClick={() => void salvar()} disabled={!mudou || salvando}>{salvando ? "Salvando…" : "Salvar campos"}</Button>
        )}
      </div>
      <p className="flex items-start gap-2 rounded-lg border border-border bg-muted/40 p-3 text-sm text-muted-foreground">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        Um campo novo chega à automação junto com o pedido, mas só tem efeito se o código dela usar esse campo.
        Apagar uma coluna não apaga o que já está guardado nos {nomeItem.toLowerCase()}s. Campo &quot;fora de uso&quot; é
        um que a automação deixou de mandar: não é pedido ao executar.
      </p>
      {([["entrada", "Informações do pedido", "Pedidas a cada execução (ex.: competência)."],
         ["colunas", `Colunas de cada ${nomeItem.toLowerCase()}`, `Guardadas no cadastro de cada ${nomeItem.toLowerCase()} (ex.: pasta de destino).`]] as const)
        .filter(([lista]) => lista === "entrada" || dados.item)
        .map(([lista, titulo, descricao]) => (
          <section key={lista} className="space-y-3">
            <div>
              <h3 className="titulo-condensado text-xl">{titulo}</h3>
              <p className="text-sm text-muted-foreground">{descricao}</p>
            </div>
            {listas[lista].length === 0 && <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-muted-foreground">Nenhum campo.</p>}
            <ol className="space-y-3">
              {listas[lista].map((c, i) => (
                <LinhaDoCampo key={`${lista}-${i}`} campo={c} tipos={dados.tipos} pode={dados.pode_editar} coluna={lista === "colunas"}
                  erros={Object.fromEntries(Object.entries(erros).filter(([k]) => k.startsWith(`${lista}.campos[${i}]`))
                    .map(([k, v]) => [k.split(".").pop() as string, v]))}
                  mudar={(parte) => mudar(lista, i, parte)}
                  subir={i > 0 ? () => mover(lista, i, i - 1) : undefined}
                  descer={i < listas[lista].length - 1 ? () => mover(lista, i, i + 1) : undefined}
                  remover={() => setListas((atual) => ({ ...atual, [lista]: atual[lista].filter((_, j) => j !== i) }))} />
              ))}
            </ol>
            {dados.pode_editar && <Button variant="outline" onClick={() => novo(lista)}><Plus className="h-4 w-4" /> Novo campo</Button>}
          </section>
        ))}
      {geral && <p role="alert" className="text-sm text-destructive">{geral}</p>}
    </div>
  );
}

function limpo(c: Rascunho): Campo {
  // origem e fora_de_uso vão só para comparar: o Portal guarda as marcas que já tinha.
  return { chave: c.chave, rotulo: c.rotulo, tipo: c.tipo, obrigatorio: c.obrigatorio,
    padrao: c.padrao === "" ? null : c.padrao ?? null, opcoes: c.tipo === "lista" ? c.opcoes : [],
    ajuda: c.ajuda || null, afeta_trabalho: c.afeta_trabalho, origem: c.origem ?? "portal", fora_de_uso: c.fora_de_uso ?? false };
}

function LinhaDoCampo({ campo, tipos, pode, coluna, erros, mudar, subir, descer, remover }: {
  campo: Rascunho;
  tipos: Formulario["tipos"];
  pode: boolean;
  coluna: boolean;
  erros: Record<string, string>;
  mudar: (parte: Partial<Rascunho>) => void;
  subir?: () => void;
  descer?: () => void;
  remover: () => void;
}) {
  const caixa = "h-10 w-full rounded-md border border-input bg-background px-3";
  const erroDe = (k: string) => erros[k] && <span role="alert" className="block text-xs text-destructive">{erros[k]}</span>;
  return (
    <li className={cn("rounded-xl border bg-card p-4 shadow-sm", Object.keys(erros).length ? "border-destructive" : "border-border",
      campo.fora_de_uso && "opacity-70")} data-campo={campo.chave || "novo"}>
      <fieldset disabled={!pode} className="grid gap-3 md:grid-cols-[minmax(0,2fr)_minmax(0,1.3fr)_minmax(0,1.2fr)_auto] md:items-start">
        <label className="space-y-1">
          <span className="text-xs font-medium text-muted-foreground">Nome</span>
          <input className={caixa} value={campo.rotulo} aria-label="Nome do campo" placeholder="ex.: Competência"
            onChange={(e) => mudar({ rotulo: e.target.value, ...(campo.novo ? { chave: chaveDe(e.target.value) } : {}) })} />
          <span className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            <span>chave: <code>{campo.chave || "—"}</code>{!campo.novo && " (não muda)"}</span>
            {campo.origem === "automacao" && <span className="rounded bg-secondary px-1.5 py-0.5 text-secondary-foreground">da automação</span>}
            {campo.fora_de_uso && (
              <span className="rounded bg-warning/15 px-1.5 py-0.5 font-medium text-foreground" title="A automação deixou de mandar este campo: não é pedido ao executar.">fora de uso</span>
            )}
          </span>
          {erroDe("rotulo")}{erroDe("chave")}
        </label>
        <label className="space-y-1">
          <span className="text-xs font-medium text-muted-foreground">Tipo</span>
          <select className={caixa} value={campo.tipo} aria-label="Tipo do campo"
            onChange={(e) => mudar({ tipo: e.target.value as TipoDeCampo, padrao: null })}>
            {tipos.map((t) => <option key={t.tipo} value={t.tipo}>{t.rotulo}</option>)}
          </select>
          {erroDe("tipo")}
        </label>
        <div className="space-y-2 pt-5">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="h-4 w-4" checked={campo.obrigatorio} onChange={(e) => mudar({ obrigatorio: e.target.checked })} /> Obrigatório
          </label>
          {coluna && (
            <label className="flex items-center gap-2 text-sm" title="Muda o tempo do trabalho: entra na estimativa">
              <input type="checkbox" className="h-4 w-4" checked={campo.afeta_trabalho} onChange={(e) => mudar({ afeta_trabalho: e.target.checked })} /> Muda o tempo
            </label>
          )}
        </div>
        <div className="flex gap-1 pt-5">
          <Button variant="ghost" size="icon" onClick={subir} disabled={!subir} aria-label="Subir"><ArrowUp className="h-4 w-4" /></Button>
          <Button variant="ghost" size="icon" onClick={descer} disabled={!descer} aria-label="Descer"><ArrowDown className="h-4 w-4" /></Button>
          <Button variant="ghost" size="icon" onClick={remover} aria-label={`Remover ${campo.rotulo || "campo"}`}><Trash2 className="h-4 w-4 text-destructive" /></Button>
        </div>
        {campo.tipo === "lista" && (
          <label className="space-y-1 md:col-span-2">
            <span className="text-xs font-medium text-muted-foreground">Opções (uma por linha)</span>
            <textarea rows={3} className={cn(caixa, "h-auto py-2")} value={campo.opcoes.join("\n")} aria-label="Opções"
              onChange={(e) => mudar({ opcoes: e.target.value.split("\n").map((o) => o.trim()).filter(Boolean) })} />
            {erroDe("opcoes")}
          </label>
        )}
        <div className="md:col-span-2">
          {campo.tipo !== "json" && (
            <CampoDeEntrada campo={{ ...campo, rotulo: "Valor padrão", obrigatorio: false, ajuda: null, chave: `padrao-${campo.chave}` }}
              valor={campo.padrao} mudar={(v) => mudar({ padrao: v })} erro={erros.padrao} />
          )}
        </div>
        <label className="space-y-1 md:col-span-2">
          <span className="text-xs font-medium text-muted-foreground">Ajuda (aparece embaixo do campo)</span>
          <input className={caixa} value={campo.ajuda ?? ""} aria-label="Ajuda do campo" onChange={(e) => mudar({ ajuda: e.target.value })} />
        </label>
      </fieldset>
    </li>
  );
}
