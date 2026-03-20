export default function ForbiddenPage() {
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="rounded-[2rem] bg-white/85 p-10 text-center shadow-xl">
        <h1 className="text-3xl font-semibold">Acesso negado</h1>
        <p className="mt-3 text-sm text-slate-600">
          Seu usuario nao possui permissao suficiente para visualizar este recurso.
        </p>
      </div>
    </main>
  );
}
