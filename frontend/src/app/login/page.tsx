import { LoginForm } from "@/components/auth/login-form";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-12">
      <div className="grid max-w-5xl gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <section className="rounded-[2rem] bg-ink p-10 text-white shadow-xl">
          <p className="text-sm uppercase tracking-[0.32em] text-teal-200">Operacao</p>
          <h1 className="mt-6 text-4xl font-semibold leading-tight">
            Controle execucoes, prioridades e acesso por categoria em um unico painel.
          </h1>
          <p className="mt-4 max-w-xl text-sm text-slate-200">
            A estrutura inicial ja contempla JWT, workers, Redis, PostgreSQL, filas e guardas de rota para o portal.
          </p>
        </section>
        <section className="rounded-[2rem] bg-white/85 p-8 shadow-xl">
          <h2 className="text-2xl font-semibold">Entrar</h2>
          <p className="mt-2 text-sm text-slate-500">Use o usuario inicial do ambiente para acessar o painel.</p>
          <div className="mt-8">
            <LoginForm />
          </div>
        </section>
      </div>
    </main>
  );
}
