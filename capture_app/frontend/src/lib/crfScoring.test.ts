import { describe, expect, it } from 'vitest'
import { evalSide, overallMissing, toDerived, type Fields } from './crfScoring'

// Baseline: every field answered, LOPS-negative, PAD-negative, no deformity, no history.
// category should be 0 (Negative). Individual tests below mutate one axis at a time from here.
const BASE: Fields = {
  ckd: 'no',
  mf_L_hallux: 'y', mf_L_mth1: 'y', mf_L_mth5: 'y',
  abi_L: 'normal',
  ulcer_L: 'no', amp_L: 'no',
}

describe('evalSide — LOPS (monofilament)', () => {
  it('felt at all 3 sites -> lops false', () => {
    const r = evalSide({ ...BASE }, 'L')
    expect(r.lops).toBe(false)
    expect(r.missing).not.toContain('โมโนฟิลาเมนต์')
  })

  it('not felt at all 3 sites -> lops true', () => {
    const r = evalSide({ ...BASE, mf_L_hallux: 'n', mf_L_mth1: 'n', mf_L_mth5: 'n' }, 'L')
    expect(r.lops).toBe(true)
  })

  it('felt 2/3, not felt 1/3 -> lops false (majority felt)', () => {
    const r = evalSide({ ...BASE, mf_L_mth5: 'n' }, 'L')
    expect(r.lops).toBe(false)
  })

  it('felt 1/3, not felt 2/3 -> lops true (majority not felt)', () => {
    const r = evalSide({ ...BASE, mf_L_mth1: 'n', mf_L_mth5: 'n' }, 'L')
    expect(r.lops).toBe(true)
  })

  it('only 2 of 3 answered, both not felt -> already decided lops (3rd site cannot save it)', () => {
    const fields: Fields = { ...BASE, mf_L_hallux: 'n', mf_L_mth1: 'n', mf_L_mth5: undefined }
    const r = evalSide(fields, 'L')
    expect(r.lops).toBe(true)
    expect(r.missing).toContain('โมโนฟิลาเมนต์') // still flagged incomplete even though decided
  })

  it('only 1 of 3 answered, felt -> undecided (remaining 2 could still tip either way)', () => {
    const fields: Fields = { ...BASE, mf_L_mth1: undefined, mf_L_mth5: undefined }
    const r = evalSide(fields, 'L')
    expect(r.lops).toBeNull()
    expect(r.missing).toContain('โมโนฟิลาเมนต์')
  })

  it('none answered -> lops null, missing flagged', () => {
    const fields: Fields = { ...BASE, mf_L_hallux: undefined, mf_L_mth1: undefined, mf_L_mth5: undefined }
    const r = evalSide(fields, 'L')
    expect(r.lops).toBeNull()
    expect(r.missing).toContain('โมโนฟิลาเมนต์')
  })
})

describe('evalSide — PAD (ABI/TBI)', () => {
  it('abi normal -> pad false, no missing ABI', () => {
    const r = evalSide({ ...BASE, abi_L: 'normal' }, 'L')
    expect(r.pad).toBe(false)
    expect(r.missing).not.toContain('ABI')
    expect(r.needTbi).toBe(false)
  })

  it('abi pad -> pad true', () => {
    const r = evalSide({ ...BASE, abi_L: 'pad' }, 'L')
    expect(r.pad).toBe(true)
  })

  it('abi missing entirely -> pad null, missing ABI', () => {
    const r = evalSide({ ...BASE, abi_L: undefined }, 'L')
    expect(r.pad).toBeNull()
    expect(r.missing).toContain('ABI')
  })

  it('abi calcified requires TBI — missing TBI leaves pad undecided', () => {
    const r = evalSide({ ...BASE, abi_L: 'calcified' }, 'L')
    expect(r.needTbi).toBe(true)
    expect(r.pad).toBeNull()
    expect(r.missing).toContain('TBI')
  })

  it('abi calcified + tbi normal -> pad false', () => {
    const r = evalSide({ ...BASE, abi_L: 'calcified', tbi_L: 'normal' }, 'L')
    expect(r.pad).toBe(false)
    expect(r.missing).not.toContain('TBI')
  })

  it('abi calcified + tbi pad -> pad true', () => {
    const r = evalSide({ ...BASE, abi_L: 'calcified', tbi_L: 'pad' }, 'L')
    expect(r.pad).toBe(true)
  })
})

