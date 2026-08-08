/* Cross-case image browser — level-2 follow-up to crf-detail.html's per-case image section.
   That page answers "show me this one patient's images"; this page answers "let me scan
   thumbnails across every captured case" (QC sweep before a training run, spot a bad thermal
   capture, etc). Source is GET /api/manifest — the same commits list crf-list.html and
   capture.html's own saved-table already use, so a case shows up here the moment it's committed
   (podo and/or thermal — commit doesn't require both). */

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { ManifestRow } from '@/lib/crfTypes'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'

function Thumb({ src, label }: { src: string; label: string }) {
  const [broken, setBroken] = useState(false)
  if (!src || broken) {
    return (
      <div className="bg-secondary flex aspect-square w-24 shrink-0 flex-col items-center justify-center rounded-md border text-center">
        <span className="text-muted-foreground text-[10px]">ไม่มี{label}</span>
      </div>
    )
  }
  return (
    <a href={src} target="_blank" rel="noreferrer" className="block w-24 shrink-0 overflow-hidden rounded-md border">
      <div className="bg-foreground/95 flex aspect-square items-center justify-center overflow-hidden">
        <img src={src} alt={label} className="h-full w-full object-contain" onError={() => setBroken(true)} />
      </div>
      <div className="text-muted-foreground truncate px-1 py-1 text-center text-[10px]">{label}</div>
    </a>
  )
}

export default function Gallery() {
  const [rows, setRows] = useState<ManifestRow[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    api<ManifestRow[]>('/api/manifest')
      .then(setRows)
      .catch(() => setError(true))
  }, [])

  return (
    <div className="mx-auto max-w-[1600px] px-4 py-6">
      <div className="mb-4">
        <h1 className="text-lg font-bold">คลังภาพ</h1>
        <p className="text-muted-foreground text-[13px]">
          ไล่ดูรูปทุกเคสที่บันทึกแล้วในหน้าเดียว — เช็คคุณภาพภาพก่อนเอาไปเทรนโมเดล
          คลิกรูปเพื่อดูเต็มขนาด หรือคลิกรหัสวิจัยเพื่อดูรายละเอียดเต็ม (มีทั้ง original/full/train ต่อข้าง)
        </p>
      </div>

      {!rows && !error && <div className="text-muted-foreground text-sm">กำลังโหลด…</div>}
      {error && <div className="text-muted-foreground text-sm">โหลดรายการไม่ได้ — ตรวจสอบว่าต่อกับเซิร์ฟเวอร์อยู่</div>}
      {rows && rows.length === 0 && (
        <div className="text-muted-foreground text-[13px] italic">ยังไม่มีเคสที่บันทึกภาพ</div>
      )}

      {rows && rows.length > 0 && (
        <div className="space-y-3">
          {[...rows].sort((a, b) => b.research_id.localeCompare(a.research_id)).map((r) => (
            <Card key={r.research_id} className="p-3.5">
              <div className="flex flex-wrap items-center gap-4">
                <div className="w-24 shrink-0">
                  <a
                    href={`crf-detail.html?pid=${encodeURIComponent(r.research_id)}`}
                    className="text-primary block font-mono font-bold hover:underline"
                  >
                    {r.research_id}
                  </a>
                  <Badge variant={r.status === 'complete' ? 'default' : 'secondary'} className="mt-1">
                    {r.status === 'complete' ? 'ครบ' : 'ไม่ครบ'}
                  </Badge>
                </div>
                <div className="flex flex-1 flex-wrap gap-2.5">
                  <Thumb src={r.podo_raw ? `/api/file/${r.podo_raw}` : ''} label="Podoscope" />
                  <Thumb src={r.thermal ? `/api/file/${r.thermal}` : ''} label="Thermal" />
                  <Thumb
                    src={r.podo_prepro === 'yes' ? `/api/file/podo/${r.research_id}/preprocessing/${r.research_id}_podo_L_full.png` : ''}
                    label="เท้าซ้าย"
                  />
                  <Thumb
                    src={r.podo_prepro === 'yes' ? `/api/file/podo/${r.research_id}/preprocessing/${r.research_id}_podo_R_full.png` : ''}
                    label="เท้าขวา"
                  />
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
