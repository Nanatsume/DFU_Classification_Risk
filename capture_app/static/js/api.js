/* Shared fetch helper + LIVE/DEMO mode probe — used by every page. Dedupes the near-identical
   api()/probeServer() pairs that used to live separately in crf.html and index.html. */

async function api(path, body, method) {
  const opt = body !== undefined
    ? { method: method || 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
    : { method: method || 'GET' };
  const res = await fetch(path, opt);
  if (!res.ok) {
    const e = new Error(path + ' -> ' + res.status);
    e.status = res.status;
    throw e;
  }
  return res.json();
}

/* Detects LIVE (server reachable + session valid) vs DEMO (server unreachable) — auth.js already
   handles the "reachable but not logged in" case by redirecting to login.html before this runs,
   so by the time probeMode() is called on a protected page, a non-ok /api/health basically means
   "no server at all" (e.g. crf.html/capture.html opened as a plain file). */
async function probeMode() {
  try {
    const h = await api('/api/health');
    return { live: true, health: h };
  } catch (e) {
    return { live: false, health: null };
  }
}
