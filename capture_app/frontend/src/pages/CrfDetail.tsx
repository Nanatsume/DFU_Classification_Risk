import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { CrfRecord, DerivedSide, ManifestRow, RoiSummaryRow } from '@/lib/crfTypes'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

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

export default function CrfDetail() {
  const [rec, setRec] = useState<CrfRecord | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [captured, setCaptured] = useState(false)
  const [roiDone, setRoiDone] = useState(false)
  const pid = new URLSearchParams(location.search).get('pid') || ''

  useEffect(() => {
    if (!pid) return
    api<CrfRecord>('/api/crf/' + encodeURIComponent(pid))
      .then(setRec)
      .catch(() => setNotFound(true))
    api<ManifestRow[]>('/api/manifest')
      .then((rows) => setCaptured(rows.some((r) => r.research_id === pid)))
      .catch(() => {})
    api<RoiSummaryRow[]>('/api/roi')
      .then((rows) => setRoiDone(rows.some((r) => r.rid === pid)))
      .catch(() => {})
  }, [pid])

  if (!pid) return <p className="p-6 text-sm">ไม่ได้ระบุรหัสวิจัย (?pid=)</p>
  if (notFound) return <p className="p-6 text-sm">ไม่พบเคส {pid}</p>
  if (!rec) return <p className="p-6 text-sm">กำลังโหลด…</p>

  const f = rec.data?.fields || {}
  const der = rec.data?.derived || {}
  const dt = rec.savedAt ? new Date(rec.savedAt) : null

  return (
    <div className="mx-auto max-w-5xl px-4 pb-10">
      <div className="mb-4 mt-6 flex flex-wrap items-end justify-between gap-4">
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
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" asChild>
            <a href="crf-list.html">กลับไปหน้าประวัติ</a>
          </Button>
          <Button variant="outline" asChild>
            <a href={`crf-form.html?edit=${encodeURIComponent(pid)}`}>แก้ไขข้อมูล</a>
          </Button>
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
            {(roiDone ? 'เปิด ROI ของ ' : 'ทำ ROI ของ ') + pid} →
          </Button>
          <Button asChild>
            <a href={`capture.html?rid=${encodeURIComponent(pid)}`}>
              {(captured ? 'ดูภาพของ ' : 'ถ่ายภาพ ') + pid} →
            </a>
          </Button>
        </div>
      </div>

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
    </div>
  )
}
