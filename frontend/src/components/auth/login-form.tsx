"use client";

import Link from "next/link";
import type { FormEvent } from "react";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, ArrowLeft, ArrowRight, Eye, EyeOff, MailCheck } from "lucide-react";

import { AVISO_SESSAO, VOLTAR_PARA } from "@/components/auth/auth-provider";
import { Button } from "@/components/ui/button";
import { Field, Input, Label } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useAuth } from "@/hooks/use-auth";
import { ErroDaApi } from "@/lib/api";
import { confirmarCodigo, login, reenviarCodigo } from "@/lib/auth";

/*
 * Login em dois passos (13/11/2026): e-mail e senha; depois o código de 6 dígitos que chega por
 * e-mail, com "Confiar neste navegador por 30 dias" (nos próximos 30 dias, só a senha).
 */

type Desafio = { desafio: string; email: string; tentativas: number };
const ESPERA_PARA_REENVIAR_S = 30;

export function LoginForm() {
  const router = useRouter();
  const { concluirLogin } = useAuth();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [verSenha, setVerSenha] = useState(false);
  const [desafio, setDesafio] = useState<Desafio | null>(null);
  const [codigo, setCodigo] = useState("");
  const [confiar, setConfiar] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [expirou, setExpirou] = useState(false);
  const [liberaEm, setLiberaEm] = useState(0);  // hora (ms) em que "Reenviar código" libera
  const [espera, setEspera] = useState(0);
  const campoDoCodigo = useRef<HTMLInputElement>(null);

  useEffect(() => {
    try {
      setExpirou(window.sessionStorage.getItem(AVISO_SESSAO) === "1");
    } catch {
      /* sem armazenamento */
    }
  }, []);

  // Conta pelo relógio (não por soma de segundos): não atrasa com a aba lenta ou em segundo plano.
  useEffect(() => {
    const falta = () => Math.max(0, Math.ceil((liberaEm - Date.now()) / 1000));
    setEspera(falta());
    if (liberaEm <= Date.now()) return;
    const t = setInterval(() => {
      const s = falta();
      setEspera(s);
      if (s === 0) clearInterval(t);
    }, 250);
    return () => clearInterval(t);
  }, [liberaEm]);

  /** Volta para a tela de onde a pessoa veio (só caminho interno do Portal). */
  function destino(): string {
    try {
      const volta = window.sessionStorage.getItem(VOLTAR_PARA);
      window.sessionStorage.removeItem(VOLTAR_PARA);
      window.sessionStorage.removeItem(AVISO_SESSAO);
      if (volta && volta.startsWith("/") && !volta.startsWith("//") && !volta.startsWith("/login")) return volta;
    } catch {
      /* sem armazenamento */
    }
    return "/dashboard";
  }

  async function entrarCom(accessToken: string) {
    await concluirLogin(accessToken);
    router.push(destino());
    router.refresh();
  }

  async function enviarSenha(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);
    setAviso(null);
    setEnviando(true);
    try {
      const r = await login({ email: email.trim(), password: senha });
      if ("access_token" in r) {
        await entrarCom(r.access_token);
        return;
      }
      setDesafio({ desafio: r.desafio, email: r.email, tentativas: r.tentativas });
      setCodigo("");
      setLiberaEm(Date.now() + ESPERA_PARA_REENVIAR_S * 1000);
      setTimeout(() => campoDoCodigo.current?.focus(), 50);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível entrar.");
    } finally {
      setEnviando(false);
    }
  }

  async function enviarCodigo(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!desafio) return;
    setErro(null);
    setEnviando(true);
    try {
      const r = await confirmarCodigo(desafio.desafio, codigo, confiar, email.trim());
      await entrarCom(r.access_token);
    } catch (err) {
      const dados = err instanceof ErroDaApi ? err.dados : null;
      if (dados?.voltar_ao_login) {
        setDesafio(null);
        setSenha("");
        setAviso(err instanceof Error ? err.message : null);
      } else {
        setErro(err instanceof Error ? err.message : "Código não confere.");
        setCodigo("");
        campoDoCodigo.current?.focus();
      }
    } finally {
      setEnviando(false);
    }
  }

  async function reenviar() {
    if (!desafio) return;
    setErro(null);
    try {
      const r = await reenviarCodigo(desafio.desafio);
      setDesafio({ ...desafio, email: r.email, tentativas: r.tentativas });
      setAviso("Mandamos um código novo. O anterior não vale mais.");
      setLiberaEm(Date.now() + ESPERA_PARA_REENVIAR_S * 1000);
    } catch (err) {
      const dados = err instanceof ErroDaApi ? err.dados : null;
      if (dados?.voltar_ao_login) setDesafio(null);
      setErro(err instanceof Error ? err.message : "Não foi possível mandar outro código.");
    }
  }

  const caixaDeErro = erro && (
    <div role="alert" className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-sm text-destructive" data-testid="erro-do-login">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {erro}
    </div>
  );

  if (desafio) {
    return (
      <form className="space-y-5" onSubmit={enviarCodigo} data-testid="passo-do-codigo">
        <div className="flex items-start gap-3 rounded-lg border border-border bg-muted/30 p-4">
          <MailCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
          <p className="text-sm">
            Mandamos um código de 6 dígitos para <b>{desafio.email}</b>. Ele vale 10 minutos.
          </p>
        </div>
        {aviso && <p className="text-sm text-muted-foreground">{aviso}</p>}
        <Field>
          <Label htmlFor="codigo">Código</Label>
          <Input id="codigo" ref={campoDoCodigo} inputMode="numeric" autoComplete="one-time-code" value={codigo}
            onChange={(e) => setCodigo(e.target.value.replace(/\D/g, "").slice(0, 6))}
            className="h-14 text-center font-mono text-2xl tracking-[0.5em]" placeholder="••••••" />
        </Field>
        <label className="flex items-start gap-2.5 text-sm">
          <input type="checkbox" className="mt-0.5 h-4 w-4" checked={confiar} onChange={(e) => setConfiar(e.target.checked)} />
          <span>
            <b>Confiar neste navegador por 30 dias</b>
            <span className="block text-muted-foreground">Nos próximos 30 dias, entra só com a senha. Não marque em computador compartilhado.</span>
          </span>
        </label>
        {caixaDeErro}
        <Button type="submit" size="lg" className="w-full" disabled={enviando || codigo.length !== 6}>
          {enviando ? <><Spinner /> Conferindo…</> : <>Entrar <ArrowRight className="h-4 w-4" /></>}
        </Button>
        <div className="flex items-center justify-between text-sm">
          <button type="button" className="flex items-center gap-1 text-muted-foreground hover:text-foreground"
            onClick={() => { setDesafio(null); setErro(null); setAviso(null); }}>
            <ArrowLeft className="h-4 w-4" /> Voltar
          </button>
          <button type="button" className="font-medium text-primary hover:underline disabled:text-muted-foreground disabled:no-underline"
            disabled={espera > 0} onClick={() => void reenviar()}>
            {espera > 0 ? `Reenviar código em ${espera}s` : "Reenviar código"}
          </button>
        </div>
      </form>
    );
  }

  return (
    <form className="space-y-5" onSubmit={enviarSenha} data-testid="passo-da-senha">
      <p className="-mt-4 text-base text-muted-foreground">Use o e-mail e a senha da sua conta no Portal.</p>
      {expirou && (
        <div className="flex items-center gap-2 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2.5 text-sm" data-testid="sessao-expirada">
          <AlertCircle className="h-4 w-4 shrink-0 text-warning" />
          Sua sessão expirou. Entre de novo para continuar de onde parou.
        </div>
      )}
      {aviso && (
        <div className="flex items-center gap-2 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2.5 text-sm">
          <AlertCircle className="h-4 w-4 shrink-0 text-warning" /> {aviso}
        </div>
      )}
      <Field>
        <Label htmlFor="email">E-mail</Label>
        <Input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)}
          placeholder="voce@biason.net" className="h-12 text-base" />
      </Field>
      <Field>
        <div className="flex items-center justify-between">
          <Label htmlFor="password">Senha</Label>
          <Link href={`/esqueci-senha${email.trim() ? `?email=${encodeURIComponent(email.trim())}` : ""}`}
            className="text-sm font-medium text-primary hover:underline">Esqueci a senha</Link>
        </div>
        <div className="relative">
          <Input id="password" type={verSenha ? "text" : "password"} autoComplete="current-password" required value={senha}
            onChange={(e) => setSenha(e.target.value)} className="h-12 pr-11 text-base" />
          <button type="button" aria-label={verSenha ? "Esconder a senha" : "Mostrar a senha"} onClick={() => setVerSenha(!verSenha)}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-muted-foreground hover:text-foreground">
            {verSenha ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
      </Field>
      {caixaDeErro}
      <Button type="submit" size="lg" className="w-full" disabled={enviando || !email.trim() || !senha}>
        {enviando ? <><Spinner /> Entrando…</> : <>Entrar no portal <ArrowRight className="h-4 w-4" /></>}
      </Button>
      <p className="text-center text-sm text-muted-foreground">Primeiro acesso? Use o link &quot;Crie sua senha&quot; do e-mail de convite.</p>
    </form>
  );
}
