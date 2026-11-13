"use client";

import type { FormEvent } from "react";
import { useState } from "react";
import { KeyRound, MonitorSmartphone } from "lucide-react";

import { CamposDeSenhaNova, regrasDaSenha } from "@/components/auth/senha";
import { Button } from "@/components/ui/button";
import { Field, Input, Label } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { esquecerDispositivo } from "@/lib/auth";
import { formatDateTime } from "@/lib/utils";

/** "Mozilla/5.0 (Windows NT 10.0...) ... Edg/130" vira "Edge no Windows". */
export function resumoDoNavegador(ua: string | null): string {
  if (!ua) return "Navegador";
  const nome = /Edg\//.test(ua) ? "Edge" : /OPR\//.test(ua) ? "Opera" : /Firefox\//.test(ua) ? "Firefox"
    : /Chrome\//.test(ua) ? "Chrome" : /Safari\//.test(ua) ? "Safari" : "Navegador";
  const sistema = /Windows/.test(ua) ? "Windows" : /Android/.test(ua) ? "Android" : /iPhone|iPad/.test(ua) ? "iPhone/iPad"
    : /Mac OS X/.test(ua) ? "Mac" : /Linux/.test(ua) ? "Linux" : null;
  return sistema ? `${nome} no ${sistema}` : nome;
}

/** Trocar a senha (pede a atual) e esquecer os navegadores confiáveis (13/11/2026). */
export function SenhaEAcesso() {
  const { token, user } = useAuth();
  const { toast } = useToast();
  const navegadores = useApi<{ navegadores: { id: string; desde: string; vale_ate: string; navegador: string | null }[] }>("/auth/navegadores");
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const email = user?.email ?? "";
  const lista = Array.isArray(navegadores.data?.navegadores) ? navegadores.data.navegadores : [];

  async function trocar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);
    setOcupado(true);
    try {
      await apiRequest("/auth/trocar-senha", { token, method: "POST", body: JSON.stringify({ atual, nova }) });
      esquecerDispositivo(email);
      setAtual(""); setNova(""); setConfirmar("");
      toast({ title: "Senha trocada", description: "Os navegadores confiáveis vão pedir o código de novo.", kind: "success" });
      await navegadores.refetch();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível trocar a senha.");
    } finally {
      setOcupado(false);
    }
  }

  async function esquecer() {
    setOcupado(true);
    try {
      await apiRequest("/auth/navegadores", { token, method: "DELETE" });
      esquecerDispositivo(email);
      toast({ title: "Navegadores esquecidos", description: "No próximo login, todos pedem o código.", kind: "success" });
      await navegadores.refetch();
    } catch (err) {
      toast({ title: "Não foi possível", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setOcupado(false);
    }
  }

  return (
    <section className="space-y-4" data-testid="senha-e-acesso">
      <h2 className="titulo-condensado text-2xl">Senha e acesso</h2>
      <div className="grid gap-4 lg:grid-cols-2">
        <form onSubmit={trocar} className="space-y-4 rounded-xl border border-border bg-card p-5 shadow-sm">
          <h3 className="flex items-center gap-2 font-semibold text-titulo"><KeyRound className="h-4 w-4 text-primary" /> Trocar a senha</h3>
          <Field>
            <Label htmlFor="senha-atual">Senha atual</Label>
            <Input id="senha-atual" type="password" autoComplete="current-password" value={atual} onChange={(e) => setAtual(e.target.value)} />
          </Field>
          <CamposDeSenhaNova email={email} senha={nova} confirmar={confirmar} onSenha={setNova} onConfirmar={setConfirmar} />
          {erro && <p role="alert" className="text-sm text-destructive">{erro}</p>}
          <Button type="submit" disabled={ocupado || !atual || nova !== confirmar || !regrasDaSenha(nova, email).every((r) => r.ok)}>
            Trocar a senha
          </Button>
        </form>
        <div className="space-y-3 rounded-xl border border-border bg-card p-5 shadow-sm">
          <h3 className="flex items-center gap-2 font-semibold text-titulo"><MonitorSmartphone className="h-4 w-4 text-primary" /> Navegadores confiáveis</h3>
          <p className="text-sm text-muted-foreground">
            Onde você marcou &quot;Confiar neste navegador&quot;: por 30 dias, eles pedem só a senha, sem o código.
          </p>
          {lista.length === 0 ? <p className="text-sm">Nenhum agora: todo login pede o código.</p> : (
            <ul className="divide-y divide-border rounded-lg border border-border text-sm" data-testid="navegadores">
              {lista.map((n) => (
                <li key={n.id} className="px-3 py-2">
                  <p className="truncate font-medium" title={n.navegador ?? undefined}>{resumoDoNavegador(n.navegador)}</p>
                  <p className="text-xs text-muted-foreground">desde {formatDateTime(n.desde)} · vale até {formatDateTime(n.vale_ate)}</p>
                </li>
              ))}
            </ul>
          )}
          {lista.length > 0 && <Button variant="outline" disabled={ocupado} onClick={() => void esquecer()}>Esquecer todos</Button>}
        </div>
      </div>
    </section>
  );
}