describe('evalSide — deformity', () => {
  it('nothing checked -> deform false, empty list', () => {
    const r = evalSide({ ...BASE }, 'L')
    expect(r.deform).toBe(false)
    expect(r.deformList).toEqual([])
  })

  it('one item checked -> deform true, named in the list', () => {
    const r = evalSide({ ...BASE, def_L_hammer: true }, 'L')
    expect(r.deform).toBe(true)
    expect(r.deformList).toEqual(['นิ้วเท้าโก่ง'])
  })

  it('multiple items across groups all collected', () => {
    const r = evalSide({ ...BASE, def_L_hammer: true, def_L_cavus: true, def_L_charcot: true }, 'L')
    expect(r.deformList).toHaveLength(3)
  })
})

describe('evalSide — history', () => {
  it('no ulcer, no amp, no ckd -> history false', () => {
    const r = evalSide({ ...BASE }, 'L')
    expect(r.history).toBe(false)
  })

  it('ulcer yes -> history true', () => {
    const r = evalSide({ ...BASE, ulcer_L: 'yes' }, 'L')
    expect(r.history).toBe(true)
  })

  it('amputation yes -> history true', () => {
    const r = evalSide({ ...BASE, amp_L: 'yes' }, 'L')
    expect(r.history).toBe(true)
  })

  it('ckd yes (global field) -> history true even with no ulcer/amp', () => {
    const r = evalSide({ ...BASE, ckd: 'yes' }, 'L')
    expect(r.history).toBe(true)
  })

  it('ulcer/amp unanswered -> missing flags for both, history still computed as false', () => {
    const r = evalSide({ ...BASE, ulcer_L: undefined, amp_L: undefined }, 'L')
    expect(r.missing).toContain('ประวัติแผล')
    expect(r.missing).toContain('การตัดรยางค์')
    expect(r.history).toBe(false)
  })
})

describe('evalSide — IWGDF category boundaries', () => {
  it('no LOPS, no PAD, no deform, no history -> category 0 (Negative)', () => {
    const r = evalSide({ ...BASE }, 'L')
    expect(r.autoCat).toBe(0)
  })

  it('LOPS only, no deform, no history -> category 1', () => {
    const fields: Fields = { ...BASE, mf_L_hallux: 'n', mf_L_mth1: 'n', mf_L_mth5: 'n' }
    const r = evalSide(fields, 'L')
    expect(r.lops).toBe(true)
    expect(r.pad).toBe(false)
    expect(r.autoCat).toBe(1)
  })

  it('PAD only, no deform, no history -> category 1', () => {
    const r = evalSide({ ...BASE, abi_L: 'pad' }, 'L')
    expect(r.autoCat).toBe(1)
  })

  it('LOPS and PAD together -> category 2, regardless of deform/history', () => {
    const fields: Fields = { ...BASE, mf_L_hallux: 'n', mf_L_mth1: 'n', mf_L_mth5: 'n', abi_L: 'pad' }
    const r = evalSide(fields, 'L')
    expect(r.autoCat).toBe(2)
  })

  it('LOPS xor PAD, plus deformity -> category 2', () => {
    const r = evalSide({ ...BASE, abi_L: 'pad', def_L_hammer: true }, 'L')
    expect(r.lops).toBe(false)
    expect(r.pad).toBe(true)
    expect(r.deform).toBe(true)
    expect(r.autoCat).toBe(2)
  })

  it('LOPS or PAD, plus history -> category 3 (history wins over the deform-only cat-2 rule)', () => {
    const r = evalSide({ ...BASE, abi_L: 'pad', ulcer_L: 'yes' }, 'L')
    expect(r.autoCat).toBe(3)
  })

  it('history alone, without LOPS or PAD -> category 0, flagged historyOnly (not enough for cat 3)', () => {
    const r = evalSide({ ...BASE, ulcer_L: 'yes' }, 'L')
    expect(r.lops).toBe(false)
    expect(r.pad).toBe(false)
    expect(r.autoCat).toBe(0)
    expect(r.historyOnly).toBe(true)
  })

  it('category stays null while LOPS or PAD is undecided', () => {
    const r = evalSide({ ...BASE, abi_L: undefined }, 'L')
    expect(r.pad).toBeNull()
    expect(r.autoCat).toBeNull()
  })
})

