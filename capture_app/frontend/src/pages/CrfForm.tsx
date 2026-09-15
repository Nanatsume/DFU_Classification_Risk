import { useEffect, useMemo, useState } from 'react'
import { api } from '@/lib/api'
import { DEFORM, MF_SITES, SIDES, evalSide, overallMissing, toDerived, type Fields, type Side } from '@/lib/crfScoring'
import { clearDraft, draftAnswerCount, isEmptyDraft, readDraft, writeDraft } from '@/lib/crfDraft'
import type { CrfRecord } from '@/lib/crfTypes'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'

function Seg({ value, onChange, options, disabled }: {
  value: string | undefined
  onChange: (v: string) => void
  options: { v: string; t: string }[]
  disabled?: boolean
}) {
  return (
    <div className={'inline-flex overflow-hidden rounded-md border ' + (disabled ? 'opacity-45' : '')}>
      {options.map((o) => (
        <button
          key={o.v}
          type="button"
          disabled={disabled}
          onClick={() => onChange(o.v)}
          className={
            'border-r px-3.5 py-1.5 font-mono text-[13px] last:border-r-0 disabled:cursor-not-allowed ' +
            (value === o.v ? 'bg-foreground text-white' : 'bg-card text-muted-foreground hover:bg-secondary')
          }
        >
          {o.t}
        </button>
      ))}
    </div>
  )
}

function Verdict({ text, tone }: { text: string; tone?: 'ok' | 'bad' | 'warn' }) {
  const cls =
    tone === 'ok' ? 'bg-cat-0/15 text-cat-0'
    : tone === 'bad' ? 'bg-destructive/15 text-destructive'
    : tone === 'warn' ? 'bg-cat-2/15 text-cat-2'
    : 'bg-secondary text-muted-foreground'
  return (
    <span className={'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[13px] font-semibold ' + cls}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {text}
    </span>
  )
}

function Panel({ side, children }: { side: Side; children: React.ReactNode }) {
  const sd = SIDES.find((s) => s.k === side)!
  const tint = side === 'L' ? { border: '#0f6a80', bg: '#f0f7f9', chip: '#d9eaef' } : { border: '#7c3a66', bg: '#faf1f6', chip: '#eedde7' }
  return (
    <div className="overflow-hidden rounded-md border" style={{ borderLeftColor: tint.border, borderLeftWidth: 5, background: tint.bg }}>
      <div className="flex items-center justify-between gap-2.5 px-4 py-2.5 font-bold" style={{ background: tint.chip, color: tint.border }}>
        <span>{sd.th}</span>
        <span className="rounded px-2 py-1 font-mono text-[10.5px] tracking-wider text-white" style={{ background: tint.border }}>{sd.en}</span>
      </div>
      <div className="space-y-3.5 p-4">{children}</div>
    </div>
  )
}

const ABI_OPTS = [
  { v: 'normal', label: 'ปกติ', sub: '0.90 – 1.30' },
  { v: 'pad', label: 'PAD', sub: 'น้อยกว่า 0.90' },
  { v: 'calcified', label: 'หลอดเลือดแข็งตัว', sub: 'มากกว่า 1.30' },
]
const TBI_OPTS = [
  { v: 'normal', label: 'ปกติ', sub: '0.70 ขึ้นไป' },
  { v: 'pad', label: 'PAD', sub: 'น้อยกว่า 0.70' },
]

