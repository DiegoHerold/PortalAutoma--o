export function LoadingState({ label = "Carregando..." }: { label?: string }) {
  return <div className="rounded-2xl bg-white/70 p-4 text-sm text-slate-500">{label}</div>;
}
