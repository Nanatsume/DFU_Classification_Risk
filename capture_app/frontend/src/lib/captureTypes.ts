export interface CaseRow {
  research_id: string
  nurse: string
  iwgdf: { L: number | null; R: number | null }
  has_podo: boolean
  has_thermal: boolean
}

export interface CommitRecord {
  schema_version: string
  research_id: string
  captured_at: string
  operator: string
  podoscope: { raw: string | null; preprocessing: { L: string; R: string } | null }
  thermal: { image: string | null; radiometric: string | null }
  status: 'complete' | 'partial'
  app_version: string
}

export interface ManifestRow {
  research_id: string
  captured_at: string
  status: string
  podo_raw: string
  podo_prepro: string
  thermal: string
}

export type Modality = 'podoscope' | 'thermal'
