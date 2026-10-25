export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

type Body = Record<string, unknown> | unknown[] | FormData | undefined;

/** Every call goes to the same origin; writes carry the header the server requires (CSRF guard). */
export async function api<T = any>(path: string, method = "GET", body?: Body): Promise<T> {
  const headers: Record<string, string> = {};
  if (method !== "GET") headers["X-Requested-With"] = "timelog";
  const multipart = typeof FormData !== "undefined" && body instanceof FormData;
  if (body !== undefined && !multipart) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(path, { method, headers, credentials: "same-origin", body: body === undefined ? undefined : multipart ? body as FormData : JSON.stringify(body) });
  } catch {
    throw new ApiError("ارتباط با سرور برقرار نشد", 0);
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    if (res.status === 401 && typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login/";
    }
    throw new ApiError(data.error || "خطا", res.status);
  }
  const type = res.headers.get("content-type") || "";
  return (type.includes("application/json") ? res.json() : (res as any)) as T;
}

export const get = <T = any>(path: string) => api<T>(path);
export const post = <T = any>(path: string, body?: Body) => api<T>(path, "POST", body ?? {});
export const put = <T = any>(path: string, body?: Body) => api<T>(path, "PUT", body ?? {});
export const del = <T = any>(path: string) => api<T>(path, "DELETE");

/** SWR fetcher. */
export const fetcher = (path: string) => get(path);

export function errorText(e: unknown): string {
  return e instanceof Error ? e.message : "خطا";
}
