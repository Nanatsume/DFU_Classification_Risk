/* Hardware smoke test, deliberately outside the patient flow. Staff wants to confirm the
   podoscope still fires — after a reboot, after replugging it, before a patient sits down —
   without going through /api/session/start (which issues a research id and creates a row in
   `cases`). Shots taken here go through POST /api/camera-test/capture, which uses the same
   SOURCE.grab() as a real capture but writes under camera-test/ (see server_paths.camera_test_dir)
   rather than podo/ — never a case, never in the manifest, never uploaded by tools/backup.py. */

import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { PodoscopeLiveView } from '@/components/PodoscopeLiveView'

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

type CameraSettings = {
  auto_exposure: boolean
  exposure: number
  auto_focus: boolean
  focus: number
  auto_wb: boolean
  wb_temperature: number
  brightness: number
  contrast: number
  saturation: number
  gain: number
}

const SETTINGS_DEFAULTS: CameraSettings = {
  auto_exposure: true, exposure: -6,
  auto_focus: true, focus: 255,
  auto_wb: true, wb_temperature: 4500,
  brightness: 128, contrast: 32, saturation: 32, gain: 28,
}

function SliderRow({ label, value, min, max, step = 1, onChange, hint }: {
  label: string
  value: number
  min: number
  max: number
  step?: number
  onChange: (v: number) => void
  hint?: string
}) {
  return (
    <div className="mb-2.5">
      <div className="mb-1 flex items-center justify-between text-[12px]">
        <span>{label}</span>
        <span className="text-muted-foreground font-mono">{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full"
      />
      {hint && <div className="text-muted-foreground text-[10.5px]">{hint}</div>}
    </div>
  )
}

/** Measured on the actual Logi C615 rather than guessed: exposure and gain both reliably move
 *  brightness (see capture_source.py's comment for the numbers), white balance takes a Kelvin
 *  value cleanly, but focus only really has two working positions on this camera — every value
 *  tried besides 0 and 255 silently failed to apply — so it gets two buttons, not a slider.
 *  There is no aperture control to expose: a webcam's iris, where it has one at all, is fixed. */
function CameraSettingsPanel({ settings, onPatch }: {
  settings: CameraSettings
  onPatch: (p: Partial<CameraSettings>) => void
}) {
  return (
    <div className="h-full rounded-md border p-4">
      <div className="mb-1 text-[13px] font-bold">ตั้งค่ากล้อง</div>
      <p className="text-muted-foreground mb-3 text-[11.5px] leading-relaxed">
        แก้ปัญหาแสงไม่เท่ากันระหว่างรอบถ่าย — กล้องนี้ไม่มีรูรับแสง (f-stop) แบบกล้องถ่ายรูปจริง
        ปรับได้แค่ Exposure (ความไวชัตเตอร์), Gain (ทำหน้าที่คล้าย ISO), Focus (ใกล้/ไกล — เลือกได้แค่
        2 ระยะ), และ White Balance เปิดวิดีโอสดไว้แล้วปรับดูจะเห็นผลทันที และมีผลกับการถ่ายเคสจริงด้วย
        ไม่ใช่แค่หน้านี้
      </p>

      <div className="mb-2 flex items-center gap-2">
        <Checkbox
          id="auto_exposure"
          checked={settings.auto_exposure}
          onCheckedChange={(v) => onPatch({ auto_exposure: !!v })}
        />
        <label htmlFor="auto_exposure" className="text-[12.5px]">ปรับแสงอัตโนมัติ (auto exposure)</label>
      </div>
      {!settings.auto_exposure && (
        <SliderRow
          label="Exposure"
          value={settings.exposure}
          min={-13}
          max={-1}
          onChange={(v) => onPatch({ exposure: v })}
          hint="มืด (-13) ← → สว่าง (-1)"
        />
      )}

      <div className="mb-2 flex items-center gap-2">
        <Checkbox
          id="auto_focus"
          checked={settings.auto_focus}
          onCheckedChange={(v) => onPatch({ auto_focus: !!v })}
        />
        <label htmlFor="auto_focus" className="text-[12.5px]">โฟกัสอัตโนมัติ (auto focus)</label>
      </div>
      {!settings.auto_focus && (
        <div className="mb-2.5 flex gap-2">
          <Button size="sm" variant={settings.focus === 0 ? 'default' : 'outline'} onClick={() => onPatch({ focus: 0 })}>
            ใกล้ (Near)
          </Button>
          <Button size="sm" variant={settings.focus === 255 ? 'default' : 'outline'} onClick={() => onPatch({ focus: 255 })}>
            ไกล (Far)
          </Button>
        </div>
      )}

      <div className="mb-2 flex items-center gap-2">
        <Checkbox
          id="auto_wb"
          checked={settings.auto_wb}
          onCheckedChange={(v) => onPatch({ auto_wb: !!v })}
        />
        <label htmlFor="auto_wb" className="text-[12.5px]">ปรับสมดุลสีขาวอัตโนมัติ (auto white balance)</label>
      </div>
      {!settings.auto_wb && (
        <SliderRow
          label="White balance (K)"
          value={settings.wb_temperature}
          min={2500}
          max={8000}
          step={100}
          onChange={(v) => onPatch({ wb_temperature: v })}
        />
      )}

      <SliderRow label="Brightness" value={settings.brightness} min={0} max={255} onChange={(v) => onPatch({ brightness: v })} />
      <SliderRow label="Contrast" value={settings.contrast} min={0} max={255} onChange={(v) => onPatch({ contrast: v })} />
      <SliderRow label="Saturation" value={settings.saturation} min={0} max={255} onChange={(v) => onPatch({ saturation: v })} />
      <SliderRow
        label="Gain (คล้าย ISO)"
        value={settings.gain}
        min={0}
        max={255}
        onChange={(v) => onPatch({ gain: v })}
        hint="ค่าสูงเกิน ~100 ภาพจะขาวเกิน (คลิป) ได้ง่าย"
      />

      <Button size="sm" variant="outline" onClick={() => onPatch(SETTINGS_DEFAULTS)}>
        รีเซ็ตเป็นค่าเริ่มต้น
      </Button>
    </div>
  )
}

export default function CameraTest() {
  const [status, setStatus] = useState<CameraStatus | null>(null)
  const [shots, setShots] = useState<Shot[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [live, setLive] = useState(true)
  const [settings, setSettings] = useState<CameraSettings | null>(null)
  const [showSettings, setShowSettings] = useState(true)
  const [modalShot, setModalShot] = useState<Shot | null>(null)
  const patchTimer = useRef<number | null>(null)

  async function checkCamera() {
    try { setStatus(await api<CameraStatus>('/api/camera')) } catch { setStatus(null) }
  }

  // Filenames are unique per shot (Test-<timestamp>.png), so the list itself is the source of
  // truth — no separate in-memory record to fall out of sync with what's actually on disk.
  async function loadShots() {
    try { setShots(await api<Shot[]>('/api/camera-test/list?modality=podoscope')) } catch { /* leave previous list */ }
  }

  async function loadSettings() {
    try { setSettings(await api<CameraSettings>('/api/camera/settings')) } catch { /* leave previous */ }
  }

  // Applied to state immediately so the slider feels instant, then sent to the server debounced
  // — a slider fires onChange on every pixel of drag, and each one calls save_camera_settings()
  // AND applies it live if the preview is open, so this is the difference between one request
  // when the finger lifts and dozens while it is still moving.
  function patchSettings(p: Partial<CameraSettings>) {
    setSettings((s) => (s ? { ...s, ...p } : s))
    if (patchTimer.current) window.clearTimeout(patchTimer.current)
    patchTimer.current = window.setTimeout(() => {
      api<CameraSettings>('/api/camera/settings', p).catch(() => { /* next change retries with fresh values */ })
    }, 150)
  }

  useEffect(() => {
    checkCamera()
    loadShots()
    loadSettings()
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
          <Button size="sm" variant="outline" onClick={() => setShowSettings((v) => !v)}>
            {showSettings ? 'ซ่อนตั้งค่ากล้อง' : 'ตั้งค่ากล้อง'}
          </Button>
        </div>
        {(live || (showSettings && settings)) && (
          <div className="mb-3 flex flex-wrap items-start gap-3">
            {live && <div className="min-w-[320px] flex-1">
              <PodoscopeLiveView />
            </div>}
            {showSettings && settings && (
              <div className="w-full sm:w-72 sm:shrink-0">
                <CameraSettingsPanel settings={settings} onPatch={patchSettings} />
              </div>
            )}
          </div>
        )}

        {error && <p className="mb-2 text-[13px] text-destructive">{error}</p>}
        <Button onClick={shoot} disabled={busy}>{busy ? 'กำลังถ่าย…' : 'ถ่ายทดสอบ'}</Button>
        {shots.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-3">
            {shots.slice(0, 12).map((s) => (
              <button
                key={s.name}
                type="button"
                onClick={() => setModalShot(s)}
                className="block w-28 shrink-0 cursor-pointer overflow-hidden rounded-md border text-left"
              >
                <div className="bg-foreground/95 flex aspect-square items-center justify-center overflow-hidden">
                  <img src={s.url} alt={s.name} className="h-full w-full object-contain" />
                </div>
                <div className="text-muted-foreground truncate px-1 py-1 text-center text-[10px]">{s.name}</div>
              </button>
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

      <Dialog open={!!modalShot} onOpenChange={(open) => !open && setModalShot(null)}>
        <DialogContent className="max-w-3xl sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>{modalShot?.name}</DialogTitle>
          </DialogHeader>
          {modalShot && (
            <img
              src={modalShot.url}
              alt={modalShot.name}
              className="max-h-[75vh] w-full rounded-md object-contain"
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
