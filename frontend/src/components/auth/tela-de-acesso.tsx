import type { ReactNode } from "react";
import { Activity, Hand, ShieldCheck } from "lucide-react";

/*
 * Telas de acesso (13/11/2026): login, código, esqueci a senha e criar a senha, na identidade
 * Biason (faixa azul-marinho com o logo branco à esquerda; o formulário à direita).
 */

const DESTAQUES = [
  { icon: Activity, texto: "Cada execução ao vivo, com telas, logs e previsão de término" },
  { icon: Hand, texto: "Quando uma automação precisa de você, um e-mail com o botão para continuar" },
  { icon: ShieldCheck, texto: "Acesso com código por e-mail e navegador confiável por 30 dias" },
];

export function TelaDeAcesso({ titulo, subtitulo, children }: { titulo: string; subtitulo?: ReactNode; children: ReactNode }) {
  return (
    <main className="grid min-h-screen bg-background lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <section className="relative hidden flex-col justify-between overflow-hidden bg-sidebar p-12 text-sidebar-foreground lg:flex">
        <div className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 rounded-full bg-white/5" />
        <div className="pointer-events-none absolute -bottom-32 -left-16 h-80 w-80 rounded-full bg-white/5" />
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/marca/logo-biason-branco.png" alt="Biason Assessoria Empresarial" className="relative h-12 w-auto self-start" />
        <div className="relative max-w-lg">
          <p className="mb-3 text-sm font-semibold uppercase tracking-[0.18em] text-sidebar-foreground/60">Portal de Automações</p>
          <h1 className="titulo-condensado text-4xl leading-tight text-white">As automações da Biason, acompanhadas de perto.</h1>
          <ul className="mt-10 space-y-4">
            {DESTAQUES.map(({ icon: Icone, texto }) => (
              <li key={texto} className="flex items-center gap-3 text-base text-sidebar-foreground/85">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/10 text-white">
                  <Icone className="h-4 w-4" />
                </span>
                {texto}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-sm text-sidebar-foreground/50">Biason Assessoria Empresarial</p>
      </section>

      <section className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="mb-10 lg:hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/marca/logo-biason-azul.png" alt="Biason Assessoria Empresarial" className="h-10 w-auto dark:hidden" />
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/marca/logo-biason-branco.png" alt="" aria-hidden className="hidden h-10 w-auto dark:block" />
          </div>
          <h2 className="titulo-condensado text-3xl text-titulo">{titulo}</h2>
          {subtitulo && <p className="mt-2 text-base text-muted-foreground">{subtitulo}</p>}
          <div className="mt-8">{children}</div>
        </div>
      </section>
    </main>
  );
}
