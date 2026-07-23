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
    const message = await response.text();
    throw new Error(message || "Erro na comunicacao com a API.");
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
    const message = await response.text();
    throw new Error(message || "Erro na comunicacao com a API.");
  }

  const text = await response.text();
  return text ? (JSON.parse(text) as T) : (undefined as T);
}
