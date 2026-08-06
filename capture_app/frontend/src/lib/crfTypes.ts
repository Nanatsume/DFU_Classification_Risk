// Shared shape of a saved CRF record — matches capture_app/crf_store.py's CrfRecord model
// and the JSON written to data/crf/{pid}.json. Used by CrfList, CrfDetail, and CrfForm.

export interface DerivedSide {
  lops: boolean | null
  pad: boolean | null
  deformity: boolean
  deformities: string[]
  history: boolean | null
  category: number | null
  label: 'Positive' | 'Negative' | null
}

export interface CrfData {
  form: string
  savedAt: string
  fields: Record<string, string | boolean>
  derived: {
    L: DerivedSide
    R: DerivedSide
  }
}

export interface CrfRecord {
  pid: string
  nurse: string
  nurse2: string
  savedAt: string
  data: CrfData
  schema_version?: string
}

export interface ManifestRow {
  research_id: string
  captured_at: string
  status: string
  podo_raw: string
  podo_prepro: string
  thermal: string
}

export interface RoiSummaryRow {
  rid: string
  savedAt: string
  summary: Record<string, unknown>
}
