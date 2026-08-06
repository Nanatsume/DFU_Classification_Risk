/* Shared session guard — included on every protected page, right after js/api.js.
   Hides the page until /api/session confirms an authenticated cookie; redirects to login.html
   otherwise. This is a client-side gate only — the real protection is server-side (every
   data-bearing endpoint requires the same cookie regardless of what this script does), see
   auth.py's module docstring for the full reasoning. */

document.documentElement.style.visibility = 'hidden';

(async function guardPage() {
  let authenticated = false;
  try {
    const s = await api('/api/session');
    authenticated = !!s.authenticated;
  } catch (e) {
    authenticated = false;
  }
  if (!authenticated) {
    const next = encodeURIComponent(location.pathname.split('/').pop() + location.search);
    location.replace('login.html?next=' + next);
    return;
  }
  document.documentElement.style.visibility = 'visible';
})();

async function logout() {
  try { await api('/api/logout', {}); } catch (e) { /* clear cookie anyway on the server side */ }
  location.href = 'login.html';
}
