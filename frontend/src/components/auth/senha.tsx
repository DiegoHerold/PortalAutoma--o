"use client";

import Link from "next/link";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AlertCircle, ArrowLeft, Check, CheckCircle2, Eye, EyeOff, MailCheck } from "lucide-react";

import { TelaDeAcesso } from "@/components/auth/tela-de-acesso";
import { Button } from "@/components/ui/button";
import { Field, Input, Label } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { definirSenha, pedirLinkDeSenha, verLinkDeSenha } from "@/lib/auth";
import { cn } from "@/lib/utils";

/*
 * Esqueci a senha e criar a senha (13/11/2026). O link do e-mail traz o token no fragmento (#t=...),
 * que o navegador não manda ao servidor: a página lê e manda no corpo do pedido.
 */

export function EsqueciASenha() {
  const params = useSearchParams();
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [mensagem, setMensagem] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setEnviando(true);
    setErro(null);
    try {
      setMensagem((await pedirLinkDeSenha(email.trim())).mensagem);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível pedir o link.");
    } finally {
      setEnviando(false);
    }
  }

  if (mensagem) {
    return (
      <div className="space-y-6" data-testid="link-pedido">
        <div className="flex items-start gap-3 rounded-lg border border-success/30 bg-success/5 p-4">
          <MailCheck className="mt-0.5 h-5 w-5 shrink-0 text-success" />
          <p>{mensagem} O link vale 1 hora.</p>
        </div>
        <Link href="/login" className="flex items-center gap-1 text-sm font-medium text-primary hover:underline"><ArrowLeft className="h-4 w-4" /> Voltar ao login</Link>
      </div>
    );
  }
  return (
    <form className="space-y-5" onSubmit={enviar}>
      <Field>
        <Label htmlFor="email">E-mail da sua conta</Label>
        <Input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)}
          className="h-12 text-base" placeholder="voce@biason.net" />
      </Field>
      {erro && <p role="alert" className="text-sm text-destructive">{erro}</p>}
      <Button type="submit" size="lg" className="w-full" disabled={enviando || !email.trim()}>
        {enviando ? <><Spinner /> Mandando…</> : "Mandar o link"}
      </Button>
      <Link href="/login" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" /> Voltar ao login</Link>
    </form>
  );
}

/** As mesmas regras do Portal, mostradas enquanto a pessoa digita. */
export function regrasDaSenha(senha: string, email: string): { texto: string; ok: boolean }[] {
  const nome = email.split("@")[0]?.toLowerCase() ?? "";
  return [
    { texto: "De 8 a 128 caracteres", ok: senha.length >= 8 && senha.length <= 128 },
    { texto: "Não é um caractere repetido", ok: senha.length > 0 && new Set(senha).size > 1 },
    { texto: "Não contém o seu nome de e-mail", ok: senha.length > 0 && !(nome.length >= 4 && senha.toLowerCase().includes(nome)) },
  ];
}

