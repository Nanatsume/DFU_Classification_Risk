/* Shared navbar — ported from static/js/nav.js. Present at the top of every protected page
   (rendered by AuthGuard). Highlights the active link, shows LIVE/DEMO from /api/health, and
   the logout button. */

import { useEffect, useState } from 'react'
import { probeMode } from '@/lib/api'
import { logout } from '@/lib/auth'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

const LINKS = [
  { href: 'index.html', label: 'หน้าแรก' },
  { href: 'crf-form.html', label: 'กรอกฟอร์มใหม่' },
  { href: 'crf-list.html', label: 'ประวัติการบันทึก' },
  { href: 'capture.html', label: 'ถ่ายภาพ' },
]

// the detail page highlights the list tab, same as before
const ALIAS: Record<string, string> = { 'crf-detail.html': 'crf-list.html' }

export function Navbar() {
  const [mode, setMode] = useState<'checking' | 'live' | 'demo'>('checking')
  const [simulated, setSimulated] = useState(false)

  useEffect(() => {
    let cancelled = false
    probeMode().then(({ live, health }) => {
      if (cancelled) return
      setMode(live ? 'live' : 'demo')
      setSimulated(live && health?.source === 'SimulatedSource')
    })
    return () => {
      cancelled = true
    }
  }, [])

  const here = location.pathname.split('/').pop() || 'index.html'
  const active = ALIAS[here] || here

  return (
    <nav className="bg-sidebar text-sidebar-foreground border-b-[3px] border-primary">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-1.5 px-4 py-2.5">
        <span className="mr-3.5 text-sm font-bold text-white whitespace-nowrap">
          🦶 DFU Data Collection
        </span>
        {LINKS.map((l) => (
          <a
            key={l.href}
            href={l.href}
            className={
              'rounded-md px-3 py-1.5 text-[13px] no-underline transition-colors ' +
              (active === l.href
                ? 'bg-primary text-white'
                : 'text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-white')
            }
          >
            {l.label}
          </a>
        ))}
        <span className="flex-1" />
        {mode !== 'checking' && (
          <Badge
            variant="outline"
            className={
              'mr-1 border-0 text-[10px] tracking-wider uppercase ' +
              (mode === 'live'
                ? 'bg-emerald-900/60 text-emerald-200'
                : 'bg-amber-900/60 text-amber-200')
            }
          >
            {mode === 'live' ? `LIVE${simulated ? ' · กล้องจำลอง' : ''}` : 'DEMO'}
          </Badge>
        )}
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="border-sidebar-border bg-transparent text-sidebar-foreground hover:bg-sidebar-accent hover:text-white"
          onClick={logout}
        >
          ออกจากระบบ
        </Button>
      </div>
    </nav>
  )
}
