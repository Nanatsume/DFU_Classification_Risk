/** Unsaved CRF form state, kept in localStorage so a reload cannot lose a foot examination.
 *
 * Why this exists: the form has ~30 fields and the research id is only minted when it is saved,
 * so until the nurse presses บันทึก the answers live nowhere but React state. A mobile browser
 * evicting a backgrounded tab — which it does routinely, e.g. while the nurse answers a message —
 * takes the whole examination with it, and the patient's feet have to be re-examined.
 *
 * Deliberately NOT a fix for the research id: reserving an id on page load (what this app used to
 * do) restores the number after a reload but leaves every field blank, which is the half that
 * actually matters. Drafts solve that; id reservation only littered the database with unused ids.
 *
 * Drafts are per-browser and per-device, never sent anywhere. Only new cases are drafted — editing
 * a saved case already has a server-side copy to fall back on, and mixing the two would let a
 * stale draft overwrite real data.
 */

export type CrfDraft = {
  fields: Record<string, unknown>
  nurse: string
  nurse2: string
  note: string
  savedAt: string
}

const KEY = 'crf_draft_v1'
/** Older than this and the draft is almost certainly a forgotten tab, not work in progress.
 *  Offering to restore a two-week-old examination invites attaching it to the wrong patient. */
const MAX_AGE_DAYS = 7

/** Every accessor is guarded: localStorage throws in private mode and when site data is blocked,
 *  and a form that will not load is far worse than one that cannot remember a draft. */
export function readDraft(now: Date = new Date()): CrfDraft | null {
  let raw: string | null
  try {
    raw = localStorage.getItem(KEY)
  } catch {
    return null
  }
  if (!raw) return null

  let draft: CrfDraft
  try {
    draft = JSON.parse(raw) as CrfDraft
  } catch {
    clearDraft() // corrupt entry would otherwise prompt on every single page load
    return null
  }
  if (!draft || typeof draft !== 'object' || !draft.savedAt) return null

  const ageDays = (now.getTime() - new Date(draft.savedAt).getTime()) / 86_400_000
  if (!Number.isFinite(ageDays) || ageDays > MAX_AGE_DAYS || ageDays < -1) {
    clearDraft()
    return null
  }
  return draft
}

export function writeDraft(draft: Omit<CrfDraft, 'savedAt'>): void {
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...draft, savedAt: new Date().toISOString() }))
  } catch {
    /* quota exceeded or storage blocked — the form still works, it just will not survive a reload */
  }
}

export function clearDraft(): void {
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* nothing to do */
  }
}

/** True when the draft holds nothing a nurse would mind losing — used to avoid prompting to
 *  restore a form that was opened and immediately closed. */
export function isEmptyDraft(draft: Pick<CrfDraft, 'fields' | 'nurse' | 'nurse2' | 'note'>): boolean {
  const filled = Object.values(draft.fields ?? {}).filter(
    (v) => v !== '' && v !== null && v !== undefined && v !== false,
  )
  return filled.length === 0 && !draft.nurse && !draft.nurse2 && !(draft.note ?? '').trim()
}

/** How many answers the draft holds, for the restore prompt — "12 ช่อง" tells the nurse whether
 *  this is the examination they were in the middle of or a stray tab. */
export function draftAnswerCount(draft: Pick<CrfDraft, 'fields'>): number {
  return Object.values(draft.fields ?? {}).filter(
    (v) => v !== '' && v !== null && v !== undefined && v !== false,
  ).length
}
