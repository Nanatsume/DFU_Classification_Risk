import { useEffect, useState } from 'react'
import { api, ApiError } from '@/lib/api'
import type { CaseRow, CommitRecord, ManifestRow, Modality } from '@/lib/captureTypes'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const RECORDS_KEY = 'capture_records'

const DEMO_CASES: CaseRow[] = [
  { research_id: 'P0001', nurse: 'พว. สมหญิง ใจดี', iwgdf: { L: 2, R: 1 }, has_podo: false, has_thermal: false },
  { research_id: 'P0002', nurse: 'พว. อรุณี ศรีสุข', iwgdf: { L: 0, R: 0 }, has_podo: false, has_thermal: false },
]

const pad = (n: number, l: number) => String(n).padStart(l, '0')
function nowISO() {
  const d = new Date()
  const z = (n: number) => pad(n, 2)
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}:${z(d.getSeconds())}+07:00`
}
const timeTH = (iso: string) => iso.slice(11, 19)

function drawSim(modality: Modality, rid: string): string {
  const cv = document.createElement('canvas')
  cv.width = 640
  cv.height = 480
  const x = cv.getContext('2d')!
  if (modality === 'podoscope') {
    x.fillStyle = '#0b0f16'
    x.fillRect(0, 0, 640, 480)
    x.strokeStyle = 'rgba(80,110,150,.18)'
    for (let i = 0; i <= 640; i += 32) { x.beginPath(); x.moveTo(i, 0); x.lineTo(i, 480); x.stroke() }
    for (let j = 0; j <= 480; j += 32) { x.beginPath(); x.moveTo(0, j); x.lineTo(640, j); x.stroke() }
    x.fillStyle = 'rgba(90,130,180,.28)'
    ;[[250, 240], [390, 240]].forEach(([cx, cy]) => { x.beginPath(); x.ellipse(cx, cy, 46, 120, 0, 0, 7); x.fill() })
    x.fillStyle = 'rgba(150,180,215,.85)'
    x.font = '600 22px sans-serif'
    x.textAlign = 'center'
    x.fillText('PODOSCOPE', 320, 60)
  } else {
    const g = x.createRadialGradient(320, 240, 20, 320, 240, 320)
    g.addColorStop(0, '#f7e94b'); g.addColorStop(.35, '#e8802f'); g.addColorStop(.7, '#8c2f6b'); g.addColorStop(1, '#141a4a')
    x.fillStyle = g
    x.fillRect(0, 0, 640, 480)
    x.fillStyle = '#fff'
    x.font = '600 22px sans-serif'
    x.textAlign = 'center'
    x.fillText('THERMAL (จำลอง)', 320, 60)
  }
  x.fillStyle = 'rgba(255,255,255,.9)'
  x.font = '400 15px monospace'
  x.textAlign = 'left'
  x.fillText(rid + '  ' + timeTH(nowISO()), 16, 462)
  return cv.toDataURL('image/png')
}

const loadRecords = (): CommitRecord[] => {
  try { return JSON.parse(localStorage.getItem(RECORDS_KEY) || '[]') } catch { return [] }
}
const saveRecords = (r: CommitRecord[]) => localStorage.setItem(RECORDS_KEY, JSON.stringify(r))

interface DisplayRow {
  research_id: string
  captured_at: string
  status: string
  podo: boolean
  prepro: boolean
  thermal: boolean
  rec: CommitRecord | ManifestRow
}
function toDisplay(x: CommitRecord | ManifestRow): DisplayRow {
  if ('podoscope' in x) {
    return {
      research_id: x.research_id, captured_at: x.captured_at, status: x.status,
      podo: !!x.podoscope.raw, prepro: !!x.podoscope.preprocessing, thermal: !!x.thermal?.image, rec: x,
    }
  }
  return {
    research_id: x.research_id, captured_at: x.captured_at, status: x.status,
    podo: !!x.podo_raw, prepro: x.podo_prepro === 'yes', thermal: !!x.thermal, rec: x,
  }
}

export default function Capture() {
  const [mode, setMode] = useState<'checking' | 'live' | 'demo'>('checking')
  const [cases, setCases] = useState<CaseRow[]>([])
  const [session, setSession] = useState<{ rid: string; startedAt: string; caseInfo: CaseRow | null } | null>(null)
  const [shots, setShots] = useState<Record<Modality, boolean>>({ podoscope: false, thermal: false })
  const [previews, setPreviews] = useState<Record<Modality, string | null>>({ podoscope: null, thermal: null })
  const [operator, setOperator] = useState('')
  const [qc, setQc] = useState<{ status: 'idle' | 'running' | 'ok' | 'failed'; left?: string; right?: string; error?: string }>({ status: 'idle' })
  const [saved, setSaved] = useState<DisplayRow[]>([])
  const [modalRec, setModalRec] = useState<unknown>(null)
  const [justCommittedRid, setJustCommittedRid] = useState<string | null>(null)

  function iwgdfText(c: CaseRow) {
    return `IWGDF ซ้าย ${c.iwgdf?.L ?? '—'} · ขวา ${c.iwgdf?.R ?? '—'}`
  }
  const findCase = (rid: string) => cases.find((c) => c.research_id === rid)
  const pendingCases = () => cases.filter((c) => !(c.has_podo && c.has_thermal))

  async function refreshSaved(liveMode: boolean) {
    let items: DisplayRow[]
    if (liveMode) {
      try { items = (await api<ManifestRow[]>('/api/manifest')).slice().reverse().map(toDisplay) }
      catch { items = [] }
    } else {
      items = loadRecords().map(toDisplay)
    }
    setSaved(items)
  }
  async function refreshCasesAndPicker(liveMode: boolean) {
    if (liveMode) {
      try { setCases(await api<CaseRow[]>('/api/cases')) } catch { /* keep previous */ }
    }
  }

  useEffect(() => {
    ;(async () => {
      let liveMode = false
      try {
        await api('/api/health')
        liveMode = true
        setMode('live')
        try { setCases(await api<CaseRow[]>('/api/cases')) } catch { setCases([]) }
      } catch {
        setMode('demo')
        setCases(DEMO_CASES)
      }
      await refreshSaved(liveMode)
      const urlRid = new URLSearchParams(location.search).get('rid')
      if (urlRid) startSession(urlRid, liveMode)
      // eslint-disable-next-line react-hooks/exhaustive-deps
    })()
  }, [])

  async function startSession(rid: string, liveMode: boolean) {
    if (!rid) return
    let info = findCase(rid)
    if (!info && liveMode) {
      try { const fresh = await api<CaseRow[]>('/api/cases'); setCases(fresh); info = fresh.find((c) => c.research_id === rid) } catch { /* ignore */ }
    }
    setSession({ rid, startedAt: nowISO(), caseInfo: info || null })
    setShots({ podoscope: false, thermal: false })
    setPreviews({ podoscope: null, thermal: null })
    setQc({ status: 'idle' })
  }

  async function capture(m: Modality) {
    if (!session) return
    let src: string
    if (mode === 'live') {
      try {
        const res = await api<{ url: string }>('/api/capture', { rid: session.rid, modality: m })
        src = res.url + '?t=' + Date.now()
      } catch (e) {
        if (e instanceof ApiError && e.status === 409) {
          alert('เคส ' + session.rid + ' ยังไม่มีแบบฟอร์ม CRF — กรอกฟอร์มก่อนจึงจะถ่ายภาพได้')
          return
        }
        throw e
      }
    } else {
      src = drawSim(m, session.rid)
    }
    setShots((s) => ({ ...s, [m]: true }))
    setPreviews((p) => ({ ...p, [m]: src }))
    if (m === 'podoscope' && mode === 'live') runPreprocess(session.rid)
  }
  function retake(m: Modality) {
    setShots((s) => ({ ...s, [m]: false }))
    setPreviews((p) => ({ ...p, [m]: null }))
    if (m === 'podoscope') setQc({ status: 'idle' })
  }

  async function runPreprocess(rid: string) {
    setQc({ status: 'running' })
    try {
      const res = await api<{ status: string; left_url?: string; right_url?: string; error?: string }>('/api/preprocess', { rid })
      if (res.status === 'ok') {
        setQc({ status: 'ok', left: res.left_url + '?t=' + Date.now(), right: res.right_url + '?t=' + Date.now() })
      } else {
        setQc({ status: 'failed', error: res.error })
      }
    } catch (e) {
      setQc({ status: 'failed', error: e instanceof Error ? e.message : String(e) })
    }
  }

  async function commit() {
    if (!session) return
    const rid = session.rid
    let rec: CommitRecord
    if (mode === 'live') {
      rec = await api<CommitRecord>('/api/commit', { rid, operator })
    } else {
      const prepro = shots.podoscope ? { L: `${rid}_podo_L.png`, R: `${rid}_podo_R.png` } : null
      rec = {
        schema_version: 'demo', research_id: rid, captured_at: nowISO(), operator,
        podoscope: { raw: `${rid}_podo.png`, preprocessing: prepro },
        thermal: { image: `${rid}_thermal.png`, radiometric: null },
        status: 'complete', app_version: 'demo',
      }
      const recs = loadRecords(); recs.unshift(rec); saveRecords(recs)
    }
    setJustCommittedRid(rid)
    setSession(null)
    setOperator('')
    await refreshSaved(mode === 'live')
    await refreshCasesAndPicker(mode === 'live')
  }

  async function showModalFor(row: DisplayRow) {
    let r: unknown = row.rec
    if (!('podoscope' in (r as object)) && mode === 'live') {
      try { r = await (await fetch('/api/file/meta/' + row.research_id + '.json')).json() } catch { /* keep row */ }
    }
    setModalRec(r)
  }

  const chk = (b: boolean) => (b ? <span className="text-cat-0">✓</span> : <span className="text-muted-foreground">—</span>)
  const nShots = (shots.podoscope ? 1 : 0) + (shots.thermal ? 1 : 0)

  return (
    <div className="mx-auto max-w-[1600px] px-4 py-6">
      <div className="mb-5 flex items-center gap-3.5">
        <div className="bg-primary flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-2xl text-white">🦶</div>
        <div>
          <h1 className="text-[17px] font-bold">ถ่ายภาพเก็บข้อมูล (Podoscope + Thermal)</h1>
          <div className="text-muted-foreground text-[11.5px]">โรงพยาบาลพุทธชินราช พิษณุโลก · คณะ ICT มหาวิทยาลัยมหิดล</div>
        </div>
      </div>

      {!session ? (
        <Card className="mb-4.5 p-5 text-center">
          <p className="text-muted-foreground mb-4 text-sm">เลือกเคสที่กรอกแบบฟอร์ม CRF แล้วและยังไม่ได้ถ่ายภาพ</p>
          {mode === 'checking' ? (
            <div className="text-muted-foreground text-sm">กำลังตรวจสอบ…</div>
          ) : pendingCases().length === 0 ? (
            <div className="text-muted-foreground text-[12.5px] italic">
              ยังไม่มีเคสที่กรอกฟอร์มรอถ่ายภาพ — เปิดแบบฟอร์ม CRF เพื่อลงทะเบียนเคสใหม่ก่อน
            </div>
          ) : (
            <div className="mx-auto max-w-lg space-y-2 text-left">
              {pendingCases().map((c) => (
                <div key={c.research_id} className="bg-secondary flex items-center gap-3 rounded-md border px-3.5 py-2.5">
                  <span className="text-primary font-mono font-bold">{c.research_id}</span>
                  <span className="text-muted-foreground flex-1 text-[11.5px]">{c.nurse || '—'} · {iwgdfText(c)}</span>
                  <Button size="sm" onClick={() => startSession(c.research_id, mode === 'live')}>ถ่ายภาพเคสนี้</Button>
                </div>
              ))}
            </div>
          )}
          <p className="mt-3.5">
            <a href="crf-form.html" target="_blank" rel="noreferrer" className="text-primary text-[11.5px] font-semibold hover:underline">
              เปิดแบบฟอร์ม CRF เพื่อลงทะเบียนเคสใหม่ →
            </a>
          </p>
        </Card>
      ) : (
        <>
          <Card className="mb-4.5 p-5">
            <div className="flex flex-wrap items-center gap-5">
              <div className="flex flex-col gap-0.5">
                <span className="text-muted-foreground text-[10px] font-bold tracking-[0.12em] uppercase">Research ID</span>
                <span className="text-primary font-mono text-3xl font-extrabold">{session.rid}</span>
              </div>
              <div className="bg-cat-1/10 text-cat-1 rounded-md border border-current/30 px-3.5 py-2 text-xs">
                {session.caseInfo
                  ? `${session.caseInfo.nurse || '—'} · ${iwgdfText(session.caseInfo)} — ตรวจสอบว่าเป็นผู้ป่วยคนถูกก่อนถ่าย`
                  : 'ไม่พบข้อมูลฟอร์มของเคสนี้ในรายการ — ตรวจสอบรหัสให้ตรงกับแบบฟอร์มก่อนถ่าย'}
              </div>
              <label className="text-muted-foreground flex items-center gap-2 text-[12.5px]">
                ผู้ถ่ายภาพ
                <Input value={operator} onChange={(e) => setOperator(e.target.value)} placeholder="ชื่อผู้ถ่าย" className="h-8 w-40" />
              </label>
              <div className="text-muted-foreground ml-auto text-right text-[11.5px]">
                เริ่ม {timeTH(session.startedAt)}<br />1 คน = 1 podoscope + 1 thermal
              </div>
            </div>
          </Card>

          <div className="mb-4.5 grid grid-cols-1 gap-4.5 sm:grid-cols-2">
            {(['podoscope', 'thermal'] as Modality[]).map((m) => (
              <Card key={m} className="overflow-hidden p-0">
                <div className="flex items-center gap-2.5 border-b px-4 py-3">
                  <span className={'h-2.5 w-2.5 rounded-full ' + (m === 'podoscope' ? 'bg-blue-600' : 'bg-orange-600')} />
                  <h3 className="text-sm font-bold">{m === 'podoscope' ? 'Podoscope' : 'Thermal'}</h3>
                  <span className="text-muted-foreground text-[11px]">{m === 'podoscope' ? 'ภาพแรงกดฝ่าเท้า' : 'ภาพความร้อน (radiometric)'}</span>
                  <Badge variant={shots[m] ? 'default' : 'secondary'} className="ml-auto">
                    {shots[m] ? '✓ ถ่ายแล้ว' : 'ยังไม่ถ่าย'}
                  </Badge>
                </div>
                <div className="bg-foreground/95 relative flex aspect-[4/3] items-center justify-center overflow-hidden">
                  {previews[m] ? (
                    <img src={previews[m]!} alt="" className="h-full w-full object-contain" />
                  ) : (
                    <div className="text-center text-[12.5px] text-white/40">
                      <span className="mb-2 block text-3xl opacity-50">{m === 'podoscope' ? '📷' : '🌡️'}</span>
                      กดปุ่มด้านล่างเพื่อถ่าย
                    </div>
                  )}
                </div>
                <div className="flex gap-2 p-3">
                  {!shots[m] ? (
                    <Button className="flex-1" onClick={() => capture(m)}>ถ่ายภาพ</Button>
                  ) : (
                    <Button variant="outline" className="flex-1" onClick={() => retake(m)}>ถ่ายใหม่</Button>
                  )}
                </div>
              </Card>
            ))}
          </div>

          {qc.status !== 'idle' && (
            <Card className="mb-4.5 p-5">
              <div className="mb-3 flex flex-wrap items-center gap-2.5">
                <h4 className="text-muted-foreground text-xs font-bold tracking-[0.03em] uppercase">
                  Preprocessing (QC) — เท้าซ้าย / ขวา
                </h4>
                <span className="text-muted-foreground text-xs">
                  {qc.status === 'running' && 'กำลังประมวลผล... (segment + แยกซ้าย-ขวา + CLAHE)'}
                  {qc.status === 'ok' && '✓ แยกซ้าย-ขวาสำเร็จ — ตรวจว่าเท้าติดครบและแยกถูก'}
                  {qc.status === 'failed' && <span className="text-destructive">✗ preprocessing ล้มเหลว: {qc.error || ''} — ควรถ่ายใหม่</span>}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4.5">
                {(['L', 'R'] as const).map((side) => (
                  <Card key={side} className="overflow-hidden p-0">
                    <div className="flex items-center gap-2.5 border-b px-4 py-3">
                      <span className="h-2.5 w-2.5 rounded-full bg-blue-600" />
                      <h3 className="text-sm font-bold">{side === 'L' ? 'ซ้าย (L)' : 'ขวา (R)'}</h3>
                    </div>
                    <div className="bg-foreground/95 flex aspect-square items-center justify-center overflow-hidden">
                      {qc.status === 'running' && <span className="text-2xl text-white/60">⏳</span>}
                      {qc.status === 'failed' && <span className="text-2xl text-white/60">✗</span>}
                      {qc.status === 'ok' && (
                        <img src={side === 'L' ? qc.left : qc.right} alt="" className="h-full w-full object-contain" />
                      )}
                    </div>
                  </Card>
                ))}
              </div>
            </Card>
          )}

          <Card className="mb-4.5 flex flex-wrap items-center gap-4 p-5">
            <div className="text-muted-foreground text-sm">ถ่ายแล้ว <b className="text-foreground">{nShots} / 2</b> ส่วน</div>
            <Button className="ml-auto" disabled={nShots !== 2} onClick={commit}>✓ ยืนยันและบันทึก</Button>
          </Card>
        </>
      )}

      <Card className="p-5">
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <h4 className="font-bold">เคสที่บันทึกแล้ว</h4>
          <span className="text-muted-foreground text-xs">ถ่ายภาพแล้ว {saved.length} เคส</span>
        </div>
        {saved.length === 0 ? (
          <div className="text-muted-foreground text-[12.5px] italic">ยังไม่มีเคสที่บันทึก</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="text-muted-foreground text-left text-[10.5px] font-bold uppercase">
                  <th className="border-b py-2 pr-2">Research ID</th>
                  <th className="border-b py-2 pr-2">เวลา</th>
                  <th className="border-b py-2 pr-2">ไฟล์</th>
                  <th className="border-b py-2 pr-2">สถานะ</th>
                  <th className="border-b py-2" />
                </tr>
              </thead>
              <tbody>
                {saved.map((it) => (
                  <tr key={it.research_id + it.captured_at}>
                    <td className="border-b py-2 pr-2 font-mono">{it.research_id}</td>
                    <td className="border-b py-2 pr-2">{timeTH(it.captured_at)}</td>
                    <td className="border-b py-2 pr-2 text-[11.5px]">
                      podo {chk(it.podo)} · prepro {chk(it.prepro)} · thermal {chk(it.thermal)}
                    </td>
                    <td className="border-b py-2 pr-2">
                      <Badge variant={it.status === 'complete' ? 'default' : 'secondary'}>
                        {it.status === 'complete' ? 'ครบ' : 'ไม่ครบ'}
                      </Badge>
                    </td>
                    <td className="border-b py-2">
                      <button className="text-primary text-[11.5px] font-semibold hover:underline" onClick={() => showModalFor(it)}>
                        ดู JSON
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Dialog open={modalRec !== null} onOpenChange={(open) => !open && setModalRec(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>รายละเอียด (JSON)</DialogTitle>
          </DialogHeader>
          <pre className="bg-foreground max-h-96 overflow-auto rounded-lg p-4 font-mono text-[11.5px] text-white/90">
            {JSON.stringify(modalRec, null, 2)}
          </pre>
        </DialogContent>
      </Dialog>

      {/* หลังยืนยันและบันทึกเสร็จ ถามว่าจะกลับหน้าหลัก หรือไปทำ ROI ของเคสนี้ต่อเลย — preprocessing
          รันไปแล้วตอนถ่าย podoscope เสร็จ ภาพ ROI พร้อมใช้อยู่แล้วตอนนี้ */}
      <Dialog open={justCommittedRid !== null} onOpenChange={(open) => !open && setJustCommittedRid(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>บันทึกเคส {justCommittedRid} สำเร็จ</DialogTitle>
          </DialogHeader>
          <p className="text-muted-foreground -mt-2 mb-1 text-[13px]">จะกลับหน้าหลัก หรือทำ ROI ของเคสนี้ต่อเลย?</p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => { location.href = 'index.html' }}>
              กลับหน้าหลัก
            </Button>
            <Button
              onClick={() => {
                const rid = justCommittedRid!
                setJustCommittedRid(null)
                window.open('via/index.html?rid=' + encodeURIComponent(rid), '_blank')
              }}
            >
              ทำ ROI ต่อ →
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
