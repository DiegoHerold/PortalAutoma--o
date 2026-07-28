import { Boxes, Activity, GaugeCircle, ShieldCheck } from "lucide-react";

import { LoginForm } from "@/components/auth/login-form";

const highlights = [
  { icon: Activity, text: "Monitoramento de execuções em tempo real" },
  { icon: GaugeCircle, text: "Estimativa de início e término por histórico" },
  { icon: ShieldCheck, text: "Acesso por papel e permissão por categoria" },
];

export default function LoginPage() {
  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      {/* Brand / operations panel */}
      <section className="relative hidden flex-col justify-between overflow-hidden bg-sidebar p-12 text-sidebar-foreground lg:flex">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.06]"
          style={{
            backgroundImage:
              "linear-gradient(hsl(var(--sidebar-foreground)) 1px, transparent 1px), linear-gradient(90deg, hsl(var(--sidebar-foreground)) 1px, transparent 1px)",
            backgroundSize: "42px 42px",
          }}
        />
        <div className="relative flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Boxes className="h-5 w-5" />
          </div>
          <span className="font-display text-lg font-semibold text-white">Portal de Automações</span>
        </div>

        <div className="relative max-w-md">
          <h1 className="font-display text-4xl font-semibold leading-tight text-white">
            Orquestre automações, filas e workers em um só lugar.
          </h1>
          <p className="mt-4 text-sm text-sidebar-foreground/70">
            Dispare por gatilho, distribua para a máquina certa e acompanhe cada execução com estimativa de tempo em
            tempo real.
          </p>
          <ul className="mt-8 space-y-3">
            {highlights.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-3 text-sm text-sidebar-foreground/85">
                <span className="flex h-8 w-8 items-center justify-center rounded-md bg-sidebar-accent text-primary">
                  <Icon className="h-4 w-4" />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-sidebar-foreground/50">Biason Assessoria Empresarial</p>
      </section>

      {/* Auth panel */}
      <section className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Boxes className="h-6 w-6" />
            </div>
            <h1 className="font-display text-2xl font-semibold">Portal de Automações</h1>
          </div>
          <h2 className="font-display text-2xl font-semibold tracking-tight">Entrar</h2>
          <p className="mt-1.5 text-sm text-muted-foreground">Acesse o painel operacional com sua conta.</p>
          <div className="mt-8">
            <LoginForm />
          </div>
        </div>
      </section>
    </main>
  );
}
