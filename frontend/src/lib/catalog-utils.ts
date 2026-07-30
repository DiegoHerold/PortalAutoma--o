export type NormalizedValidationError = {
  code?: string;
  title: string;
  field?: string;
  message: string;
  severity?: string;
  expected?: string;
  received?: string;
  details?: Record<string, unknown>;
  technical: string;
};

export function normalizeCatalogKey(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9_.-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function formatBytes(bytes?: number | null): string {
  if (bytes == null || Number.isNaN(bytes)) return "-";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(value >= 10 ? 1 : 2)} ${units[index]}`;
}

export function compareSemver(a?: string | null, b?: string | null): number | null {
  const left = parseSemver(a);
  const right = parseSemver(b);
  if (!left || !right) return null;
  for (let index = 0; index < 3; index += 1) {
    const diff = left.numbers[index] - right.numbers[index];
    if (diff !== 0) return diff > 0 ? 1 : -1;
  }
  if (left.prerelease === right.prerelease) return 0;
  if (!left.prerelease) return 1;
  if (!right.prerelease) return -1;
  return left.prerelease.localeCompare(right.prerelease);
}

export function isSemverBelow(current?: string | null, minimum?: string | null): boolean {
  const comparison = compareSemver(current, minimum);
  return comparison != null && comparison < 0;
}

export function normalizeValidationErrors(errors?: Array<Record<string, unknown>> | null): NormalizedValidationError[] {
  return (errors ?? []).map((error) => {
    const details = asRecord(error.details);
    const field = stringValue(error.field) ?? stringValue(error.path) ?? stringValue(error.location);
    const message = stringValue(error.message) ?? stringValue(details?.message) ?? "Problema de validacao informado pelo backend.";
    const code = stringValue(error.code);
    return {
      code,
      title: code ? labelFromCode(code) : "Erro de validacao",
      field,
      message,
      severity: stringValue(error.severity) ?? stringValue(details?.severity),
      expected: stringifyValue(error.expected ?? details?.expected),
      received: stringifyValue(error.received ?? details?.received ?? details?.value),
      details,
      technical: JSON.stringify(error, null, 2),
    };
  });
}

export function defaultAutomationManifest(automationKey: string): string {
  const key = automationKey || "dominio.automacao";
  return [
    "schema_version: '1.0'",
    "automation:",
    `  id: ${key}`,
    "  name: Nova automacao",
    "  version: 1.0.0",
    "  description: Primeira versao",
    "runtime:",
    "  id: python-desktop",
    "  version: 1.0.0",
    "entrypoint:",
    "  type: python-function",
    "  module: automation.main",
    "  function: run",
    "execution:",
    "  mode: background",
    "  timeout_seconds: 300",
    "resources:",
    "  cpu_units: 1",
    "  memory_mb: 512",
    "  disk_mb: 100",
    "capabilities:",
    "  required: []",
    "exclusive_resources: []",
  ].join("\n");
}

export async function sha256File(file: File, maxBytes = 128 * 1024 * 1024): Promise<{ hash: string | null; skippedReason?: string }> {
  if (typeof crypto === "undefined" || !crypto.subtle) {
    return { hash: null, skippedReason: "Hash indisponivel neste navegador." };
  }
  if (file.size > maxBytes) {
    return { hash: null, skippedReason: `Hash local pulado para arquivos acima de ${formatBytes(maxBytes)}.` };
  }
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  const bytes = Array.from(new Uint8Array(digest));
  return { hash: bytes.map((byte) => byte.toString(16).padStart(2, "0")).join("") };
}

function parseSemver(value?: string | null): { numbers: [number, number, number]; prerelease: string } | null {
  if (!value) return null;
  const match = value.trim().match(/^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$/);
  if (!match) return null;
  return {
    numbers: [Number(match[1]), Number(match[2]), Number(match[3])],
    prerelease: match[4] ?? "",
  };
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : undefined;
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function stringifyValue(value: unknown): string | undefined {
  if (value == null || value === "") return undefined;
  return typeof value === "string" ? value : JSON.stringify(value);
}

function labelFromCode(code: string): string {
  return code
    .toLowerCase()
    .split(/[_\s.-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
