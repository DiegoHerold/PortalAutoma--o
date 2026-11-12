"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, ArrowRight } from "lucide-react";

import { AVISO_SESSAO, VOLTAR_PARA } from "@/components/auth/auth-provider";
import { useAuth } from "@/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { Input, Label, Field } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";

export function LoginForm() {
  const router = useRouter();
  const { signIn } = useAuth();
  const [email, setEmail] = useState("admin@portal.local");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [expirou, setExpirou] = useState(false);

  useEffect(() => {
    try {
      setExpirou(window.sessionStorage.getItem(AVISO_SESSAO) === "1");
    } catch {
      /* sem armazenamento */
    }
  }, []);

  /** Volta para a tela em que a sessão venceu (só caminho interno do Portal). */
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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signIn({ email, password });
      router.push(destino());
      router.refresh();
    } catch {
      setError("Não foi possível autenticar com as credenciais informadas.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit}>
      {expirou && (
        <div className="flex items-center gap-2 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-sm" data-testid="sessao-expirada">
          <AlertCircle className="h-4 w-4 shrink-0 text-warning" />
          Sua sessão expirou. Entre de novo para continuar de onde parou.
        </div>
      )}
      <Field>
        <Label htmlFor="email">E-mail</Label>
        <Input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      </Field>
      <Field>
        <Label htmlFor="password">Senha</Label>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </Field>
      {error && (
        <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}
      <Button type="submit" size="lg" className="w-full" disabled={submitting}>
        {submitting ? (
          <>
            <Spinner /> Entrando…
          </>
        ) : (
          <>
            Entrar no portal <ArrowRight className="h-4 w-4" />
          </>
        )}
      </Button>
    </form>
  );
}