describe('the known regression case (P0003 payload used throughout development)', () => {
  it('L: all monofilament felt + ABI normal + no history -> category 0 / Negative', () => {
    const fields: Fields = {
      ckd: 'no',
      mf_L_hallux: 'y', mf_L_mth1: 'y', mf_L_mth5: 'y',
      abi_L: 'normal', ulcer_L: 'no', amp_L: 'no',
    }
    const d = toDerived(evalSide(fields, 'L'))
    expect(d.category).toBe(0)
    expect(d.label).toBe('Negative')
  })

  it('R: all monofilament not felt + ABI pad -> category 2 / Positive', () => {
    const fields: Fields = {
      ckd: 'no',
      mf_R_hallux: 'n', mf_R_mth1: 'n', mf_R_mth5: 'n',
      abi_R: 'pad', ulcer_R: 'no', amp_R: 'no',
    }
    const d = toDerived(evalSide(fields, 'R'))
    expect(d.category).toBe(2)
    expect(d.label).toBe('Positive')
  })
})

describe('toDerived', () => {
  it('maps a null category to a null label, not "Negative"', () => {
    const d = toDerived(evalSide({ ...BASE, abi_L: undefined }, 'L'))
    expect(d.category).toBeNull()
    expect(d.label).toBeNull()
  })

  it('category 0 -> Negative, category >= 1 -> Positive', () => {
    expect(toDerived(evalSide({ ...BASE }, 'L')).label).toBe('Negative')
    expect(toDerived(evalSide({ ...BASE, abi_L: 'pad' }, 'L')).label).toBe('Positive')
  })
})

describe('overallMissing', () => {
  const fullFields: Fields = {
    ckd: 'no',
    mf_L_hallux: 'y', mf_L_mth1: 'y', mf_L_mth5: 'y', abi_L: 'normal', ulcer_L: 'no', amp_L: 'no',
    mf_R_hallux: 'y', mf_R_mth1: 'y', mf_R_mth5: 'y', abi_R: 'normal', ulcer_R: 'no', amp_R: 'no',
  }
  const evalBoth = (fields: Fields) => ({ L: evalSide(fields, 'L' as const), R: evalSide(fields, 'R' as const) })

  it('a fully completed form with distinct nurses has no missing items', () => {
    const missing = overallMissing('P0001', fullFields, 'Nurse A', 'Nurse B', evalBoth(fullFields))
    expect(missing).toEqual([])
  })

  it('flags a missing research id', () => {
    const missing = overallMissing('', fullFields, 'Nurse A', 'Nurse B', evalBoth(fullFields))
    expect(missing).toContain('รหัสวิจัย')
  })

  it('flags missing CKD answer', () => {
    const fields = { ...fullFields, ckd: undefined }
    const missing = overallMissing('P0001', fields, 'Nurse A', 'Nurse B', evalBoth(fields))
    expect(missing).toContain('ไตวายระยะสุดท้าย (CKD stage 5)')
  })

  it('flags missing nurse(s)', () => {
    const missing = overallMissing('P0001', fullFields, '', '', evalBoth(fullFields))
    expect(missing).toContain('พยาบาลผู้ตรวจ')
  })

  it('flags duplicate nurse selection', () => {
    const missing = overallMissing('P0001', fullFields, 'Same Person', 'Same Person', evalBoth(fullFields))
    expect(missing).toContain('พยาบาลผู้ตรวจซ้ำกัน')
  })

  it('propagates per-side missing items with a Thai side label prefix', () => {
    const fields = { ...fullFields, abi_L: undefined }
    const missing = overallMissing('P0001', fields, 'A', 'B', evalBoth(fields))
    expect(missing).toContain('เท้าซ้าย: ABI')
  })
})
