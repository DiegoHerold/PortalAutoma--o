import { apiRequest } from "@/lib/api";
import { API_BASE_URL } from "@/lib/constants";
import type {
  AutomationVersionCreateRequest,
  AutomationVersionResponse,
  BlockRequest,
  PackageResponse,
  PackageUploadCreateRequest,
  PackageUploadResponse,
  RuntimeCreateRequest,
  RuntimeResponse,
  RuntimeVersionCreateRequest,
  RuntimeVersionResponse,
} from "@/types/catalog";

export type UploadProgress = {
  loaded: number;
  total: number;
  percent: number;
};

export function createRuntime(token: string, payload: RuntimeCreateRequest, idempotencyKey: string) {
  return apiRequest<RuntimeResponse>("/runtimes", {
    method: "POST",
    token,
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(payload),
  });
}

export function createRuntimeVersion(token: string, runtimeId: string, payload: RuntimeVersionCreateRequest, idempotencyKey: string) {
  return apiRequest<RuntimeVersionResponse>(`/runtimes/${runtimeId}/versions`, {
    method: "POST",
    token,
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(payload),
  });
}

export function publishRuntimeVersion(token: string, runtimeVersionId: string) {
  return apiRequest<RuntimeVersionResponse>(`/runtime-versions/${runtimeVersionId}/publish`, { method: "POST", token });
}

export function deprecateRuntimeVersion(token: string, runtimeVersionId: string) {
  return apiRequest<RuntimeVersionResponse>(`/runtime-versions/${runtimeVersionId}/deprecate`, { method: "POST", token });
}

export function blockRuntimeVersion(token: string, runtimeVersionId: string, payload: BlockRequest) {
  return apiRequest<RuntimeVersionResponse>(`/runtime-versions/${runtimeVersionId}/block`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function createAutomationVersion(
  token: string,
  automationId: number,
  payload: AutomationVersionCreateRequest,
  idempotencyKey: string,
) {
  return apiRequest<AutomationVersionResponse>(`/automations/${automationId}/versions`, {
    method: "POST",
    token,
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(payload),
  });
}

export function validateAutomationVersion(token: string, versionId: number) {
  return apiRequest<AutomationVersionResponse>(`/automation-versions/${versionId}/validate`, { method: "POST", token });
}

export function publishAutomationVersion(token: string, versionId: number) {
  return apiRequest<AutomationVersionResponse>(`/automation-versions/${versionId}/publish`, { method: "POST", token });
}

export function deprecateAutomationVersion(token: string, versionId: number) {
  return apiRequest<AutomationVersionResponse>(`/automation-versions/${versionId}/deprecate`, { method: "POST", token });
}

export function blockAutomationVersion(token: string, versionId: number, payload: BlockRequest) {
  return apiRequest<AutomationVersionResponse>(`/automation-versions/${versionId}/block`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function initiatePackageUpload(token: string, versionId: number, payload: PackageUploadCreateRequest, idempotencyKey: string) {
  return apiRequest<PackageUploadResponse>(`/automation-versions/${versionId}/package-uploads`, {
    method: "POST",
    token,
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(payload),
  });
}

export function completePackageUpload(token: string, uploadSessionId: string) {
  return apiRequest<PackageResponse>(`/package-uploads/${uploadSessionId}/complete`, { method: "POST", token });
}

export function abortPackageUpload(token: string, uploadSessionId: string) {
  return apiRequest<void>(`/package-uploads/${uploadSessionId}/abort`, { method: "POST", token });
}

export function putPackageFile({
  token,
  uploadUrl,
  uploadSessionId,
  file,
  onProgress,
}: {
  token: string;
  uploadUrl?: string | null;
  uploadSessionId: string;
  file: File;
  onProgress?: (progress: UploadProgress) => void;
}): { promise: Promise<void>; abort: () => void } {
  const portalUpload = !uploadUrl || isPortalUploadUrl(uploadUrl);
  const url = portalUpload ? `${API_BASE_URL}/package-uploads/${uploadSessionId}/bytes` : resolveUploadUrl(uploadUrl);
  const body = portalUpload ? multipartBody(file) : file;

  const xhr = new XMLHttpRequest();
  const promise = new Promise<void>((resolve, reject) => {
    xhr.open("PUT", url);
    if (portalUpload) {
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    } else if (file.type) {
      xhr.setRequestHeader("Content-Type", file.type);
    }
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      onProgress?.({
        loaded: event.loaded,
        total: event.total,
        percent: Math.round((event.loaded / event.total) * 100),
      });
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress?.({ loaded: file.size, total: file.size, percent: 100 });
        resolve();
        return;
      }
      reject(new Error(xhrErrorMessage(xhr)));
    };
    xhr.onerror = () => reject(new Error("Falha de rede durante o envio do pacote."));
    xhr.onabort = () => reject(new Error("Envio cancelado."));
    xhr.send(body);
  });

  return { promise, abort: () => xhr.abort() };
}

function multipartBody(file: File): FormData {
  const formData = new FormData();
  formData.append("file", file, file.name);
  return formData;
}

function resolveUploadUrl(uploadUrl: string): string {
  if (/^https?:\/\//i.test(uploadUrl)) return uploadUrl;
  if (uploadUrl.startsWith("/api/")) return `${new URL(API_BASE_URL).origin}${uploadUrl}`;
  if (uploadUrl.startsWith("/")) return `${API_BASE_URL}${uploadUrl}`;
  return uploadUrl;
}

function isPortalUploadUrl(uploadUrl?: string | null): boolean {
  if (!uploadUrl) return true;
  if (uploadUrl.startsWith("/")) return true;
  try {
    const api = new URL(API_BASE_URL);
    const target = new URL(uploadUrl);
    return api.origin === target.origin && target.pathname.includes("/package-uploads/");
  } catch {
    return false;
  }
}

function xhrErrorMessage(xhr: XMLHttpRequest): string {
  if (!xhr.responseText) return `Falha no upload (${xhr.status}).`;
  try {
    const parsed = JSON.parse(xhr.responseText) as { detail?: string; error?: { message?: string } };
    return parsed.error?.message ?? parsed.detail ?? `Falha no upload (${xhr.status}).`;
  } catch {
    return xhr.responseText;
  }
}

