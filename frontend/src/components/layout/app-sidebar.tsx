import Link from "next/link";

const items = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/automations", label: "Automacoes" },
  { href: "/jobs", label: "Jobs" },
  { href: "/workers", label: "Workers" },
  { href: "/users", label: "Usuarios" },
  { href: "/categories", label: "Categorias" },
];

export function AppSidebar() {
  return (
    <aside className="rounded-[2rem] bg-ink p-6 text-white shadow-xl">
      <div className="mb-8">
        <p className="text-xs uppercase tracking-[0.3em] text-teal-200">Portal</p>
        <h2 className="mt-2 text-2xl font-semibold">Automacoes</h2>
      </div>
      <nav className="space-y-2">
        {items.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="block rounded-2xl px-4 py-3 text-sm text-slate-100 transition hover:bg-white/10"
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
