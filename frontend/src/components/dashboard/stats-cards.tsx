const stats = [
  { label: "Automacoes ativas", value: "24" },
  { label: "Execucoes aguardando", value: "13" },
  { label: "Workers online", value: "5" },
];

export function StatsCards() {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {stats.map((item) => (
        <div key={item.label} className="rounded-3xl bg-white/80 p-6 shadow-sm">
          <p className="text-sm text-slate-500">{item.label}</p>
          <p className="mt-4 text-4xl font-semibold">{item.value}</p>
        </div>
      ))}
    </div>
  );
}
