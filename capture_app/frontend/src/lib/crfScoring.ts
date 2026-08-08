// The IWGDF risk-scoring engine — ported field-for-field from the vanilla evalSide()/collect()/
// restore() in the pre-React crf-form.html. Pure functions operating on a plain field map instead
// of reading the DOM directly, so the exact same branching logic drives React state. Do not change
// the branch order or conditions without re-running the same P0003 regression case used earlier
// this session (L: all monofilament felt + ABI normal + no history -> category 0/Negative;
// R: all monofilament not felt + ABI pad -> category 2/Positive).

export const SIDES = [
  { k: 'L' as const, th: 'เท้าซ้าย', en: 'LEFT' },
  { k: 'R' as const, th: 'เท้าขวา', en: 'RIGHT' },
]
export type Side = (typeof SIDES)[number]['k']

export const MF_SITES = [
  { k: 'hallux', th: 'หัวแม่เท้า' },
  { k: 'mth1', th: 'MTH ที่ 1' },
  { k: 'mth5', th: 'MTH ที่ 5' },
]

export const DEFORM = [
  {
    g: 'ความผิดปกติของนิ้วเท้า',
    items: [
      { k: 'hammer', th: 'นิ้วเท้าโก่ง', en: 'Hammer toe' },
      { k: 'mallet', th: 'นิ้วเท้าพับ', en: 'Mallet toe' },
      { k: 'claw', th: 'นิ้วเท้างอ', en: 'Claw toe' },
      { k: 'hallux', th: 'นิ้วหัวแม่เท้าเอียง', en: 'Hallux valgus' },
    ],
  },
  {
    g: 'อุ้งเท้าและฝ่าเท้า',
    items: [
      { k: 'mth_prom', th: 'หัวกระดูก Metatarsal โปน', en: '' },
      { k: 'bony', th: 'กระดูกยื่นผิดปกติขนาดใหญ่', en: '' },
      { k: 'cavus', th: 'เท้าโก่ง อุ้งเท้าสูง', en: 'Pes cavus' },
      { k: 'planus', th: 'เท้าแบน', en: 'Pes planus' },
      { k: 'equinus', th: 'เท้าจิก', en: 'Pes equinus' },
    ],
  },
  {
    g: 'ข้อต่อและกระดูก',
    items: [
      { k: 'charcot', th: 'เท้าผิดรูปจากโรคชาร์โคต์', en: 'Charcot' },
      { k: 'ljm', th: 'การเคลื่อนไหวข้อต่อจำกัด', en: '' },
    ],
  },
  {
    g: 'การเปลี่ยนแปลงโครงสร้างจากประวัติ',
    items: [
      { k: 'trauma', th: 'บาดเจ็บที่เท้าที่หายแล้ว', en: '' },
      { k: 'surgery', th: 'การผ่าตัดเท้าอื่นๆ', en: '' },
    ],
  },
]

export type FieldValue = string | boolean | undefined
export type Fields = Record<string, FieldValue>

export interface SideEval {
  lops: boolean | null
  pad: boolean | null
  deform: boolean
  deformList: string[]
  ulcer: string | null
  amp: string | null
  ckd: string | null
  history: boolean
  autoCat: number | null
  historyOnly: boolean
  missing: string[]
  needTbi: boolean
}

export function evalSide(fields: Fields, k: Side): SideEval {
  const missing: string[] = []

  // monofilament -> LOPS
  const mf = MF_SITES.map((m) => fields[`mf_${k}_${m.k}`] as string | undefined)
  const answered = mf.filter(Boolean).length
  const felt = mf.filter((v) => v === 'y').length
  let mfRes: 'normal' | 'lops' | null = null
  if (answered === 3) mfRes = felt >= 2 ? 'normal' : 'lops'
  else if (felt < 2 && 3 - answered < 2 - felt) mfRes = 'lops'
  else if (felt >= 2) mfRes = 'normal'
  if (answered < 3) missing.push('โมโนฟิลาเมนต์')

  let lops: boolean | null = null
  if (mfRes === 'lops') lops = true
  else if (mfRes === 'normal') lops = false

  // ABI/TBI -> PAD
  const abiBand = fields[`abi_${k}`] as string | undefined
  let pad: boolean | null = null
  if (!abiBand) missing.push('ABI')
  else if (abiBand === 'pad') pad = true
  else if (abiBand === 'normal') pad = false

  const needTbi = abiBand === 'calcified'
  if (needTbi) {
    const tb = fields[`tbi_${k}`] as string | undefined
    if (!tb) missing.push('TBI')
    else pad = tb === 'pad'
  }

  // deformity
  const deformList: string[] = []
  DEFORM.forEach((g) =>
    g.items.forEach((i) => {
      if (fields[`def_${k}_${i.k}`]) deformList.push(i.th)
    }),
  )
  const deform = deformList.length > 0

  // history
  const ulcer = (fields[`ulcer_${k}`] as string) ?? null
  const amp = (fields[`amp_${k}`] as string) ?? null
  const ckd = (fields.ckd as string) ?? null
  if (!ulcer) missing.push('ประวัติแผล')
  if (!amp) missing.push('การตัดรยางค์')
  const history = ulcer === 'yes' || amp === 'yes' || ckd === 'yes'

  // IWGDF category — ประเภท 3 ต้องมี LOPS หรือ PAD ร่วมกับประวัติ
  let cat: number | null = null
  if (lops !== null && pad !== null) {
    if ((lops || pad) && history) cat = 3
    else if (lops && pad) cat = 2
    else if ((lops || pad) && deform) cat = 2
    else if (lops || pad) cat = 1
    else cat = 0
  }

  return {
    lops,
    pad,
    deform,
    deformList,
    ulcer,
    amp,
    ckd,
    history,
    autoCat: cat,
    historyOnly: history && lops === false && pad === false,
    missing,
    needTbi,
  }
}

export interface DerivedSide {
  lops: boolean | null
  pad: boolean | null
  deformity: boolean
  deformities: string[]
  history: boolean
  category: number | null
  label: 'Positive' | 'Negative' | null
}

export function toDerived(r: SideEval): DerivedSide {
  return {
    lops: r.lops,
    pad: r.pad,
    deformity: r.deform,
    deformities: r.deformList,
    history: r.history,
    category: r.autoCat,
    label: r.autoCat === null ? null : r.autoCat >= 1 ? 'Positive' : 'Negative',
  }
}

/** Every non-scoring "is the form complete enough to save" check, mirrors render()'s `need` list. */
export function overallMissing(
  pid: string,
  fields: Fields,
  nurse: string,
  nurse2: string,
  evals: Record<Side, SideEval>,
): string[] {
  const need: string[] = []
  if (!pid.trim()) need.push('รหัสวิจัย')
  if (!fields.ckd) need.push('ไตวายระยะสุดท้าย (CKD stage 5)')
  if (!nurse || !nurse2) need.push('พยาบาลผู้ตรวจ')
  if (nurse && nurse === nurse2) need.push('พยาบาลผู้ตรวจซ้ำกัน')
  SIDES.forEach((s) => evals[s.k].missing.forEach((m) => need.push(s.th + ': ' + m)))
  return need
}
