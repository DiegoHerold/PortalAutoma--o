"use client";

import { useState } from "react";

import type { Campo } from "@/lib/campos";
import { cn } from "@/lib/utils";

const CAIXA = "h-11 w-full rounded-md border border-input bg-background px-3 text-base";

/** Um campo do formulário no tipo dele. O Portal confere de novo ao gravar. */
export function CampoDeEntrada({ campo, valor, mudar, erro }: {
  campo: Campo;
  valor: unknown;
  mudar: (v: unknown) => void;
  erro?: string;
}) {
  const id = `campo-${campo.chave}`;
  const rotulo = (
    <span className="text-sm font-medium">
      {campo.rotulo}{campo.obrigatorio && <span className="text-destructive" aria-hidden> *</span>}
    </span>
  );
  const rodape = (
    <>
      {campo.ajuda && <span className="block text-sm text-muted-foreground">{campo.ajuda}</span>}
      {erro && <span role="alert" className="block text-sm text-destructive">{erro}</span>}
    </>
  );
  const borda = erro ? "border-destructive" : "";

  if (campo.tipo === "sim_nao") {
    return (
      <div className="space-y-1 sm:col-span-2">
        <label htmlFor={id} className="flex cursor-pointer items-center gap-3">
          <input id={id} type="checkbox" className="h-5 w-5 accent-[hsl(var(--primary))]" checked={valor === true}
            onChange={(e) => mudar(e.target.checked)} aria-label={campo.rotulo} />
          {rotulo}
        </label>
        {rodape}
      </div>
    );
  }
  if (campo.tipo === "json") return <CampoJson id={id} campo={campo} valor={valor} mudar={mudar} erro={erro} rotulo={rotulo} />;

  let controle: React.ReactNode;
  const texto = valor === null || valor === undefined ? "" : String(valor);
  if (campo.tipo === "lista") {
    controle = (
      <select id={id} className={cn(CAIXA, borda)} value={texto} onChange={(e) => mudar(e.target.value || null)} aria-label={campo.rotulo}>
        <option value="">{campo.obrigatorio ? "Escolha…" : "—"}</option>
        {campo.opcoes.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  } else if (campo.tipo === "texto_longo") {
    controle = <textarea id={id} rows={4} className={cn(CAIXA, "h-auto py-2", borda)} value={texto}
      onChange={(e) => mudar(e.target.value)} aria-label={campo.rotulo} />;
  } else {
    const tipoHtml = { numero: "text", inteiro: "number", data: "date", email: "email" }[campo.tipo as string] ?? "text";
    const dica = { mes_ano: "MM/AAAA", numero: "ex.: 1,5", pasta: "C:\\pasta\\destino" }[campo.tipo as string];
    controle = <input id={id} type={tipoHtml} className={cn(CAIXA, borda)} value={texto} placeholder={dica}
      inputMode={campo.tipo === "numero" || campo.tipo === "mes_ano" ? "decimal" : undefined}
      onChange={(e) => mudar(e.target.value)} aria-label={campo.rotulo} />;
  }
  return (
    <label htmlFor={id} className={cn("space-y-1.5", campo.tipo === "texto_longo" && "sm:col-span-2")}>
      {rotulo}
      {controle}
      {rodape}
    </label>
  );
}

function CampoJson({ id, campo, valor, mudar, erro, rotulo }: {
  id: string; campo: Campo; valor: unknown; mudar: (v: unknown) => void; erro?: string; rotulo: React.ReactNode;
}) {
  const [texto, setTexto] = useState(() => (valor === undefined || valor === null ? "" : JSON.stringify(valor, null, 2)));
  const [invalido, setInvalido] = useState(false);
  return (
    <label htmlFor={id} className="space-y-1.5 sm:col-span-2">
      {rotulo}
      <textarea id={id} rows={5} spellCheck={false} aria-label={campo.rotulo}
        className={cn(CAIXA, "h-auto py-2 font-mono text-sm", (erro || invalido) && "border-destructive")} value={texto}
        onChange={(e) => {
          setTexto(e.target.value);
          if (!e.target.value.trim()) { setInvalido(false); mudar(null); return; }
          try { mudar(JSON.parse(e.target.value)); setInvalido(false); } catch { setInvalido(true); }
        }} />
      <span className="block text-sm text-muted-foreground">{campo.ajuda ?? "Dados avançados, em JSON."}</span>
      {(erro || invalido) && <span role="alert" className="block text-sm text-destructive">{erro ?? "JSON inválido"}</span>}
    </label>
  );
}
