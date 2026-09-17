/* Hardware smoke test, deliberately outside the patient flow. Staff wants to confirm the
   podoscope still fires — after a reboot, after replugging it, before a patient sits down —
   without going through /api/session/start (which issues a research id and creates a row in
   `cases`). Shots taken here go through POST /api/camera-test/capture, which uses the same
   SOURCE.grab() as a real capture but writes under camera-test/ (see server_paths.camera_test_dir)
   rather than podo/ — never a case, never in the manifest, never uploaded by tools/backup.py. */

import { useEffect, useState } from 'react'
import { api, ApiError } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

type CameraStatus = {
  mode: 'usb' | 'sim'
  connected: boolean
  name: string | null
  devices: string[]
  error: string | null
}

function StatusStrip({ status }: { status: CameraStatus | null }) {
  if (!status) return null
  const ok = status.mode === 'usb' && status.connected
  const tone =
    status.mode === 'sim' ? { bg: 'bg-cat-2/10', border: 'border-l-cat-2', text: 'text-cat-2', dot: 'bg-cat-2' }
    : ok ? { bg: 'bg-cat-0/10', border: 'border-l-cat-0', text: 'text-cat-0', dot: 'bg-cat-0' }
    : { bg: 'bg-destructive/10', border: 'border-l-destructive', text: 'text-destructive', dot: 'bg-destructive' }
  const headline =
    status.mode === 'sim' ? 'โหมดจำลอง — ไม่ได้ใช้กล้องจริง (ตั้งค่าจาก CAPTURE_SOURCE ของเซิร์ฟเวอร์)'
    : ok ? `กล้องพร้อมใช้งาน · ${status.name}`
    : 'ยังไม่พบกล้องโพโดสโคป'
  return (
    <div className={`mb-3 rounded-md border border-l-[5px] px-4 py-2.5 ${tone.bg} ${tone.border}`}>
      <span className={`mr-2 inline-block h-2.5 w-2.5 rounded-full ${tone.dot}`} />
      <span className={`text-[13px] font-bold ${tone.text}`}>{headline}</span>
    </div>
  )
}

type Shot = { url: string; name: string }

/** Live MJPEG view, `<img>` pointed at the multipart stream — the server holds one cv2 handle
 *  open for as long as this element exists and releases it the moment the element (and so the
 *  request behind it) goes away, whether that's the toggle below or navigating off the page. The
 *  crosshair is a plain overlay div, independent of the stream itself, for lining the foot up on
 *  the rig the way the OS camera app's own grid does. */
function LiveView() {
  const [state, setState] = useState<'connecting' | 'ok' | 'failed'>('connecting')
  // Bust the cache on mount so toggling off and back on opens a fresh stream rather than an
  // <img> the browser thinks is already loaded.
  const [src] = useState(() => '/api/camera-test/preview?t=' + Date.now())

  return (
    <div className="relative mb-3 aspect-video w-full overflow-hidden rounded-md bg-black">
      <img
        src={src}
        alt="วิดีโอสดจากกล้อง Podoscope"
        className="h-full w-full object-contain"
        onLoad={() => setState('ok')}
        onError={() => setState('failed')}
      />
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute top-0 bottom-0 left-1/2 w-px -translate-x-1/2 bg-white/50" />
        <div className="absolute top-1/2 right-0 left-0 h-px -translate-y-1/2 bg-white/50" />
      </div>
      {state === 'connecting' && (
        <div className="absolute inset-0 flex items-center justify-center text-[12px] text-white/70">
          กำลังเชื่อมต่อวิดีโอสด…
        </div>
      )}
      {state === 'failed' && (
        <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-[12px] text-white/80">
          ต่อวิดีโอสดไม่ได้ — ตรวจว่าอยู่โหมดกล้องจริง (ไม่ใช่โหมดจำลอง)
          และไม่มีโปรแกรมอื่นถือกล้องอยู่ (Logi Capture, OBS, Teams)
        </div>
      )}
    </div>
  )
}

