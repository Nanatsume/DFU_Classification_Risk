import { useEffect, useState } from 'react'
import { api, ApiError } from '@/lib/api'
import type { CrfRecord, DerivedSide, ManifestRow, RoiSummaryRow } from '@/lib/crfTypes'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { DeleteConfirmDialog } from '@/components/DeleteConfirmDialog'
import { MF_SITES, SIDES } from '@/lib/crfScoring'
import { roiSideStatus, ROI_STATUS_TEXT } from '@/lib/roiStatus'

function today() {
  return new Date().toISOString().slice(0, 10)
}

function download(text: string, name: string, mime: string) {
  const blob = new Blob(['﻿' + text], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1500)
}

/* Patient-level IWGDF = the worse (higher-numbered) of the two feet's categories — the standard
   IWGDF convention, since a patient's overall ulcer risk is driven by whichever foot is riskier,
   not an average of the two. Null if a side's category isn't decided yet; falls back to whichever
   single side is available if only one is. */
function patientLevelIwgdf(rec: CrfRecord): { category: number | ''; label: string } {
  const cats = SIDES.map((s) => rec.data?.derived?.[s.k]?.category).filter(
    (c): c is number => c !== null && c !== undefined,
  )
  if (!cats.length) return { category: '', label: '' }
  const category = Math.max(...cats)
  return { category, label: category >= 1 ? 'Positive' : 'Negative' }
}

/* ---------- CSV #1: raw form, column order follows the CRF-07 sections (ก LOPS → ข PAD →
   ค Deformity → ง History/CKD → จ Notes/nurses) exactly as printed on the paper form — for the
   teammate who needs to read/verify this against the original questionnaire. Deformity collapses
   to one yes/no column per side instead of all 13 checkbox items (too wide) — the specific types
   are not lost, they're still in the saved record (GET /api/crf/{pid} or data/app.db), just not
   spelled out column-by-column here. Ends with the computed IWGDF result per side, plus one
   patient-level (worse-foot) verdict, so the calculation can be checked against the raw answers
   in the same row, not just the training CSV. */
const RAW_FORM_COLUMNS: string[] = [
  'pid', 'savedAt',
  ...SIDES.flatMap((s) => MF_SITES.map((m) => `mf_${s.k}_${m.k}`)),                 // ก LOPS
  ...SIDES.flatMap((s) => [`abi_${s.k}`, `tbi_${s.k}`]),                            // ข PAD
  ...SIDES.map((s) => `deformity_${s.k}`),                                          // ค Deformity (yes/no, collapsed)
  ...SIDES.flatMap((s) => [`ulcer_${s.k}`, `amp_${s.k}`]), 'ckd',                   // ง History/CKD
  'note', 'nurse', 'nurse2',                                                        // จ Notes/nurses
  ...SIDES.flatMap((s) => [                                                         // สรุปผล IWGDF ต่อข้าง (คำนวณ)
    `lops_${s.k}`, `pad_${s.k}`, `history_${s.k}`, `iwgdf_category_${s.k}`, `iwgdf_label_${s.k}`,
  ]),
  'iwgdf_category_patient', 'iwgdf_label_patient',                                  // สรุปผลระดับผู้ป่วย (ข้างที่แย่กว่า)
]

function flattenRawForm(rec: CrfRecord): Record<string, unknown> {
  const fields = rec.data?.fields || {}
  const derivedOnly = new Set(SIDES.map((s) => `deformity_${s.k}`))
  const row: Record<string, unknown> = { pid: rec.pid, savedAt: rec.savedAt }
  RAW_FORM_COLUMNS.forEach((col) => {
    if (col === 'pid' || col === 'savedAt' || derivedOnly.has(col)) return
    if (col === 'nurse') { row.nurse = rec.nurse; return }
    if (col === 'nurse2') { row.nurse2 = rec.nurse2; return }
    row[col] = fields[col] ?? ''
  })
  SIDES.forEach((s) => {
    const g = rec.data?.derived?.[s.k] || ({} as DerivedSide)
    row[`deformity_${s.k}`] = g.deformity ?? ''
    row[`lops_${s.k}`] = g.lops ?? ''
    row[`pad_${s.k}`] = g.pad ?? ''
    row[`history_${s.k}`] = g.history ?? ''
    row[`iwgdf_category_${s.k}`] = g.category ?? ''
    row[`iwgdf_label_${s.k}`] = g.label ?? ''
  })
  const patient = patientLevelIwgdf(rec)
  row.iwgdf_category_patient = patient.category
  row.iwgdf_label_patient = patient.label
  return row
}

/* ---------- CSV #2: training data, IWGDF-derived fields only, one row per foot (long format —
   L and R are separate rows, matching the per-side preprocessed images used for training). */
function flattenTrainingRows(rec: CrfRecord): Record<string, unknown>[] {
  return SIDES.map((s) => {
    const g = rec.data?.derived?.[s.k] || ({} as DerivedSide)
    return {
      pid: rec.pid,
      side: s.k,
      category: g.category ?? '',
      label: g.label ?? '',
      lops: g.lops ?? '',
      pad: g.pad ?? '',
      deformity: g.deformity ?? '',
      deformities: (g.deformities || []).join('; '),
      history: g.history ?? '',
    }
  })
}

