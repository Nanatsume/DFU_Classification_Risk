import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { CrfRecord, DerivedSide, ManifestRow } from '@/lib/crfTypes'
import { roiSideStatus, ROI_STATUS_TEXT } from '@/lib/roiStatus'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { DeleteConfirmDialog } from '@/components/DeleteConfirmDialog'

const SIDES = [
  { k: 'L' as const, th: 'เท้าซ้าย', en: 'LEFT' },
  { k: 'R' as const, th: 'เท้าขวา', en: 'RIGHT' },
]
const MF_SITES = [
  { k: 'hallux', th: 'หัวแม่เท้า' },
  { k: 'mth1', th: 'MTH ที่ 1' },
  { k: 'mth5', th: 'MTH ที่ 5' },
]
const ABIT: Record<string, string> = {
  normal: 'ปกติ 0.90–1.30',
  pad: 'PAD < 0.90',
  calcified: 'หลอดเลือดแข็งตัว > 1.30',
}
const TBIT: Record<string, string> = { normal: 'ปกติ ≥ 0.70', pad: 'PAD < 0.70' }

function DRow({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3.5 border-b border-dotted px-3 py-2 text-[13.5px] last:border-0">
      <span className="text-muted-foreground">{k}</span>
      {children}
    </div>
  )
}
function Yn({ v, yes, no }: { v: boolean | null | undefined; yes: string; no: string }) {
  if (v === true) return <span className="text-destructive font-medium">{yes}</span>
  if (v === false) return <span className="text-cat-0 font-medium">{no}</span>
  return <span className="text-muted-foreground">ไม่ได้ระบุ</span>
}
function DGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-2.5 overflow-hidden rounded-md border">
      <div className="bg-secondary text-secondary-foreground border-b px-3 py-1.5 text-xs font-semibold">
        {title}
      </div>
      {children}
    </div>
  )
}

/* Hides itself if the file 404s (e.g. thermal capture skipped, or preprocessing never ran) —
   simplest way to handle "this case doesn't have all 8 images" without a dedicated endpoint,
   since every image's path is fully determined by pid + a fixed filename suffix. */
function ImageThumb({ src, label }: { src: string; label: string }) {
  const [broken, setBroken] = useState(false)
  if (broken) return null
  return (
    <a href={src} target="_blank" rel="noreferrer" className="block overflow-hidden rounded-md border">
      <div className="bg-foreground/95 flex aspect-square items-center justify-center overflow-hidden">
        <img src={src} alt={label} className="h-full w-full object-contain" onError={() => setBroken(true)} />
      </div>
      <div className="text-muted-foreground px-2 py-1.5 text-center text-[11px]">{label}</div>
    </a>
  )
}

// VIA region shape (shape_attributes) — same format _via_dfu.js saves, see roi_store.py's
// project_json. Only the fields each shape type actually uses are read.
interface ViaShape {
  name: 'rect' | 'circle' | 'ellipse' | 'polygon' | 'polyline' | 'point'
  x?: number; y?: number; width?: number; height?: number
  cx?: number; cy?: number; r?: number; rx?: number; ry?: number
  all_points_x?: number[]; all_points_y?: number[]
}
interface ViaRegion { shape_attributes: ViaShape }

function RoiShape({ shape }: { shape: ViaShape }) {
  const stroke = '#e0552b' // matches the app's thermal/warning accent — stands out on grayscale
  const common = { stroke, strokeWidth: 3, fill: 'none', vectorEffect: 'non-scaling-stroke' as const }
  switch (shape.name) {
    case 'rect':
      return <rect x={shape.x} y={shape.y} width={shape.width} height={shape.height} {...common} />
    case 'circle':
      return <circle cx={shape.cx} cy={shape.cy} r={shape.r} {...common} />
    case 'ellipse':
      return <ellipse cx={shape.cx} cy={shape.cy} rx={shape.rx} ry={shape.ry} {...common} />
    case 'polygon':
      return <polygon points={(shape.all_points_x || []).map((x, i) => `${x},${shape.all_points_y?.[i]}`).join(' ')} {...common} />
    case 'polyline':
      return <polyline points={(shape.all_points_x || []).map((x, i) => `${x},${shape.all_points_y?.[i]}`).join(' ')} {...common} />
    case 'point':
      return <circle cx={shape.cx} cy={shape.cy} r={6} fill={stroke} stroke="#fff" strokeWidth={1.5} />
    default:
      return null
  }
}

