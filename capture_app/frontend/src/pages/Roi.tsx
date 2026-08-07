/* Case picker for ROI annotation — mirrors capture.html's picker pattern so "ทำ ROI" behaves
   the same way as "ถ่ายภาพ" from the navbar: a dedicated page, not something buried inside the
   dashboard. Opens each case's ROI in VIA 2 (via/index.html?rid=), same as before.

   Every case that's finished capturing still shows up here (not hidden), even ones where neither
   foot needs marking — just tagged "ไม่ต้องทำ" instead of a clickable action, so nothing looks
   like it's silently missing from the list. */

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { categoryToLabel, roiSideStatus, ROI_STATUS_TEXT } from '@/lib/roiStatus'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { DeleteConfirmDialog } from '@/components/DeleteConfirmDialog'

interface CaseRow {
  research_id: string
  nurse: string
  iwgdf: { L: number | null; R: number | null }
  has_podo: boolean
  has_thermal: boolean
}
interface RoiSummaryRow {
  rid: string
  summary?: { L?: { region_count?: number }; R?: { region_count?: number } }
}

export default function Roi() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [cases, setCases] = useState<CaseRow[]>([])
  const [roiCounts, setRoiCounts] = useState<Record<string, { L: number; R: number }>>({})
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  async function onDeleteRoi(rid: string) {
    await api('/api/roi/' + encodeURIComponent(rid), undefined, 'DELETE')
    setRoiCounts((c) => ({ ...c, [rid]: { L: 0, R: 0 } }))
  }

  useEffect(() => {
    ;(async () => {
      try {
        const [cs, roi] = await Promise.all([
          api<CaseRow[]>('/api/cases'),
          api<RoiSummaryRow[]>('/api/roi'),
        ])
        setCases(cs.filter((c) => c.has_podo && c.has_thermal))
        const counts: Record<string, { L: number; R: number }> = {}
        roi.forEach((r) => {
          counts[r.rid] = { L: r.summary?.L?.region_count || 0, R: r.summary?.R?.region_count || 0 }
        })
        setRoiCounts(counts)
      } catch {
        setError(true)
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  return (
    <div className="mx-auto max-w-[1600px] px-4 py-6">
      <div className="mb-4">
        <h1 className="text-lg font-bold">ทำ ROI ในภาพ</h1>
        <p className="text-muted-foreground text-[13px]">
          เลือกเคสที่ถ่ายภาพครบทั้ง podoscope และ thermal แล้ว เพื่อมาร์กบริเวณแรงกดที่เสี่ยงด้วย VIA 2 —
          ข้างที่ผลตรวจเป็น Negative ไม่ต้องมาร์ก
        </p>
      </div>

      <Card className="p-5">
        {loading && <div className="text-muted-foreground text-sm">กำลังโหลด…</div>}
        {!loading && error && (
          <div className="text-muted-foreground text-sm">
            โหลดรายการไม่ได้ — ตรวจสอบว่าต่อกับเซิร์ฟเวอร์อยู่
          </div>
        )}
        {!loading && !error && cases.length === 0 && (
          <div className="text-muted-foreground text-[13px] italic">
            ยังไม่มีเคสที่ถ่ายภาพครบทั้งสองส่วน — ไปที่ "ถ่ายภาพ" ก่อน
          </div>
        )}
        {!loading && !error && cases.length > 0 && (
          <div className="space-y-2">
            {cases.map((c) => {
              const counts = roiCounts[c.research_id] || { L: 0, R: 0 }
              const statusL = roiSideStatus(categoryToLabel(c.iwgdf?.L), counts.L)
              const statusR = roiSideStatus(categoryToLabel(c.iwgdf?.R), counts.R)
              const anyNeeded = statusL !== 'not_needed' || statusR !== 'not_needed'
              const anyDone = statusL === 'done' || statusR === 'done'
              return (
                <div
                  key={c.research_id}
                  className="bg-secondary flex items-center gap-3 rounded-md border px-3.5 py-2.5"
                >
                  <span className="text-primary font-mono font-bold">{c.research_id}</span>
                  <span className="text-muted-foreground flex-1 text-[12.5px]">
                    {c.nurse || '—'} · IWGDF ซ้าย {c.iwgdf?.L ?? '—'} · ขวา {c.iwgdf?.R ?? '—'}
                  </span>
                  <span className="text-[11px]">
                    <span className={statusL === 'done' ? 'text-cat-0' : statusL === 'pending' ? 'text-cat-1' : 'text-muted-foreground'}>
                      ซ้าย: {ROI_STATUS_TEXT[statusL]}
                    </span>
                    <span className="text-muted-foreground mx-1">·</span>
                    <span className={statusR === 'done' ? 'text-cat-0' : statusR === 'pending' ? 'text-cat-1' : 'text-muted-foreground'}>
                      ขวา: {ROI_STATUS_TEXT[statusR]}
                    </span>
                  </span>
                  {anyNeeded ? (
                    <Button size="sm" asChild>
                      <a
                        href={`via/index.html?rid=${encodeURIComponent(c.research_id)}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {anyDone ? 'เปิด ROI →' : 'ทำ ROI →'}
                      </a>
                    </Button>
                  ) : (
                    <Badge variant="secondary">ไม่ต้องทำ</Badge>
                  )}
                  {anyDone && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-destructive hover:text-destructive"
                      onClick={() => setDeleteTarget(c.research_id)}
                    >
                      ลบ ROI
                    </Button>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </Card>

      {deleteTarget && (
        <DeleteConfirmDialog
          open={!!deleteTarget}
          onOpenChange={(o) => !o && setDeleteTarget(null)}
          code={deleteTarget}
          title={`ลบผลมาร์ก ROI ของ ${deleteTarget}`}
          description="ลบเฉพาะข้อมูล ROI ที่มาร์กไว้ (ไม่กระทบฟอร์ม CRF หรือภาพถ่าย) การลบนี้ถาวรและกู้คืนไม่ได้"
          onConfirm={() => onDeleteRoi(deleteTarget)}
        />
      )}
    </div>
  )
}
