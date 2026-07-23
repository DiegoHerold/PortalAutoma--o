export const APP_NAME = "Portal de Automacoes";

/**
 * Resolves the API base URL at runtime instead of baking one in at build time.
 * Without this, accessing the frontend via the machine's LAN IP (instead of
 * localhost) would still try to call http://localhost:8000, which points at
 * the *browser's own* machine, not the server — breaking every request.
 *
 * Preference order: explicit NEXT_PUBLIC_API_URL (for reverse-proxy/prod
 * setups where the API lives on a different host) > same hostname the page
 * was loaded from, port 8000 (covers localhost, 127.0.0.1 and any LAN IP
 * automatically) > localhost fallback for SSR/build time.
 */
function resolveApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== "undefined" && window.location?.hostname) {
    return `http://${window.location.hostname}:8000/api/v1`;
  }
  return "http://localhost:8000/api/v1";
}

export const API_BASE_URL = resolveApiBaseUrl();
