type ClassValue = string | number | null | false | undefined | ClassValue[] | Record<string, boolean>;

function toVal(mix: ClassValue): string {
  if (!mix) return "";
  if (typeof mix === "string" || typeof mix === "number") return String(mix);
  if (Array.isArray(mix)) return mix.map(toVal).filter(Boolean).join(" ");
  if (typeof mix === "object") {
    return Object.keys(mix)
      .filter((key) => (mix as Record<string, boolean>)[key])
      .join(" ");
  }
  return "";
}

/** Lightweight classnames helper (clsx-style), zero dependencies. */
export function cn(...inputs: ClassValue[]): string {
  return inputs.map(toVal).filter(Boolean).join(" ");
}

export function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

export function formatTime(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

/** Human duration from seconds, e.g. 92 -> "1m 32s". */
export function formatDuration(seconds?: number | null): string {
  if (seconds == null || Number.isNaN(seconds)) return "—";
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m < 60) return rem ? `${m}m ${rem}s` : `${m}m`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return remM ? `${h}h ${remM}m` : `${h}h`;
}

/** Countdown label from now to a target ISO timestamp. */
export function formatCountdown(target?: string | null): string {
  if (!target) return "—";
  const diff = (new Date(target).getTime() - Date.now()) / 1000;
  if (Number.isNaN(diff)) return "—";
  if (diff <= 0) return "agora";
  return `em ${formatDuration(diff)}`;
}

export function relativeFromNow(value?: string | null): string {
  if (!value) return "—";
  const diff = (Date.now() - new Date(value).getTime()) / 1000;
  if (Number.isNaN(diff)) return "—";
  if (diff < 60) return "há segundos";
  if (diff < 3600) return `há ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `há ${Math.floor(diff / 3600)} h`;
  return `há ${Math.floor(diff / 86400)} d`;
}