function StatusPill({ done, doneText, pendingText, onClick, href }: {
  done: boolean
  doneText: string
  pendingText: string
  onClick?: () => void
  href?: string
}) {
  const cls =
    'inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[13px] font-medium transition-colors ' +
    (done
      ? 'bg-cat-0/15 border-cat-0/30 text-cat-0 hover:bg-cat-0/25'
      : 'bg-cat-1/10 border-cat-1/30 text-cat-1 hover:bg-cat-1/20')
  const dot = <span className={'h-1.5 w-1.5 rounded-full ' + (done ? 'bg-cat-0' : 'bg-cat-1')} />
  if (href) {
    return <a href={href} className={cls}>{dot}{done ? doneText : pendingText}</a>
  }
  return <button type="button" onClick={onClick} className={cls}>{dot}{done ? doneText : pendingText}</button>
}

function CellCat({ g }: { g?: DerivedSide }) {
  if (!g || !g.label) return <Badge variant="secondary">ยังไม่สรุป</Badge>
  return (
    <div className="space-y-0.5">
      <Badge className={g.label === 'Positive' ? 'bg-destructive text-white' : 'bg-cat-0 text-white'}>
        {g.label}
      </Badge>
      <div className="text-muted-foreground font-mono text-[11px]">IWGDF {g.category}</div>
    </div>
  )
}

