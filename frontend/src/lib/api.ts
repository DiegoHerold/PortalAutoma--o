import { API_BASE_URL } from "@/lib/constants";

type RequestOptions = RequestInit & {
  token?: string | null;
};

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");

  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  if (!text) {
    return undefined as T;
  }

  return JSON.parse(text) as T;
}

/**
 * Multipart upload (e.g. ZIP import). Deliberately does not set Content-Type
 * so the browser fills in the multipart boundary itself.
 */
export async function apiUpload<T>(path: string, formData: FormData, token: string | null): Promise<T> {
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: formData,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }

  const text = await response.text();
  return text ? (JSON.parse(text) as T) : (undefined as T);
}

/**
 * Baixa um arquivo autenticado (ex: artefato de execução) e dispara o download no navegador.
 * Necessário porque o endpoint exige o header Authorization — um <a href> puro não bastaria.
 */
export async function apiDownload(path: string, token: string | null, filename?: string): Promise<void> {
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_BASE_URL}${path}`, { headers, cache: "no-store" });
  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "download";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function errorMessage(response: Response): Promise<string> {
  const text = await response.text();
  if (!text) return "Erro na comunicacao com a API.";
  try {
    const parsed = JSON.parse(text) as {
      error?: { code?: string; message?: string; correlation_id?: string };
      detail?: string | Array<{ msg?: string }>;
    };
    if (parsed.error?.message) {
      const suffix = parsed.error.correlation_id ? ` (${parsed.error.correlation_id})` : "";
      return `${parsed.error.message}${suffix}`;
    }
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail) && parsed.detail[0]?.msg) return parsed.detail[0].msg;
  } catch {
    // Fall through to raw text.
  }
  return text || "Erro na comunicacao com a API.";
}