export function CamposDeSenhaNova({ email, senha, confirmar, onSenha, onConfirmar, rotulo = "Senha nova" }: {
  email: string; senha: string; confirmar: string; onSenha: (v: string) => void; onConfirmar: (v: string) => void; rotulo?: string }) {
  const [ver, setVer] = useState(false);
  const regras = regrasDaSenha(senha, email);
  return (
    <>
      <Field>
        <Label htmlFor="senha-nova">{rotulo}</Label>
        <div className="relative">
          <Input id="senha-nova" type={ver ? "text" : "password"} autoComplete="new-password" value={senha} onChange={(e) => onSenha(e.target.value)}
            className="h-12 pr-11 text-base" />
          <button type="button" aria-label={ver ? "Esconder a senha" : "Mostrar a senha"} onClick={() => setVer(!ver)}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-muted-foreground hover:text-foreground">
            {ver ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
        <ul className="mt-2 space-y-1 text-sm" data-testid="regras-da-senha">
          {regras.map((r) => (
            <li key={r.texto} className={cn("flex items-center gap-1.5", r.ok ? "text-success" : "text-muted-foreground")}>
              <Check className={cn("h-3.5 w-3.5", r.ok ? "opacity-100" : "opacity-30")} /> {r.texto}
            </li>
          ))}
        </ul>
      </Field>
      <Field>
        <Label htmlFor="senha-confirmar">Repita a senha</Label>
        <Input id="senha-confirmar" type={ver ? "text" : "password"} autoComplete="new-password" value={confirmar}
          onChange={(e) => onConfirmar(e.target.value)} className="h-12 text-base" />
        {confirmar && confirmar !== senha && <p className="text-sm text-destructive">As duas senhas não são iguais.</p>}
      </Field>
    </>
  );
}

export function CriarSenha() {
  const [token, setToken] = useState<string | null>(null);
  const [link, setLink] = useState<{ tipo: "convite" | "redefinir"; email: string; nome: string } | null>(null);
  const [erroDoLink, setErroDoLink] = useState<string | null>(null);
  const [senha, setSenha] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [pronto, setPronto] = useState(false);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    const t = new URLSearchParams(window.location.hash.replace(/^#/, "")).get("t");
    setToken(t);
    if (!t) {
      setErroDoLink("Este link está incompleto. Abra de novo pelo botão do e-mail ou peça outro em Esqueci a senha.");
      return;
    }
    verLinkDeSenha(t).then(setLink).catch((err) => setErroDoLink(err instanceof Error ? err.message : "Este link não vale."));
  }, []);

  async function salvar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || senha !== confirmar) return;
    setEnviando(true);
    setErro(null);
    try {
      await definirSenha(token, senha);
      setPronto(true);
      window.history.replaceState(null, "", window.location.pathname);  // o token sai da barra de endereço
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível salvar a senha.");
    } finally {
      setEnviando(false);
    }
  }

  const titulo = link?.tipo === "convite" ? "Crie sua senha" : "Senha nova";
  const regrasOk = regrasDaSenha(senha, link?.email ?? "").every((r) => r.ok);
  return (
    <TelaDeAcesso titulo={titulo} subtitulo={link ? <>Para <b className="text-foreground">{link.email}</b></> : undefined}>
      {pronto ? (
        <div className="space-y-6" data-testid="senha-salva">
          <div className="flex items-start gap-3 rounded-lg border border-success/30 bg-success/5 p-4">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
            <p>Senha salva. Agora entre com ela; no primeiro acesso, o Portal manda um código para o seu e-mail.</p>
          </div>
          <Button asChild size="lg" className="w-full"><Link href="/login">Ir para o login</Link></Button>
        </div>
      ) : erroDoLink ? (
        <div className="space-y-6" data-testid="link-invalido">
          <div className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-destructive">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" /> <p>{erroDoLink}</p>
          </div>
          <Button asChild variant="outline" size="lg" className="w-full"><Link href="/esqueci-senha">Pedir outro link</Link></Button>
        </div>
      ) : !link ? (
        <div className="skeleton h-48 rounded-xl" />
      ) : (
        <form className="space-y-5" onSubmit={salvar}>
          {link.tipo === "convite" && <p className="text-muted-foreground">Olá, {link.nome}. Escolha a senha que vai usar no Portal.</p>}
          <CamposDeSenhaNova email={link.email} senha={senha} confirmar={confirmar} onSenha={setSenha} onConfirmar={setConfirmar} />
          {erro && <p role="alert" className="text-sm text-destructive">{erro}</p>}
          <Button type="submit" size="lg" className="w-full" disabled={enviando || !regrasOk || senha !== confirmar}>
            {enviando ? <><Spinner /> Salvando…</> : "Salvar a senha"}
          </Button>
        </form>
      )}
    </TelaDeAcesso>
  );
}
