import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export default function Home() {
  const [crfCount, setCrfCount] = useState<number | null>(null)

  useEffect(() => {
    api<Record<string, unknown>[]>('/api/crf')
      .then((rows) => setCrfCount(rows.length))
      .catch(() => {
        /* not logged in yet / server unreachable — leave blank */
      })
  }, [])

  return (
    <header className="border-b-0">
      <div className="bg-foreground mb-6 px-4 py-7 text-[#e8eef1]">
        <div className="mx-auto max-w-[1600px]">
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

      <div className="mx-auto grid max-w-[1600px] grid-cols-1 gap-4 px-4 pb-10 sm:grid-cols-2">
        <Card className="border-l-primary flex flex-col border-l-[5px] p-5">
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
            <Button asChild>
              <a href="roi.html">เลือกเคสที่จะทำ ROI</a>
            </Button>
          </div>
        </Card>

        <Card className="flex flex-col border-l-[5px] border-l-[#2f5e7c] p-5">
          <div className="text-muted-foreground font-mono text-[11px] tracking-[0.2em]">04</div>
          <div className="my-2 text-lg font-bold text-[#2f5e7c]">ประวัติการบันทึก</div>
          <p className="text-muted-foreground mb-4 flex-1 text-[13.5px] leading-relaxed">
            ดูภาพรวมทุกเคส — ฟอร์มที่กรอก (01), สถานะถ่ายภาพ (02), และสถานะ ROI (03) รวมไว้ในตารางเดียว
          </p>
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <a href="crf-list.html">
                ดูประวัติทั้งหมด {crfCount !== null && crfCount > 0 ? `(${crfCount} เคส)` : ''}
              </a>
            </Button>
          </div>
        </Card>

        <Card className="flex flex-col border-l-[5px] border-l-[#4b5563] p-5 sm:col-span-2">
          <div className="text-muted-foreground font-mono text-[11px] tracking-[0.2em]">05</div>
          <div className="my-2 text-lg font-bold text-[#4b5563]">คลังภาพ</div>
          <p className="text-muted-foreground mb-4 flex-1 text-[13.5px] leading-relaxed">
            ไล่ดูรูปทุกเคสที่บันทึกแล้วในหน้าเดียว (podoscope, thermal, ซ้าย/ขวา) เช็คคุณภาพภาพก่อนเอาไปเทรนโมเดล
          </p>
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <a href="gallery.html">เปิดคลังภาพ</a>
            </Button>
          </div>
        </Card>
      </div>
    </header>
  )
}
