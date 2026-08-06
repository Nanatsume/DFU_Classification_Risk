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

function flatten(rec: CrfRecord): Record<string, unknown> {
  const row: Record<string, unknown> = {
    pid: rec.pid,
    savedAt: rec.savedAt,
    nurse: rec.nurse,
    nurse2: rec.nurse2,
  }
  const fields = rec.data?.fields || {}
  Object.keys(fields).forEach((k) => {
    if (k !== 'pid' && k !== 'nurse' && k !== 'nurse2') row[k] = fields[k]
  })
  ;(['L', 'R'] as const).forEach((side) => {
    const g = rec.data?.derived?.[side] || ({} as DerivedSide)
    row['iwgdf_' + side] = g.category
    row['label_' + side] = g.label
    row['lops_' + side] = g.lops
    row['pad_' + side] = g.pad
    row['deformity_' + side] = g.deformity
  })
  return row
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
  const [roiDone, setRoiDone] = useState<Set<string>>(new Set())
  const [toast, setToast] = useState('')

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
      setRoiDone(new Set(rows.map((r) => r.rid)))
    } catch {
      setRoiDone(new Set())
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

  function exportCsv() {
    if (!records.length) {
      alert('ยังไม่มีข้อมูลให้ส่งออก')
      return
    }
    const flat = records.map(flatten)
    const keys: string[] = []
    flat.forEach((r) => Object.keys(r).forEach((k) => { if (!keys.includes(k)) keys.push(k) }))
    const cell = (v: unknown) => '"' + String(v === null || v === undefined ? '' : v).replace(/"/g, '""') + '"'
    const csv = keys.join(',') + '\n' + flat.map((r) => keys.map((k) => cell(r[k])).join(',')).join('\n')
    download(csv, 'CRF07_records_' + today() + '.csv', 'text/csv;charset=utf-8')
  }

  async function onDelete(pid: string) {
    if (!confirm('ลบ ' + pid + ' ออกจากประวัติ?')) return
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
    <div className="mx-auto max-w-5xl px-4 pb-10">
      <div className="mb-4 mt-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-lg font-bold">ประวัติการบันทึก</div>
          <div className="text-muted-foreground font-mono text-[11px]">Saved records · CRF-07</div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={exportCsv}>ส่งออก CSV ทั้งหมด</Button>
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
                const isRoi = roiDone.has(r.pid)
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
                      <Button size="sm" variant={isCaptured ? 'secondary' : 'outline'} asChild>
                        <a href={`capture.html?rid=${encodeURIComponent(r.pid)}`}>
                          {isCaptured ? 'ถ่ายแล้ว' : 'ยังไม่ถ่าย'}
                        </a>
                      </Button>
                    </TableCell>
                    <TableCell>
                      <Button size="sm" variant={isRoi ? 'secondary' : 'outline'} onClick={() => onRoi(r.pid)}>
                        {isRoi ? 'ทำแล้ว' : 'ยังไม่ทำ'}
                      </Button>
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap">
                      <Button size="sm" variant="ghost" asChild>
                        <a href={`crf-detail.html?pid=${encodeURIComponent(r.pid)}`}>ดูรายละเอียด</a>
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => onDelete(r.pid)}>ลบ</Button>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
