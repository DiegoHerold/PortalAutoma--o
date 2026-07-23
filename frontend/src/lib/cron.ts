/** Very small, friendly cron descriptor for common patterns (pt-BR). */
export function describeCron(expr?: string | null): string {
  if (!expr) return "—";
  const parts = expr.trim().split(/\s+/);
  if (parts.length < 5) return expr;
  const [min, hour, dom, mon, dow] = parts;

  const every = (v: string) => v === "*";
  const time = (h: string, m: string) =>
    `${h.padStart(2, "0")}:${m.padStart(2, "0")}`;

  if (every(dom) && every(mon) && every(dow) && !every(hour) && !every(min)) {
    return `Todos os dias às ${time(hour, min)}`;
  }
  if (every(dom) && every(mon) && !every(dow) && !every(hour)) {
    const days = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
    const label = dow.split(",").map((d) => days[Number(d) % 7] ?? d).join(", ");
    return `Toda ${label} às ${time(hour, min)}`;
  }
  if (min.startsWith("*/")) {
    return `A cada ${min.slice(2)} min`;
  }
  if (every(hour) && !every(min)) {
    return `Todo hora no min ${min}`;
  }
  return expr;
}
