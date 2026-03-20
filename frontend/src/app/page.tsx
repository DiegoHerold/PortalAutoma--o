import Link from "next/link";

export default function HomePage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="max-w-2xl rounded-[2rem] bg-white/80 p-10 shadow-xl backdrop-blur">
        <p className="text-sm font-semibold uppercase tracking-[0.28em] text-accent">Portal de automacoes</p>
        <h1 className="mt-4 text-5xl font-semibold leading-tight">Base pronta para orquestrar jobs, workers e permissoes.</h1>
        <p className="mt-4 text-slate-600">
          O scaffold ja separa backend, frontend, filas, autenticacao e o inicio da camada operacional.
        </p>
        <div className="mt-8 flex gap-3">
          <Link href="/login" className="rounded-2xl bg-ink px-5 py-3 text-sm font-semibold text-white">
            Entrar
          </Link>
          <Link href="/dashboard" className="rounded-2xl border border-slate-200 px-5 py-3 text-sm font-semibold">
            Ver painel
          </Link>
        </div>
      </div>
    </main>
  );
}
