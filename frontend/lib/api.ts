import "server-only";

// The API key lives only on the server. The browser never sees it, and never
// calls the backend directly: all requests go through server components/actions.
const API_URL = process.env.API_URL ?? "http://localhost:8000";
const API_KEY = process.env.API_KEY ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      cache: "no-store",
      headers: { "Content-Type": "application/json", "X-API-Key": API_KEY, ...(init.headers ?? {}) },
      signal: AbortSignal.timeout(45_000),
    });
  } catch {
    throw new ApiError(0, "The data service is unreachable.");
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {}
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export async function safe<T>(p: Promise<T>): Promise<{ data: T | null; error: ApiError | null }> {
  try {
    return { data: await p, error: null };
  } catch (e) {
    return { data: null, error: e instanceof ApiError ? e : new ApiError(0, "Unexpected error") };
  }
}
