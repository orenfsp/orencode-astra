export const API_BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "http://127.0.0.1:8002";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

function csrfToken(): string {
  return document.cookie.split("; ").find((value) => value.startsWith("fsp_csrf="))?.split("=").slice(1).join("=") ?? "";
}

function describe(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    // Ошибки валидации FastAPI: берём человекочитаемые сообщения.
    return detail.map((item: { msg?: string }) => (item.msg ?? "").replace(/^Value error, /, "")).filter(Boolean).join("; ");
  }
  return `Сервер ответил с кодом ${status}`;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const isForm = init.body instanceof FormData;
  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init.body && !isForm ? { "Content-Type": "application/json" } : {}),
      ...(!["GET", "HEAD", "OPTIONS"].includes(method) ? { "X-CSRF-Token": csrfToken() } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    throw new ApiError(describe(body?.detail, response.status), response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

export function errorText(reason: unknown, fallback = "Операция не выполнена"): string {
  return reason instanceof Error && reason.message ? reason.message : fallback;
}

/** Ссылка на файл, который отдаёт API (документы .docx и .xlsx); cookie сессии уходят вместе с переходом. */
export function fileUrl(path: string): string {
  return `${API_BASE}/api/v1${path}`;
}
