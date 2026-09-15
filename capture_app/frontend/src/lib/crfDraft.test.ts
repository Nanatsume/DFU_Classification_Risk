import { beforeEach, describe, expect, it, vi } from 'vitest'
import { clearDraft, draftAnswerCount, isEmptyDraft, readDraft, writeDraft } from './crfDraft'

const KEY = 'crf_draft_v1'

/** jsdom is not configured for this suite, so stand in a minimal localStorage. It also lets the
 *  tests simulate the private-mode / blocked-storage case, which is the one that must never take
 *  the form down with it. */
function installStorage(impl?: Partial<Storage>) {
  const store = new Map<string, string>()
  const base: Storage = {
    getItem: (k) => store.get(k) ?? null,
    setItem: (k, v) => void store.set(k, v),
    removeItem: (k) => void store.delete(k),
    clear: () => store.clear(),
    key: (i) => [...store.keys()][i] ?? null,
    get length() {
      return store.size
    },
  }
  vi.stubGlobal('localStorage', { ...base, ...impl })
  return store
}

beforeEach(() => {
  installStorage()
})

describe('round trip', () => {
  it('gives back what was written', () => {
    writeDraft({ fields: { ckd: 'no', mf_L_hallux: 'y' }, nurse: 'A', nurse2: 'B', note: 'hi' })
    const draft = readDraft()
    expect(draft?.fields).toEqual({ ckd: 'no', mf_L_hallux: 'y' })
    expect(draft?.nurse).toBe('A')
    expect(draft?.note).toBe('hi')
  })

  it('returns null when nothing has been written', () => {
    expect(readDraft()).toBeNull()
  })

  it('clearDraft removes it', () => {
    writeDraft({ fields: { ckd: 'no' }, nurse: '', nurse2: '', note: '' })
    clearDraft()
    expect(readDraft()).toBeNull()
  })
})

describe('age', () => {
  it('keeps a draft from earlier today', () => {
    writeDraft({ fields: { ckd: 'no' }, nurse: '', nurse2: '', note: '' })
    const inThreeHours = new Date(Date.now() + 3 * 3600_000)
    expect(readDraft(inThreeHours)).not.toBeNull()
  })

  it('discards one older than a week', () => {
    writeDraft({ fields: { ckd: 'no' }, nurse: '', nurse2: '', note: '' })
    const inTenDays = new Date(Date.now() + 10 * 86_400_000)
    expect(readDraft(inTenDays)).toBeNull()
  })

  it('offering a stale draft could attach an old examination to the wrong patient', () => {
    writeDraft({ fields: { ckd: 'no' }, nurse: '', nurse2: '', note: '' })
    readDraft(new Date(Date.now() + 10 * 86_400_000))
    expect(localStorage.getItem(KEY)).toBeNull() // and it is purged, not merely hidden
  })
})

describe('corrupt or hostile storage', () => {
  it('survives a non-JSON entry and clears it', () => {
    localStorage.setItem(KEY, 'not json at all')
    expect(readDraft()).toBeNull()
    expect(localStorage.getItem(KEY)).toBeNull()
  })

  it('survives an entry that is JSON but not a draft', () => {
    localStorage.setItem(KEY, '"just a string"')
    expect(readDraft()).toBeNull()
  })

  it('returns null rather than throwing when storage is blocked', () => {
    installStorage({
      getItem: () => {
        throw new Error('SecurityError: storage is disabled')
      },
    })
    expect(() => readDraft()).not.toThrow()
    expect(readDraft()).toBeNull()
  })

  it('writing never throws when the quota is exhausted', () => {
    installStorage({
      setItem: () => {
        throw new Error('QuotaExceededError')
      },
    })
    expect(() => writeDraft({ fields: { ckd: 'no' }, nurse: '', nurse2: '', note: '' })).not.toThrow()
  })
})

describe('isEmptyDraft', () => {
  const blank = { fields: {}, nurse: '', nurse2: '', note: '' }

  it('a freshly opened form counts as empty, so no restore prompt appears', () => {
    expect(isEmptyDraft(blank)).toBe(true)
  })

  it('unchecked deformity checkboxes do not count as answers', () => {
    expect(isEmptyDraft({ ...blank, fields: { def_L_claw: false, def_R_charcot: false } })).toBe(true)
  })

  it('one real answer is enough to be worth restoring', () => {
    expect(isEmptyDraft({ ...blank, fields: { ckd: 'no' } })).toBe(false)
  })

  it('a nurse chosen but nothing else still counts', () => {
    expect(isEmptyDraft({ ...blank, nurse: 'ธนกฤต อินทรสุวรรณ' })).toBe(false)
  })

  it('whitespace in the note does not count', () => {
    expect(isEmptyDraft({ ...blank, note: '   ' })).toBe(true)
  })
})

describe('draftAnswerCount', () => {
  it('counts only answered fields, so the prompt tells the nurse what is at stake', () => {
    expect(
      draftAnswerCount({
        fields: { ckd: 'no', abi_L: 'normal', def_L_claw: false, note: '' },
      }),
    ).toBe(2)
  })
})