export default function CameraTest() {
  const [status, setStatus] = useState<CameraStatus | null>(null)
  const [shots, setShots] = useState<Shot[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [live, setLive] = useState(false)

  async function checkCamera() {
    try { setStatus(await api<CameraStatus>('/api/camera')) } catch { setStatus(null) }
  }

  // Filenames are unique per shot (Test-<timestamp>.png), so the list itself is the source of
  // truth — no separate in-memory record to fall out of sync with what's actually on disk.
  async function loadShots() {
    try { setShots(await api<Shot[]>('/api/camera-test/list?modality=podoscope')) } catch { /* leave previous list */ }
  }

  useEffect(() => {
    checkCamera()
    loadShots()
    const t = setInterval(checkCamera, 5000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function shoot() {
    setBusy(true)
    setError(null)
    try {
      await api('/api/camera-test/capture', { modality: 'podoscope' })
      await loadShots()
    } catch (e) {
      setError(e instanceof ApiError ? `ถ่ายไม่สำเร็จ (รหัส ${e.status})` : 'ถ่ายไม่สำเร็จ — ตรวจสอบการเชื่อมต่อ')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-[1000px] px-4 py-6">
      <div className="mb-6">
        <h1 className="text-lg font-bold">ทดสอบกล้อง</h1>
        <p className="text-muted-foreground text-[13px] leading-relaxed">
          เช็คว่ากล้องต่อและถ่ายได้จริงเฉยๆ ไม่ผูกกับเคสผู้ป่วย ไม่ออก research id
          และไม่ปนกับข้อมูลจริงในหน้า "ถ่ายภาพเก็บข้อมูล" — ภาพที่ถ่ายที่นี่เก็บแยกไว้ในโฟลเดอร์
          camera-test/ ไม่ถูกใช้เทรนโมเดล แต่ยัง backup ขึ้น OneDrive เหมือนกัน (ทุก 15 นาที)
        </p>
      </div>

      <Card id="podoscope" className="mb-6 border-l-[5px] border-l-[#7c3a66] p-5">
        <div className="text-muted-foreground font-mono text-[11px] tracking-[0.2em]">06 · Podoscope</div>
        <div className="my-2 text-base font-bold text-[#7c3a66]">ทดสอบการถ่าย Podoscope</div>
        <StatusStrip status={status} />

        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => setLive((v) => !v)}>
            {live ? 'ปิดวิดีโอสด' : 'เปิดวิดีโอสด'}
          </Button>
          {live && (
            <span className="text-muted-foreground text-[11.5px]">
              ขณะเปิดวิดีโอสด จะถ่ายภาพเคสผู้ป่วยจริงพร้อมกันไม่ได้ — ปิดวิดีโอสดก่อนไปถ่ายเคสจริง
            </span>
          )}
        </div>
        {live && <LiveView />}

        {error && <p className="mb-2 text-[13px] text-destructive">{error}</p>}
        <Button onClick={shoot} disabled={busy}>{busy ? 'กำลังถ่าย…' : 'ถ่ายทดสอบ'}</Button>
        {shots.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-3">
            {shots.slice(0, 12).map((s) => (
              <a
                key={s.name}
                href={s.url}
                target="_blank"
                rel="noreferrer"
                className="block w-28 shrink-0 overflow-hidden rounded-md border"
              >
                <div className="bg-foreground/95 flex aspect-square items-center justify-center overflow-hidden">
                  <img src={s.url} alt={s.name} className="h-full w-full object-contain" />
                </div>
                <div className="text-muted-foreground truncate px-1 py-1 text-center text-[10px]">{s.name}</div>
              </a>
            ))}
          </div>
        )}
      </Card>

      <Card id="thermal" className="border-l-[5px] border-l-[#4b5563] p-5">
        <div className="text-muted-foreground font-mono text-[11px] tracking-[0.2em]">07 · Thermal</div>
        <div className="my-2 text-base font-bold text-[#4b5563]">ทดสอบการถ่าย Thermal</div>
        <p className="text-muted-foreground text-[13px] leading-relaxed">
          รออุปกรณ์ — กล้องความร้อนยังไม่ได้เชื่อมต่อกับระบบ (รอ SDK จากผู้ผลิต)
          เมนูนี้จะเปิดใช้ถ่ายทดสอบได้เมื่อกล้องมาถึงและต่อ driver เสร็จแล้ว
        </p>
      </Card>
    </div>
  )
}