export default function CrfList() {
  const [records, setRecords] = useState<CrfRecord[]>([])
  const [captured, setCaptured] = useState<Set<string>>(new Set())
  const [roiCounts, setRoiCounts] = useState<Record<string, { L: number; R: number }>>({})
  const [toast, setToast] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  async function loadAll() {
    try {
      setRecords(await api<CrfRecord[]>('/api/crf'))
    } catch {
      setRecords([])
    }
    try {
      const rows = await api<ManifestRow[]>('/api/manifest')
      setCaptured(new Set(rows.map((r) => r.research_id)))
    } catch {
      setCaptured(new Set())
    }
    try {
      const rows = await api<RoiSummaryRow[]>('/api/roi')
      const counts: Record<string, { L: number; R: number }> = {}
      rows.forEach((r) => {
        const s = r.summary as { L?: { region_count?: number }; R?: { region_count?: number } }
        counts[r.rid] = { L: s?.L?.region_count || 0, R: s?.R?.region_count || 0 }
      })
      setRoiCounts(counts)
    } catch {
      setRoiCounts({})
    }
  }

  useEffect(() => {
    loadAll()
  }, [])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(''), 6000)
    return () => clearTimeout(t)
  }, [toast])

  const rows = [...records].sort((a, b) => (b.pid || '').localeCompare(a.pid || ''))

  function rowsToCsv(keys: string[], rows: Record<string, unknown>[]): string {
    const cell = (v: unknown) => '"' + String(v === null || v === undefined ? '' : v).replace(/"/g, '""') + '"'
    return keys.join(',') + '\n' + rows.map((r) => keys.map((k) => cell(r[k])).join(',')).join('\n')
  }

  function exportRawFormCsv() {
    if (!records.length) { alert('ยังไม่มีข้อมูลให้ส่งออก'); return }
    const csv = rowsToCsv(RAW_FORM_COLUMNS, records.map(flattenRawForm))
    download(csv, 'CRF07_raw_form_' + today() + '.csv', 'text/csv;charset=utf-8')
  }

  function exportTrainingCsv() {
    if (!records.length) { alert('ยังไม่มีข้อมูลให้ส่งออก'); return }
    const keys = ['pid', 'side', 'category', 'label', 'lops', 'pad', 'deformity', 'deformities', 'history']
    const rows = records.flatMap(flattenTrainingRows)
    const csv = rowsToCsv(keys, rows)
    download(csv, 'IWGDF_training_per_side_' + today() + '.csv', 'text/csv;charset=utf-8')
  }

  async function doDelete(pid: string) {
    try {
      await api('/api/crf/' + encodeURIComponent(pid), undefined, 'DELETE')
      setRecords((rs) => rs.filter((r) => r.pid !== pid))
      setToast('ลบ ' + pid + ' แล้ว')
    } catch (ex) {
      if (ex instanceof ApiError && ex.status === 409) {
        alert('ลบไม่ได้ — เคส ' + pid + ' มีภาพถ่ายแล้ว ต้องลบภาพก่อนจึงจะลบฟอร์มได้')
      } else {
        alert('ลบไม่สำเร็จ' + (ex instanceof ApiError ? ` (${ex.status})` : ''))
      }
      throw ex // keep the confirm dialog open so the user can cancel or retry
    }
  }

  function onRoi(pid: string) {
    if (!captured.has(pid)) {
      alert('เคส ' + pid + ' ยังไม่มีภาพ ต้องถ่ายภาพและผ่าน preprocessing ก่อนจึงจะมาร์ก ROI ได้')
      return
    }
    window.open('via/index.html?rid=' + encodeURIComponent(pid), '_blank')
  }

  return (
    <div className="mx-auto max-w-[1600px] px-4 pb-10">
      <div className="mb-4 mt-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-lg font-bold">ประวัติการบันทึก</div>
          <div className="text-muted-foreground font-mono text-[11px]">Saved records · CRF-07</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={exportRawFormCsv}>CSV ทั้งหมด</Button>
          <Button variant="outline" onClick={exportTrainingCsv}>CSV สำหรับเทรนโมเดล</Button>
          <Button asChild>
            <a href="crf-form.html">บันทึกเคสใหม่</a>
          </Button>
        </div>
      </div>

      {toast && (
        <div className="bg-cat-0/10 border-cat-0 text-cat-0 mb-3.5 rounded-md border px-3.5 py-2.5 text-sm">
          {toast}
        </div>
      )}

      {rows.length === 0 ? (
        <p className="text-muted-foreground py-6 text-sm">
          ยังไม่มีเคสที่บันทึก กด "บันทึกเคสใหม่" เพื่อเริ่มกรอกฟอร์ม
        </p>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>รหัสวิจัย</TableHead>
                <TableHead>วันที่บันทึก</TableHead>
                <TableHead>เวลา</TableHead>
                <TableHead>พยาบาลผู้ตรวจ</TableHead>
                <TableHead>เท้าซ้าย</TableHead>
                <TableHead>เท้าขวา</TableHead>
                <TableHead>ภาพ</TableHead>
                <TableHead>ROI</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => {
                const dt = r.savedAt ? new Date(r.savedAt) : null
                const isCaptured = captured.has(r.pid)
                const counts = roiCounts[r.pid] || { L: 0, R: 0 }
                const statusL = roiSideStatus(r.data?.derived?.L?.label, counts.L)
                const statusR = roiSideStatus(r.data?.derived?.R?.label, counts.R)
                const roiAnyNeeded = statusL !== 'not_needed' || statusR !== 'not_needed'
                const roiAnyDone = statusL === 'done' || statusR === 'done'
                return (
                  <TableRow key={r.pid}>
                    <TableCell className="font-mono font-medium">{r.pid}</TableCell>
                    <TableCell>
                      {dt ? dt.toLocaleDateString('th-TH', { day: '2-digit', month: 'short', year: 'numeric' }) : '–'}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {dt ? dt.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' }) + ' น.' : '–'}
                    </TableCell>
                    <TableCell>
                      {[r.nurse, r.nurse2].filter(Boolean).map((n) => (
                        <div key={n} className="whitespace-nowrap">{n}</div>
                      ))}
                    </TableCell>
                    <TableCell><CellCat g={r.data?.derived?.L} /></TableCell>
                    <TableCell><CellCat g={r.data?.derived?.R} /></TableCell>
                    <TableCell>
                      <StatusPill
                        done={isCaptured}
                        doneText="ถ่ายแล้ว"
                        pendingText="ยังไม่ถ่าย"
                        href={`capture.html?rid=${encodeURIComponent(r.pid)}`}
                      />
                    </TableCell>
                    <TableCell>
                      <div className="text-[11px] whitespace-nowrap">
                        <div className={statusL === 'done' ? 'text-cat-0' : statusL === 'pending' ? 'text-cat-1' : 'text-muted-foreground'}>
                          ซ้าย: {ROI_STATUS_TEXT[statusL]}
                        </div>
                        <div className={statusR === 'done' ? 'text-cat-0' : statusR === 'pending' ? 'text-cat-1' : 'text-muted-foreground'}>
                          ขวา: {ROI_STATUS_TEXT[statusR]}
                        </div>
                      </div>
                      {roiAnyNeeded && (
                        <Button
                          size="sm"
                          variant={roiAnyDone ? 'outline' : 'default'}
                          className="mt-1 h-6 px-2 text-[11px]"
                          onClick={() => onRoi(r.pid)}
                        >
                          {roiAnyDone ? 'เปิด ROI' : 'ทำ ROI'} →
                        </Button>
                      )}
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap">
                      <Button size="sm" variant="ghost" asChild>
                        <a href={`crf-detail.html?pid=${encodeURIComponent(r.pid)}`}>ดูรายละเอียด</a>
                      </Button>
                      <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive" onClick={() => setDeleteTarget(r.pid)}>ลบ</Button>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {deleteTarget && (
        <DeleteConfirmDialog
          open={!!deleteTarget}
          onOpenChange={(o) => !o && setDeleteTarget(null)}
          code={deleteTarget}
          title={`ลบ ${deleteTarget} ออกจากประวัติ`}
          description="การลบนี้ถาวรและกู้คืนไม่ได้ — ลบได้เฉพาะเคสที่ยังไม่มีภาพถ่ายผูกอยู่"
          onConfirm={() => doDelete(deleteTarget)}
        />
      )}
    </div>
  )
}
