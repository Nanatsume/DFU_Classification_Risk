/* Shared fetch helper + LIVE/DEMO mode probe — ported from static/js/api.js.
   Every page's data fetching goes through this so the fetch/error-shape stays identical
   across pages (and identical to what the earlier vanilla-JS pages already did). */

export class ApiError extends Error {
  status: number
  constructor(path: string, status: number) {
    super(`${path} -> ${status}`)
    this.status = status
  }
}

export async function api<T = unknown>(
  path: string,
  body?: unknown,
  method?: string,
): Promise<T> {
  const opt: RequestInit =
    body !== undefined
      ? {
          method: method || 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }
      : { method: method || 'GET' }
  const res = await fetch(path, opt)
  if (!res.ok) throw new ApiError(path, res.status)
  return res.json() as Promise<T>
}

export interface HealthResponse {
  ok: boolean
  source: string
  next_id: string
  count: number
  crf_count: number
}

/* Detects LIVE (server reachable) vs DEMO (server unreachable, e.g. static files opened without
   the FastAPI backend running). AuthGuard already handles "reachable but not logged in" by
   redirecting to /login.html before a page's own content ever calls this. */
export async function probeMode(): Promise<
  { live: true; health: HealthResponse } | { live: false; health: null }
> {
  try {
    const health = await api<HealthResponse>('/api/health')
    return { live: true, health }
  } catch {
    return { live: false, health: null }
  }
}
