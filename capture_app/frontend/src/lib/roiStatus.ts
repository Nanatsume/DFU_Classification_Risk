// Shared "does this foot need ROI marking" logic — used by roi.html, crf-detail.html, crf-list.html,
// and mirrored in via_static/_via_dfu.js (that one's plain JS, can't import this, kept in sync by hand).
//
// Rule: a Negative foot has no LOPS/PAD by definition (see crfScoring.ts's category rule), so
// there's nothing to mark by the tool's own logic — skip it. An undetermined foot (label is null,
// e.g. the CRF form was saved incomplete) is treated as needing marking: safer to over-collect than
// to silently lose a foot that turns out Positive once the form is completed later.

export type RoiSideStatus = 'not_needed' | 'pending' | 'done'

export function roiSideStatus(
  label: 'Positive' | 'Negative' | null | undefined,
  regionCount: number,
): RoiSideStatus {
  if (label === 'Negative') return 'not_needed'
  return regionCount > 0 ? 'done' : 'pending'
}

export function categoryToLabel(category: number | null | undefined): 'Positive' | 'Negative' | null {
  if (category === null || category === undefined) return null
  return category >= 1 ? 'Positive' : 'Negative'
}

export const ROI_STATUS_TEXT: Record<RoiSideStatus, string> = {
  not_needed: 'ไม่ต้องทำ',
  pending: 'ยังไม่ทำ',
  done: 'ทำแล้ว',
}