/* Same as ImageThumb but overlays the saved ROI boxes on top — the whole point of "Full (ROI)"
   is that it's the image ROI was actually marked on, so the marks should be visible here too,
   not just inside VIA. Regions are in the image's native pixel coordinates (that's how VIA
   stores them); an SVG with a matching viewBox scales them onto the thumbnail automatically
   regardless of its displayed CSS size, no manual math needed. */
function RoiImageThumb({ src, label, regions }: { src: string; label: string; regions: ViaRegion[] }) {
  const [broken, setBroken] = useState(false)
  const [natSize, setNatSize] = useState<{ w: number; h: number } | null>(null)
  if (broken) return null
  return (
    <a href={src} target="_blank" rel="noreferrer" className="block overflow-hidden rounded-md border">
      <div className="bg-foreground/95 relative flex aspect-square items-center justify-center overflow-hidden">
        <img
          src={src}
          alt={label}
          className="h-full w-full object-contain"
          onError={() => setBroken(true)}
          onLoad={(e) => {
            const img = e.currentTarget
            setNatSize({ w: img.naturalWidth, h: img.naturalHeight })
          }}
        />
        {natSize && regions.length > 0 && (
          <svg
            className="pointer-events-none absolute inset-0 h-full w-full"
            viewBox={`0 0 ${natSize.w} ${natSize.h}`}
            preserveAspectRatio="xMidYMid meet"
          >
            {regions.map((r, i) => <RoiShape key={i} shape={r.shape_attributes} />)}
          </svg>
        )}
      </div>
      <div className="text-muted-foreground px-2 py-1.5 text-center text-[11px]">
        {label} {regions.length > 0 ? `(${regions.length})` : ''}
      </div>
    </a>
  )
}

