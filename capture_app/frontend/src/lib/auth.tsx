/* Shared session guard — wraps every protected page's root. Ported from static/js/auth.js +
   static/js/nav.js: checks GET /api/session, redirects to login.html if not authenticated,
   otherwise renders the Navbar + page content. This is a client-side gate only — the real
   protection is server-side (every data-bearing endpoint requires the same cookie regardless
   of what this component does), see capture_app/auth.py's module docstring. */

import { useEffect, useState, type ReactNode } from 'react'
import { api } from '@/lib/api'
import { Navbar } from '@/components/Navbar'

interface SessionResponse {
  authenticated: boolean
}

export async function logout() {
  try {
    await api('/api/logout', {})
  } catch {
    /* clear cookie anyway happens server-side regardless */
  }
  location.href = 'login.html'
}

export function AuthGuard({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<'checking' | 'authenticated'>('checking')

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      let authenticated = false
      try {
        const s = await api<SessionResponse>('/api/session')
        authenticated = !!s.authenticated
      } catch {
        authenticated = false
      }
      if (cancelled) return
      if (!authenticated) {
        const next = encodeURIComponent(
          location.pathname.split('/').pop() + location.search,
        )
        location.replace('login.html?next=' + next)
        return
      }
      setStatus('authenticated')
    })()
    return () => {
      cancelled = true
    }
  }, [])

  if (status === 'checking') return null // avoids a flash of protected content pre-check

  return (
    <>
      <Navbar />
      {children}
    </>
  )
}