export default function CrfForm() {
  const [pid, setPid] = useState('')
  const [pidNote, setPidNote] = useState('')
  const [fields, setFields] = useState<Fields>({})
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [isEdit, setIsEdit] = useState(false)
  // Drafts are only written once the initial load has settled, so the empty state React starts
  // with cannot overwrite a real draft before it has been offered to the nurse.
  const [draftReady, setDraftReady] = useState(false)

  const setF = (key: string, v: string | boolean) => setFields((f) => ({ ...f, [key]: v }))

  const evals = useMemo(
    () => ({ L: evalSide(fields, 'L'), R: evalSide(fields, 'R') }),
    [fields],
  )
  const missing = useMemo(
    () => overallMissing(fields, evals),
    [fields, evals],
  )

  useEffect(() => {
    ;(async () => {
      const editPid = new URLSearchParams(location.search).get('edit')
      if (editPid) {
        try {
          const rec = await api<CrfRecord>('/api/crf/' + encodeURIComponent(editPid))
          setIsEdit(true)
          setPid(rec.pid)
          setPidNote('กำลังแก้ไขเคสที่บันทึกไว้')
          setNote((rec.data?.fields?.note as string) || '')
          setFields(rec.data?.fields || {})
          return
        } catch {
          alert('โหลดเคส ' + editPid + ' ไม่สำเร็จ — เริ่มเคสใหม่แทน')
        }
      }
      // New case: no id is requested here on purpose. The server mints it when the form is
      // saved, so opening this page and walking away costs nothing.
      setPidNote('ระบบจะออกรหัสให้อัตโนมัติเมื่อกดบันทึก')

      // Offer back anything a previous session left unsaved — a reload, or a phone browser
      // dropping a backgrounded tab, would otherwise lose the whole examination.
      const draft = readDraft()
      if (draft && !isEmptyDraft(draft)) {
        const when = new Date(draft.savedAt).toLocaleString('th-TH', {
          dateStyle: 'short', timeStyle: 'short',
        })
        const prompt =
          `พบฟอร์มที่กรอกค้างไว้ ${draftAnswerCount(draft)} ช่อง (${when})` +
          '\n\nต้องการกรอกต่อจากเดิมหรือไม่?' +
          '\nกดยกเลิกเพื่อเริ่มเคสใหม่ — ข้อมูลที่ค้างไว้จะถูกลบทิ้ง'
        if (confirm(prompt)) {
          setFields(draft.fields as Fields)
          setNote(draft.note)
        } else {
          clearDraft()
        }
      }
      setDraftReady(true)
    })()
  }, [])

  // Autosave. Cheap enough to run on every keystroke — the payload is a few hundred bytes, and
  // debouncing would risk losing the last edits at exactly the moment the tab is evicted.
  useEffect(() => {
    if (!draftReady || isEdit) return
    writeDraft({ fields, note })
  }, [draftReady, isEdit, fields, note])

  async function onSave() {
    if (missing.length && !confirm(`ยังกรอกไม่ครบ ${missing.length} รายการ:\n${missing.slice(0, 8).join(' · ')}\n\nบันทึกเลยหรือไม่?`)) return
    setSaving(true)
    const data = {
      form: 'CRF-07',
      savedAt: new Date().toISOString(),
      fields: { ...fields, note },
      derived: { L: toDerived(evals.L), R: toDerived(evals.R) },
    }
    try {
      // pid is '' for a new case — the server mints it and returns the saved record; that
      // response is the only place the client learns the id.
      const saved = await api<CrfRecord>('/api/crf', { pid, savedAt: new Date().toISOString(), data })
      clearDraft()  // only once the server has it — a failed save must keep the draft
      location.href = 'crf-detail.html?pid=' + encodeURIComponent(saved.pid)
    } catch {
      alert('บันทึกไม่สำเร็จ — ตรวจสอบว่าต่อกับเซิร์ฟเวอร์อยู่แล้วลองอีกครั้ง')
      setSaving(false)
    }
  }
  function onClear() {
    if (!confirm('ล้างข้อมูลที่กรอกในฟอร์มนี้?')) return
    setFields({})
    setNote('')
    clearDraft()
  }

  return (
    // เผื่อพื้นที่ด้านล่างมากขึ้นบนจอมือถือ — แถบสรุปด้านล่าง (sticky dock) มีเนื้อหาเยอะกว่าจะพอดี
    // แถวเดียวแบบจอคอม พอ wrap เป็นหลายแถวบนจอแคบก็จะสูงขึ้นมาก ถ้าเผื่อพื้นที่ไม่พอ แถบจะไปทับ
    // เนื้อหาท้ายฟอร์มได้ (ตัวเลขนี้ประมาณคร่าวๆ ยังไม่เคยเห็นบนมือถือจริง อาจต้องปรับอีกทีหลังลองจริง)
    <div className="pb-[260px] sm:pb-36 print:pb-0">
      <div className="bg-foreground mb-6 px-4 py-6 text-[#e8eef1]">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-4">
          <div>
            <div className="font-mono text-[11px] tracking-[0.22em] text-[#7fb3b8] uppercase">Case record form · CRF-07</div>
            <h1 className="mt-1 text-2xl font-bold">แบบบันทึกข้อมูลการประเมินความเสี่ยงเท้าเบาหวาน</h1>
          </div>
          <div>
            <div className="font-mono text-[11px] tracking-[0.14em] text-[#7fb3b8] uppercase">รหัสวิจัย</div>
            <div className="mt-1 rounded bg-[#1d3241] px-3 py-1.5 font-mono text-base text-[#8fdae4]">{pid || 'ออกให้เมื่อบันทึก'}</div>
            {pidNote && <div className="mt-1 font-mono text-[10.5px] text-[#5f8f97]">{pidNote}</div>}
          </div>
        </div>
      </div>

      <main className="mx-auto max-w-[1600px] space-y-6 px-4">
        {/* ก — LOPS */}
        <section>
          <h2 className="mb-2.5 flex items-center gap-3">
            <span className="bg-foreground grid h-7 w-7 place-items-center rounded-full font-bold text-white">ก</span>
            <span>
              <div className="text-lg font-bold">การตรวจสูญเสียความรู้สึกป้องกันตัวที่เท้า</div>
              <div className="text-muted-foreground font-mono text-[11px] uppercase">Loss of protective sensation (LOPS)</div>
            </span>
          </h2>
          <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
            {SIDES.map((s) => (
              <Panel key={s.k} side={s.k}>
                <div>
                  <div className="text-[13.5px] font-semibold">เส้นใยโมโนฟิลาเมนต์ 10 กรัม</div>
                  <div className="text-muted-foreground mb-2 text-xs">Monofilament · เลือก "รู้สึก" หรือ "ไม่รู้สึก" ทั้ง 3 ตำแหน่ง</div>
                  {MF_SITES.map((m) => (
                    <div key={m.k} className="flex items-center justify-between border-b border-dotted py-1.5 last:border-0">
                      <span className="text-[13.5px]">{m.th}</span>
                      <Seg
                        value={fields[`mf_${s.k}_${m.k}`] as string}
                        onChange={(v) => setF(`mf_${s.k}_${m.k}`, v)}
                        options={[{ v: 'y', t: '✓ รู้สึก' }, { v: 'n', t: '✗ ไม่รู้สึก' }]}
                      />
                    </div>
                  ))}
                </div>
                <Verdict
                  text={
                    evals[s.k].lops === true ? `มี LOPS — รู้สึก ${MF_SITES.filter((m) => fields[`mf_${s.k}_${m.k}`] === 'y').length}/3 จุด`
                    : evals[s.k].lops === false ? `ไม่มี LOPS — รู้สึก ${MF_SITES.filter((m) => fields[`mf_${s.k}_${m.k}`] === 'y').length}/3 จุด`
                    : 'LOPS — รอข้อมูล'
                  }
                  tone={evals[s.k].lops === true ? 'bad' : evals[s.k].lops === false ? 'ok' : undefined}
                />
              </Panel>
            ))}
          </div>
        </section>

        {/* ข — PAD */}
        <section>
          <h2 className="mb-2.5 flex items-center gap-3">
            <span className="bg-foreground grid h-7 w-7 place-items-center rounded-full font-bold text-white">ข</span>
            <span>
              <div className="text-lg font-bold">การตรวจโรคหลอดเลือดแดงส่วนปลาย</div>
              <div className="text-muted-foreground font-mono text-[11px] uppercase">Peripheral arterial disease (PAD)</div>
            </span>
          </h2>
          <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
            {SIDES.map((s) => (
              <Panel key={s.k} side={s.k}>
                <div>
                  <div className="text-[13.5px] font-semibold">ดัชนีข้อเท้าต่อแขน (ABI)</div>
                  <div className="text-muted-foreground mb-2 text-xs">แตะเลือกช่วงค่าที่วัดได้</div>
                  <div className="grid gap-1.5">
                    {ABI_OPTS.map((o) => (
                      <label key={o.v} className={'flex cursor-pointer items-center gap-2 rounded-md border bg-card px-2.5 py-1.5 text-[13.5px] ' + (fields[`abi_${s.k}`] === o.v ? 'border-foreground' : '')}>
                        <input type="radio" className="accent-foreground" checked={fields[`abi_${s.k}`] === o.v} onChange={() => setF(`abi_${s.k}`, o.v)} />
                        {o.label} <b className="font-mono font-medium">{o.sub}</b>
                      </label>
                    ))}
                  </div>
                </div>
                <div className={evals[s.k].needTbi ? '' : 'opacity-45'}>
                  <div className="text-[13.5px] font-semibold">ดัชนีนิ้วเท้าต่อแขน (TBI)</div>
                  <div className="text-muted-foreground mb-2 text-xs">{evals[s.k].needTbi ? 'ABI สูงเกิน 1.30 ต้องเลือกผล TBI' : 'ใช้เมื่อ ABI มากกว่า 1.30'}</div>
                  <div className="grid gap-1.5">
                    {TBI_OPTS.map((o) => (
                      <label key={o.v} className={'flex items-center gap-2 rounded-md border bg-card px-2.5 py-1.5 text-[13.5px] ' + (evals[s.k].needTbi ? 'cursor-pointer' : 'cursor-not-allowed')}>
                        <input
                          type="radio"
                          disabled={!evals[s.k].needTbi}
                          className="accent-foreground"
                          checked={fields[`tbi_${s.k}`] === o.v}
                          onChange={() => setF(`tbi_${s.k}`, o.v)}
                        />
                        {o.label} <b className="font-mono font-medium">{o.sub}</b>
                      </label>
                    ))}
                  </div>
                </div>
                <Verdict
                  text={evals[s.k].pad === true ? 'มี PAD' : evals[s.k].pad === false ? 'ไม่มี PAD' : 'PAD — รอข้อมูล'}
                  tone={evals[s.k].pad === true ? 'bad' : evals[s.k].pad === false ? 'ok' : undefined}
                />
              </Panel>
            ))}
          </div>
        </section>

        {/* ค — Deformity */}
        <section>
          <h2 className="mb-2.5 flex items-center gap-3">
            <span className="bg-foreground grid h-7 w-7 place-items-center rounded-full font-bold text-white">ค</span>
            <span>
              <div className="text-lg font-bold">การตรวจความผิดปกติของเท้า</div>
              <div className="text-muted-foreground font-mono text-[11px] uppercase">Foot deformities</div>
            </span>
          </h2>
          <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
            {SIDES.map((s) => (
              <Panel key={s.k} side={s.k}>
                <div className="text-muted-foreground text-xs">ทำเครื่องหมายทั้งหมดที่พบ</div>
                {DEFORM.map((g) => (
                  <div key={g.g}>
                    <div className="border-b py-1 text-xs font-semibold">{g.g}</div>
                    <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
                      {g.items.map((i) => (
                        <label key={i.k} className="flex cursor-pointer items-start gap-2 rounded px-1.5 py-1 text-[13px] hover:bg-white/60">
                          <input
                            type="checkbox"
                            className="mt-0.5 accent-foreground"
                            checked={!!fields[`def_${s.k}_${i.k}`]}
                            onChange={(e) => setF(`def_${s.k}_${i.k}`, e.target.checked)}
                          />
                          <span>{i.th}{i.en && <span className="text-muted-foreground"> ({i.en})</span>}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
                <Verdict
                  text={evals[s.k].deform ? `พบความผิดปกติ ${evals[s.k].deformList.length} รายการ` : 'ไม่พบความผิดปกติ'}
                  tone={evals[s.k].deform ? 'warn' : 'ok'}
                />
              </Panel>
            ))}
          </div>
        </section>

        {/* ง — History */}
        <section>
          <h2 className="mb-2.5 flex items-center gap-3">
            <span className="bg-foreground grid h-7 w-7 place-items-center rounded-full font-bold text-white">ง</span>
            <span>
              <div className="text-lg font-bold">ประวัติแผลและการตัดรยางค์</div>
              <div className="text-muted-foreground font-mono text-[11px] uppercase">Ulcer history · amputation · ESRD</div>
            </span>
          </h2>
          <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
            {SIDES.map((s) => (
              <Panel key={s.k} side={s.k}>
                <div>
                  <div className="text-[13.5px] font-semibold">ประวัติแผลเบาหวานที่เท้า</div>
                  <Seg value={fields[`ulcer_${s.k}`] as string} onChange={(v) => setF(`ulcer_${s.k}`, v)} options={[{ v: 'no', t: 'ไม่มีประวัติ' }, { v: 'yes', t: 'มีประวัติแผล' }]} />
                </div>
                <div>
                  <div className="text-[13.5px] font-semibold">การตัดรยางค์ล่าง</div>
                  <div className="text-muted-foreground mb-1 text-xs">Lower-extremity amputation</div>
                  <Seg value={fields[`amp_${s.k}`] as string} onChange={(v) => setF(`amp_${s.k}`, v)} options={[{ v: 'no', t: 'ไม่มี' }, { v: 'yes', t: 'มี' }]} />
                </div>
                {evals[s.k].historyOnly && (
                  <div className="bg-cat-1/10 border-cat-1 text-cat-1 rounded-md border px-2.5 py-2 text-xs leading-relaxed">
                    มีประวัติแผล / ตัดรยางค์ / ไตวายระยะสุดท้าย แต่ตรวจไม่พบทั้ง LOPS และ PAD จึงยังไม่เข้าเกณฑ์ประเภท 3
                  </div>
                )}
              </Panel>
            ))}
          </div>
          <Card className="mt-3.5 p-4">
            <div className="text-[13.5px] font-semibold">ไตวายระยะสุดท้าย (CKD stage 5)</div>
            <div className="text-muted-foreground mb-2 text-xs">ข้อมูลระดับผู้ป่วย มีผลกับทั้งสองข้าง</div>
            <Seg value={fields.ckd as string} onChange={(v) => setF('ckd', v)} options={[{ v: 'no', t: 'ไม่มี' }, { v: 'yes', t: 'มี' }]} />
          </Card>
        </section>

        {/* จ — Notes + signatures */}
        <section>
          <h2 className="mb-2.5 flex items-center gap-3">
            <span className="bg-foreground grid h-7 w-7 place-items-center rounded-full font-bold text-white">จ</span>
            <span>
              <div className="text-lg font-bold">หมายเหตุและผู้บันทึก</div>
              <div className="text-muted-foreground font-mono text-[11px] uppercase">Notes · signatures</div>
            </span>
          </h2>
          <Card className="mb-3.5 p-4">
            <label className="mb-0.5 block text-[13.5px] font-semibold">หมายเหตุ</label>
            <div className="text-muted-foreground mb-2 text-xs">บันทึกสิ่งที่ตรวจพบเพิ่มเติม หรือเหตุผลที่ปรับประเภทความเสี่ยงเอง</div>
            <Textarea value={note} onChange={(e) => setNote(e.target.value)} className="min-h-[84px]" />
          </Card>
        </section>
      </main>

      {/* sticky summary dock — position:fixed elements don't respect page breaks when printed,
          the browser re-renders them at the same viewport position on every printed page, so
          this would otherwise cut across/overlap the form content mid-page (that's the bug
          reported: "พิมพ์ออกมาไม่เหมือนที่โชว์"). Hide it for print — it's a UI control (buttons,
          live scoring), not part of the CRF-07 content that's meant to end up on paper. */}
      <div className="bg-foreground fixed inset-x-0 bottom-0 z-20 border-t-4 border-primary text-[#e8eef1] shadow-[0_-6px_24px_rgba(19,36,48,.22)] print:hidden">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-4.5 px-4 py-2.5">
          {SIDES.map((s) => (
            <div key={s.k} className="flex items-center gap-2.5 border-l-[3px] pl-2.5" style={{ borderLeftColor: s.k === 'L' ? '#4fb3c4' : '#c98ab5' }}>
              <div
                className="grid h-[42px] w-[42px] place-items-center rounded-md font-mono text-xl font-medium"
                style={{
                  background: evals[s.k].autoCat === null ? '#2a3f4d'
                    : evals[s.k].autoCat === 0 ? 'var(--cat-0)' : evals[s.k].autoCat === 1 ? 'var(--cat-1)' : evals[s.k].autoCat === 2 ? 'var(--cat-2)' : 'var(--cat-3)',
                  color: evals[s.k].autoCat === null ? '#9fb6c2' : '#fff',
                }}
              >
                {evals[s.k].autoCat ?? '–'}
              </div>
              <div className="text-xs text-[#a9bec8]">
                <b className="block text-[13.5px] text-white">{s.th}</b>
                {evals[s.k].autoCat === null
                  ? (evals[s.k].missing.length ? 'ยังขาด: ' + evals[s.k].missing.slice(0, 2).join(', ') : 'ยังไม่ได้ประเมิน')
                  : (evals[s.k].autoCat! >= 1 ? 'Positive' : 'Negative')}
              </div>
            </div>
          ))}
          <div className="text-[#f0b2bb] w-full text-xs sm:w-auto" title={missing.join(' · ')}>
            {missing.length ? `ยังไม่ครบ ${missing.length} รายการ` : ''}
          </div>
          {/* จอมือถือ: ปุ่มเรียงกริด 2 คอลัมน์เต็มแถว กดง่ายกว่าปุ่มแถวเดียวบีบกันจนเล็ก
              จอใหญ่ (sm+): กลับไปเป็นแถวเดียวชิดขวาเหมือนเดิม */}
          <div className="mt-1 grid w-full grid-cols-2 gap-2 sm:mt-0 sm:ml-auto sm:flex sm:w-auto sm:flex-wrap">
            <Button type="button" variant="outline" className="border-[#47606f] bg-transparent text-[#dce7ec] hover:bg-[#1d3241]" asChild>
              <a href="index.html">หน้าแรก</a>
            </Button>
            <Button type="button" variant="outline" className="border-[#47606f] bg-transparent text-[#dce7ec] hover:bg-[#1d3241]" asChild>
              <a href="crf-list.html">ประวัติการบันทึก</a>
            </Button>
            <Button type="button" variant="outline" className="border-[#47606f] bg-transparent text-[#dce7ec] hover:bg-[#1d3241]" onClick={() => window.print()}>
              พิมพ์ / PDF
            </Button>
            <Button type="button" variant="outline" className="border-[#47606f] bg-transparent text-[#dce7ec] hover:bg-[#1d3241]" onClick={onClear}>
              ล้างฟอร์ม
            </Button>
            <Button type="button" className="col-span-2 sm:col-span-1" disabled={saving} onClick={onSave}>บันทึกข้อมูล</Button>
          </div>
        </div>
      </div>
    </div>
  )
}