export default function CrfDetail() {
  const [rec, setRec] = useState<CrfRecord | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [manifestRow, setManifestRow] = useState<ManifestRow | null>(null)
  const [roiRegions, setRoiRegions] = useState<Record<'L' | 'R', ViaRegion[]>>({ L: [], R: [] })
  const [roiDeleteOpen, setRoiDeleteOpen] = useState(false)
  const pid = new URLSearchParams(location.search).get('pid') || ''
  const captured = !!manifestRow

  async function onDeleteRoi() {
    await api('/api/roi/' + encodeURIComponent(pid), undefined, 'DELETE')
    setRoiRegions({ L: [], R: [] }) // ล้างกรอบที่วาดทับ + ทำให้สถานะกลับเป็น pending ตาม label เดิม
  }

  useEffect(() => {
    if (!pid) return
    api<CrfRecord>('/api/crf/' + encodeURIComponent(pid))
      .then(setRec)
      .catch(() => setNotFound(true))
    api<ManifestRow[]>('/api/manifest')
      .then((rows) => setManifestRow(rows.find((r) => r.research_id === pid) || null))
      .catch(() => {})
    // full VIA project — the region boxes per side are drawn back onto the Full (ROI) thumbnail
    // below, and their count doubles as the per-side "done" signal (see roiSideStatus below).
    // Full (ROI) thumbnail below. 404s (no ROI done yet) just leave the boxes empty.
    api<{ project: { _via_img_metadata?: Record<string, { file_attributes?: { foot_side?: string }; regions?: ViaRegion[] }> } }>(
      '/api/roi/' + encodeURIComponent(pid),
    )
      .then((data) => {
        const bySide: Record<'L' | 'R', ViaRegion[]> = { L: [], R: [] }
        const meta = data.project?._via_img_metadata || {}
        for (const imgId in meta) {
          const side = meta[imgId].file_attributes?.foot_side
          if (side === 'L' || side === 'R') bySide[side] = meta[imgId].regions || []
        }
        setRoiRegions(bySide)
      })
      .catch(() => {})
  }, [pid])

  if (!pid) return <p className="p-6 text-sm">ไม่ได้ระบุรหัสวิจัย (?pid=)</p>
  if (notFound) return <p className="p-6 text-sm">ไม่พบเคส {pid}</p>
  if (!rec) return <p className="p-6 text-sm">กำลังโหลด…</p>

  const f = rec.data?.fields || {}
  const der = rec.data?.derived || {}
  const dt = rec.savedAt ? new Date(rec.savedAt) : null

  const bothLabelsMissing = (der.L?.label ?? null) === null && (der.R?.label ?? null) === null
  const statusL = roiSideStatus(der.L?.label, roiRegions.L.length)
  const statusR = roiSideStatus(der.R?.label, roiRegions.R.length)
  const anyRoiNeeded = statusL !== 'not_needed' || statusR !== 'not_needed'
  const anyRoiDone = statusL === 'done' || statusR === 'done'

  return (
    <div className="mx-auto max-w-[1600px] px-4 pb-10">
      {bothLabelsMissing && (
        <div className="bg-destructive/10 border-destructive/30 text-destructive mt-6 mb-3.5 rounded-md border px-4 py-3 text-[13.5px] font-medium">
          ⚠️ ยังไม่มีผลสรุป IWGDF ทั้งสองข้าง — ข้อมูลเคสนี้ยังใช้เทรนโมเดลไม่ได้{' '}
          <a href={`crf-form.html?edit=${encodeURIComponent(pid)}`} className="underline">
            กลับไปกรอกข้อมูลให้ครบ →
          </a>
        </div>
      )}

      <div className={'mb-4 flex flex-wrap items-end justify-between gap-4' + (bothLabelsMissing ? '' : ' mt-6')}>
        <div>
          <div className="text-lg font-bold">{rec.pid}</div>
          <div className="text-muted-foreground text-xs">
            {dt
              ? 'บันทึกเมื่อ ' +
                dt.toLocaleDateString('th-TH', { day: '2-digit', month: 'long', year: 'numeric' }) +
                ' เวลา ' +
                dt.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' }) +
                ' น.'
              : ''}
            {' · พยาบาลผู้ตรวจ '}
            {[f.nurse, f.nurse2].filter(Boolean).join(' และ ') || 'ไม่ได้ระบุ'}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" asChild>
            <a href="crf-list.html">กลับไปหน้าประวัติ</a>
          </Button>
          <Button variant="outline" asChild>
            <a href={`crf-form.html?edit=${encodeURIComponent(pid)}`}>แก้ไขข้อมูล</a>
          </Button>

          {captured && (
            <span className="text-[11px]">
              <span className={statusL === 'done' ? 'text-cat-0' : statusL === 'pending' ? 'text-cat-1' : 'text-muted-foreground'}>
                ซ้าย: {ROI_STATUS_TEXT[statusL]}
              </span>
              <span className="text-muted-foreground mx-1">·</span>
              <span className={statusR === 'done' ? 'text-cat-0' : statusR === 'pending' ? 'text-cat-1' : 'text-muted-foreground'}>
                ขวา: {ROI_STATUS_TEXT[statusR]}
              </span>
            </span>
          )}
          {anyRoiNeeded ? (
            <Button
              variant="outline"
              onClick={() => {
                if (!captured) {
                  alert('เคส ' + pid + ' ยังไม่มีภาพ ต้องถ่ายภาพและผ่าน preprocessing ก่อนจึงจะมาร์ก ROI ได้')
                  return
                }
                window.open('via/index.html?rid=' + encodeURIComponent(pid), '_blank')
              }}
            >
              {(anyRoiDone ? 'เปิด ROI ของ ' : 'ทำ ROI ของ ') + pid} →
            </Button>
          ) : (
            <Badge variant="secondary">ไม่ต้องทำ ROI — ทั้งสองข้างไม่มีความเสี่ยง</Badge>
          )}
          {anyRoiDone && (
            <Button
              variant="outline"
              className="text-destructive hover:text-destructive"
              onClick={() => setRoiDeleteOpen(true)}
            >
              ลบ ROI
            </Button>
          )}

          <Button asChild>
            <a href={`capture.html?rid=${encodeURIComponent(pid)}`}>
              {(captured ? 'ดูภาพของ ' : 'ถ่ายภาพ ') + pid} →
            </a>
          </Button>
        </div>
      </div>

      {captured && manifestRow && (
        <Card className="mb-3.5 overflow-hidden p-0">
          <div className="bg-secondary text-secondary-foreground border-b px-4 py-2.5 font-bold">
            รูปภาพ
          </div>
          <CardContent className="space-y-4 p-4">
            <div>
              <div className="text-muted-foreground mb-1.5 text-xs font-semibold">ภาพต้นฉบับ</div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {manifestRow.podo_raw && (
                  <ImageThumb src={`/api/file/${manifestRow.podo_raw}`} label="Podoscope" />
                )}
                {manifestRow.thermal && (
                  <ImageThumb src={`/api/file/${manifestRow.thermal}`} label="Thermal" />
                )}
              </div>
            </div>
            {manifestRow.podo_prepro === 'yes' &&
              SIDES.map((sd) => {
                const base = `/api/file/podo/${pid}/preprocessing/${pid}_podo_${sd.k}`
                return (
                  <div key={sd.k}>
                    <div className="text-muted-foreground mb-1.5 text-xs font-semibold">{sd.th}</div>
                    <div className="grid grid-cols-3 gap-3 sm:max-w-md">
                      <ImageThumb src={`${base}_original.png`} label="Original (สี)" />
                      <RoiImageThumb src={`${base}_full.png`} label="Full (ROI)" regions={roiRegions[sd.k]} />
                      <ImageThumb src={`${base}.png`} label="Train 224×224" />
                    </div>
                  </div>
                )
              })}
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
        {SIDES.map((sd) => {
          const g: DerivedSide | undefined = der[sd.k]
          const defs = g?.deformities || []
          const abi = ABIT[f['abi_' + sd.k] as string]
          const tbi = TBIT[f['tbi_' + sd.k] as string]
          return (
            <Card key={sd.k} className="overflow-hidden p-0">
              <div className="bg-secondary flex items-center justify-between gap-2.5 px-4 py-2.5">
                <span className="font-bold">{sd.th}</span>
                <Badge className={g?.label ? (g.label === 'Positive' ? 'bg-destructive text-white' : 'bg-cat-0 text-white') : ''}>
                  {g?.label || 'ยังไม่สรุป'}
                </Badge>
                <span className="text-muted-foreground font-mono text-[10.5px] tracking-wider">{sd.en}</span>
              </div>
              <CardContent className="space-y-2.5 p-4">
                <DGroup title="การตรวจสูญเสียความรู้สึกป้องกันตัวที่เท้าด้วยโมโนฟิลาเมนต์">
                  {MF_SITES.map((m) => {
                    const v = f['mf_' + sd.k + '_' + m.k]
                    return (
                      <DRow key={m.k} k={m.th}>
                        {v === 'y' ? (
                          <span className="text-cat-0 font-medium">รู้สึก</span>
                        ) : v === 'n' ? (
                          <span className="text-destructive font-medium">ไม่รู้สึก</span>
                        ) : (
                          <span className="text-muted-foreground">ไม่ได้ตรวจ</span>
                        )}
                      </DRow>
                    )
                  })}
                  <DRow k="สรุป"><Yn v={g?.lops} yes="มี LOPS" no="ไม่มี LOPS" /></DRow>
                </DGroup>

                <DGroup title="การตรวจโรคหลอดเลือดแดงส่วนปลาย">
                  <DRow k="ABI">
                    {abi ? <span className="font-medium">{abi}</span> : <span className="text-muted-foreground">ไม่ได้ตรวจ</span>}
                  </DRow>
                  {tbi && <DRow k="TBI"><span className="font-medium">{tbi}</span></DRow>}
                  <DRow k="สรุป"><Yn v={g?.pad} yes="มี PAD" no="ไม่มี PAD" /></DRow>
                </DGroup>

                <DGroup title="การตรวจความผิดปกติของเท้า">
                  {defs.length ? (
                    <DRow k={`พบ ${defs.length} รายการ`}>
                      <span className="text-right text-[13px] leading-relaxed">
                        {defs.map((d, i) => <div key={i}>{d}</div>)}
                      </span>
                    </DRow>
                  ) : (
                    <DRow k="ผลตรวจ"><span className="text-cat-0 font-medium">ไม่พบความผิดปกติ</span></DRow>
                  )}
                </DGroup>

                <DGroup title="ประวัติแผลและการตัดรยางค์">
                  <DRow k="แผลเบาหวานที่เท้า">
                    <Yn v={f['ulcer_' + sd.k] === 'yes' ? true : f['ulcer_' + sd.k] === 'no' ? false : null} yes="มีประวัติ" no="ไม่มี" />
                  </DRow>
                  <DRow k="การตัดรยางค์ล่าง">
                    <Yn v={f['amp_' + sd.k] === 'yes' ? true : f['amp_' + sd.k] === 'no' ? false : null} yes="มี" no="ไม่มี" />
                  </DRow>
                </DGroup>

                <DGroup title="ผลสรุป">
                  <DRow k="ประเภทความเสี่ยง">
                    {g?.category === null || g?.category === undefined ? (
                      <span className="text-muted-foreground">ยังไม่สรุป</span>
                    ) : (
                      <span className="font-medium">IWGDF {g.category}</span>
                    )}
                  </DRow>
                  <DRow k="Binary label">
                    {g?.label ? (
                      <span className={'font-medium ' + (g.label === 'Positive' ? 'text-destructive' : 'text-cat-0')}>{g.label}</span>
                    ) : (
                      <span className="text-muted-foreground">ยังไม่สรุป</span>
                    )}
                  </DRow>
                </DGroup>
              </CardContent>
            </Card>
          )
        })}
      </div>

      <div className="mt-3.5 grid grid-cols-1 gap-3.5 md:grid-cols-2">
        <Card className="overflow-hidden p-0">
          <div className="bg-secondary text-secondary-foreground border-b px-3 py-1.5 text-xs font-semibold">
            ไตวายระยะสุดท้าย (CKD stage 5)
          </div>
          <div className="p-3.5 text-[13.5px]">
            {f.ckd === 'yes' ? 'มี' : f.ckd === 'no' ? 'ไม่มี' : 'ไม่ได้ระบุ'}
          </div>
        </Card>
        <Card className="overflow-hidden p-0">
          <div className="bg-secondary text-secondary-foreground border-b px-3 py-1.5 text-xs font-semibold">
            หมายเหตุ
          </div>
          <div className="p-3.5 text-[13.5px] whitespace-pre-wrap">{f.note ? String(f.note) : 'ไม่มีหมายเหตุ'}</div>
        </Card>
      </div>

      <DeleteConfirmDialog
        open={roiDeleteOpen}
        onOpenChange={setRoiDeleteOpen}
        code={pid}
        title={`ลบผลมาร์ก ROI ของ ${pid}`}
        description="ลบเฉพาะข้อมูล ROI ที่มาร์กไว้ (ไม่กระทบฟอร์ม CRF หรือภาพถ่าย) การลบนี้ถาวรและกู้คืนไม่ได้ — ต้องมาร์กใหม่ตั้งแต่ต้นถ้าต้องการ"
        onConfirm={onDeleteRoi}
      />
    </div>
  )
}
