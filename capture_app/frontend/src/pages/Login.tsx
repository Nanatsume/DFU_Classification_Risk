import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'

/* ?next= มาจาก query string ล้วนๆ — ใครก็แก้ URL ใส่ค่าอะไรก็ได้ ถ้าเอาไปยัด location.href/
   location.replace() ตรงๆ โดยไม่กรอง ค่าอย่าง "javascript:...” จะรันโค้ดในหน้าเว็บนี้ทันที (คนละ
   กรณีกับพิมพ์ javascript: เองใน address bar ซึ่งเบราว์เซอร์บล็อก — นี่คือ navigation ที่ยิงจาก
   JS ของหน้าเอง เบราว์เซอร์ไม่บล็อกให้) จำกัดให้ผ่านได้เฉพาะชื่อไฟล์หน้าในแอปเรา ต่อท้ายด้วย query
   string ได้ ไม่มี scheme (":") หรือ "//" ปนอยู่เด็ดขาด — ตรงกับรูปแบบที่ AuthGuard เป็นคนสร้างค่านี้
   ขึ้นมาเองอยู่แล้ว (lib/auth.tsx: location.pathname.split('/').pop() + location.search) */
function safeNext(raw: string | null): string {
  if (raw && /^[a-zA-Z0-9_-]+\.html(\?[^\s]*)?$/.test(raw)) return raw
  return 'index.html'
}

export default function Login() {
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // already logged in? skip straight through instead of showing the form again
  useEffect(() => {
    ;(async () => {
      try {
        const s = await api<{ authenticated: boolean }>('/api/session')
        if (s.authenticated) {
          location.replace(safeNext(new URLSearchParams(location.search).get('next')))
        }
      } catch {
        /* server unreachable — just show the form */
      }
    })()
  }, [])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErr('')
    setSubmitting(true)
    try {
      await api('/api/login', { password })
      location.href = safeNext(new URLSearchParams(location.search).get('next'))
    } catch (ex) {
      setErr(
        ex instanceof ApiError && ex.status === 401
          ? 'รหัสผ่านไม่ถูกต้อง'
          : 'เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ — ตรวจสอบว่า capture server รันอยู่',
      )
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-5">
      <Card className="w-full max-w-sm text-center">
        <CardContent className="pt-2">
          <div className="mb-2.5 text-4xl">🦶</div>
          <h1 className="mb-1 text-[17px] leading-snug font-bold">
            ระบบเก็บข้อมูลความเสี่ยงเท้าเบาหวาน
          </h1>
          <p className="text-muted-foreground mb-5 text-xs">
            โรงพยาบาลพุทธชินราช พิษณุโลก · คณะเทคโนโลยีสารสนเทศและการสื่อสาร มหาวิทยาลัยมหิดล
          </p>
          <form onSubmit={onSubmit} className="space-y-3 text-left">
            <Input
              type="password"
              placeholder="รหัสผ่านทีม"
              autoComplete="current-password"
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <div className="text-destructive min-h-[1.2em] text-xs">{err}</div>
            <Button type="submit" className="w-full" size="lg" disabled={submitting}>
              เข้าสู่ระบบ
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
