import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

interface CaseRow {
  research_id: string
  nurse: string
  iwgdf: { L: number | null; R: number | null }
  has_podo: boolean
  has_thermal: boolean
}
interface RoiSummaryRow {
  rid: string
}

export default function Home() {
  const [crfCount, setCrfCount] = useState<number | null>(null)
  const [roiOpen, setRoiOpen] = useState(false)
  const [roiLoading, setRoiLoading] = useState(false)
  const [readyCases, setReadyCases] = useState<CaseRow[] | null>(null)
  const [roiDone, setRoiDone] = useState<Set<string>>(new Set())
  const [roiError, setRoiError] = useState(false)

  useEffect(() => {
    api<Record<string, unknown>[]>('/api/crf')
      .then((rows) => setCrfCount(rows.length))
      .catch(() => {
        /* not logged in yet / server unreachable — leave blank */
      })
  }, [])

  async function toggleRoiPicker() {
    if (roiOpen) {
      setRoiOpen(false)
      return
    }
    setRoiOpen(true)
    setRoiLoading(true)
    setRoiError(false)
    try {
      const [cases, roi] = await Promise.all([
        api<CaseRow[]>('/api/cases'),
        api<RoiSummaryRow[]>('/api/roi'),
      ])
      setReadyCases(cases.filter((c) => c.has_podo && c.has_thermal))
      setRoiDone(new Set(roi.map((r) => r.rid)))
    } catch {
      setRoiError(true)
    } finally {
      setRoiLoading(false)
    }
  }

  return (
    <header className="border-b-0">
      <div className="bg-foreground mb-6 px-4 py-7 text-[#e8eef1]">
        <div className="mx-auto max-w-5xl">
          <div className="font-mono text-[11px] tracking-[0.2em] text-[#7fb3b8] uppercase">
            Data collection system
          </div>
          <h1 className="mt-1.5 text-2xl leading-tight font-bold sm:text-[27px]">
            ระบบเก็บข้อมูลความเสี่ยงเท้าเบาหวาน
          </h1>
          <p className="mt-2 max-w-[70ch] text-[13px] text-[#a9bec8]">
            โครงการพัฒนาแบบจำลองทำนายความเสี่ยงแผลเบาหวานที่เท้า
            โดยใช้ข้อมูลโพโดสโคปร่วมกับการอธิบายผลด้วยปัญญาประดิษฐ์แบบอธิบายได้ (XAI)
          </p>
          <p className="mt-2.5 border-t border-[#2a3f4d] pt-2.5 text-xs text-[#7c95a2]">
            โรงพยาบาลพุทธชินราช พิษณุโลก · คณะเทคโนโลยีสารสนเทศและการสื่อสาร มหาวิทยาลัยมหิดล
          </p>
        </div>
      </div>

      <div className="mx-auto grid max-w-5xl grid-cols-1 gap-4 px-4 pb-10 sm:grid-cols-2">
        <Card className="border-l-primary flex flex-col border-l-[5px] p-5 sm:col-span-2">
          <div className="text-muted-foreground font-mono text-[11px] tracking-[0.2em]">01</div>
          <div className="text-primary my-2 text-lg font-bold">
            แบบบันทึกข้อมูลการประเมินความเสี่ยงเท้าเบาหวาน
          </div>
          <p className="text-muted-foreground mb-4 flex-1 text-[13.5px] leading-relaxed">
            กรอกผลตรวจเท้าเบาหวานทีละเคส ระบบสรุปประเภทความเสี่ยง IWGDF และ Binary label
            ให้จากผลที่กรอก
          </p>
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <a href="crf-form.html">บันทึกเคสใหม่</a>
            </Button>
            <Button variant="outline" asChild>
              <a href="crf-list.html">
                ประวัติการบันทึก {crfCount !== null && crfCount > 0 ? `(${crfCount} เคส)` : ''}
              </a>
            </Button>
          </div>
        </Card>

        <Card className="flex flex-col border-l-[5px] border-l-[#7c3a66] p-5">
          <div className="text-muted-foreground font-mono text-[11px] tracking-[0.2em]">02</div>
          <div className="my-2 text-lg font-bold text-[#7c3a66]">ถ่ายภาพเก็บข้อมูล</div>
          <p className="text-muted-foreground mb-4 flex-1 text-[13.5px] leading-relaxed">
            ถ่ายภาพฝ่าเท้าด้วยโพโดสโคป แล้วผูกภาพเข้ากับรหัสวิจัยของเคสที่บันทึกไว้
            ต้องกรอกแบบฟอร์มของเคสนั้นก่อนจึงจะถ่ายภาพได้
          </p>
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <a href="capture.html">เลือกเคสที่จะถ่ายภาพ</a>
            </Button>
          </div>
        </Card>

        <Card className="flex flex-col border-l-[5px] border-l-[#96700a] p-5">
          <div className="text-muted-foreground font-mono text-[11px] tracking-[0.2em]">03</div>
          <div className="my-2 text-lg font-bold text-[#8a6609]">ทำ ROI ในภาพ</div>
          <p className="text-muted-foreground mb-4 flex-1 text-[13.5px] leading-relaxed">
            มาร์กบริเวณแรงกดที่เสี่ยงบนภาพฝ่าเท้าด้วย VIA 2 ทำหลังถ่ายภาพและผ่าน preprocessing แล้ว
          </p>
          <div className="flex flex-wrap gap-2">
            <Button onClick={toggleRoiPicker}>เลือกเคสที่จะทำ ROI</Button>
          </div>
          {roiOpen && (
            <div className="mt-3.5 space-y-2">
              {roiLoading && (
                <div className="text-muted-foreground text-[12.5px] italic">กำลังโหลด…</div>
              )}
              {!roiLoading && roiError && (
                <div className="text-muted-foreground text-[12.5px] italic">
                  โหลดรายการไม่ได้ — ตรวจสอบว่าต่อกับเซิร์ฟเวอร์อยู่
                </div>
              )}
              {!roiLoading && !roiError && readyCases?.length === 0 && (
                <div className="text-muted-foreground text-[12.5px] italic">
                  ยังไม่มีเคสที่ถ่ายภาพครบทั้งสองส่วน
                </div>
              )}
              {!roiLoading &&
                !roiError &&
                readyCases?.map((c) => (
                  <div
                    key={c.research_id}
                    className="bg-secondary flex items-center gap-3 rounded-md border px-3 py-2"
                  >
                    <span className="text-primary font-mono text-sm font-bold">
                      {c.research_id}
                    </span>
                    <span className="text-muted-foreground flex-1 text-[11.5px]">
                      {c.nurse || '—'}
                    </span>
                    <Button variant="outline" size="sm" asChild>
                      <a
                        href={`via/index.html?rid=${encodeURIComponent(c.research_id)}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {roiDone.has(c.research_id) ? 'เปิด ROI →' : 'ทำ ROI →'}
                      </a>
                    </Button>
                  </div>
                ))}
            </div>
          )}
        </Card>
      </div>
    </header>
  )
}
