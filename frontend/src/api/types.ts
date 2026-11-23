/** Shapes of the backend's JSON (backend/app/api/). Lengths are millimetres. */

export type Language = 'en' | 'es'
export type ParamValue = string | number | boolean
export type Params = Record<string, ParamValue>
export type Kind = 'glass_bead' | 'charm'

export interface FamilySummary {
  code: string
  kind: Kind
  name: string
  sku_prefix: string
}

export interface ParameterInfo {
  type: 'number' | 'integer' | 'boolean' | 'string'
  label: string
  unit?: string
  minimum?: number
  maximum?: number
  step?: number
  enum?: (string | number)[]
  /** Display label of each text choice ({ gold_plate: 'Gold plate' }). */
  choices?: Record<string, string>
  default?: ParamValue
  rules: string[]
  description?: string
  pattern?: string
}

export interface Swatch {
  id: string
  name: string
  hex: string
  transmission: number
  metallic: number
  roughness: number
}

export interface FamilyInfo {
  code: string
  kind: Kind
  name: string
  name_suffix: string
  material: string
  density_g_cm3: number
  parameters: Record<string, ParameterInfo>
  defaults: Params
  option_parameter: 'color' | 'finish'
  collections: string[]
  swatches: Swatch[]
}

export interface NameCheck {
  name: string
  follows: boolean
  violations: Violation[]
  suggestion: string | null
  similar: { sku: string; name: string; status: string }[]
  sap_available: boolean
}

export interface Violation {
  rule: string
  parameters: string[]
  message: string
  /** The same message in Spanish (the panel's check only). */
  message_es?: string
  nearest_valid?: { parameter: string; value: ParamValue }[]
}

export interface Validation {
  valid: boolean
  family: string
  params: Params
  violations: Violation[]
  notes: string[]
  rule_edition: string
}

export interface Measurements {
  volume_mm3: number
  mass_g: number
  material: string
  density_g_cm3: number
  bbox_mm: [number, number, number]
}

export interface Preview {
  preview_id: string
  url: string
  family: string
  params: Params
  measurements: Measurements
}

export interface PreviewResponse {
  validation: Validation
  preview: Preview | null
}

export type ActionKind = 'reserve_sku' | 'generate_design' | 'render'
export type ActionStatus = 'pending' | 'executing' | 'confirmed' | 'failed' | 'cancelled' | 'expired'

export interface ActionResult {
  ok: boolean
  message?: string
  error_kind?: string
  sku?: string
  rev?: string
  revision?: string
  name?: string
  sap_material?: string
  family?: string
  collection?: string | null
  status?: string
  files?: string[]
  measurements?: Measurements
  finish?: string
  job_id?: number
  violations?: { rule: string; message: string }[]
}

export interface PendingAction {
  id: string
  conversation_id: string
  kind: ActionKind
  status: ActionStatus
  payload: Record<string, unknown>
  result: ActionResult | null
  created_at: string
  expires_at: string
  decided_at: string | null
}

/** `POST /api/actions`: a card the designer opens from the panel (decision 0014). */
export interface OpenCardRequest {
  kind: ActionKind
  conversation_id: string | null
  language: Language
  family?: string
  name?: string
  collection?: string
  sku?: string
  rev?: string
  params?: Params
  finish?: string
}

export interface RenderJob {
  id: number
  status: 'queued' | 'running' | 'done' | 'failed'
  sku: string
  rev: string
  finish: string
  samples: number
  resolution: number
  created_at: string | null
  started_at: string | null
  finished_at: string | null
  duration_s: number | null
  image: string | null
  error: string | null
}

export interface DesignRecord {
  sku: string
  rev: string
  family: string
  name: string
  sap_material: string | null
  params: Params
  measurements: Measurements
  drawing_scale: string
  generated_on: string
  urls: Record<'step' | 'stl' | 'glb' | 'drawing', string>
  /** The revision a new generation would get (after the highest one with files). */
  next_rev: string
}

export interface CatalogItem {
  sku: string
  sap_material: string
  name: string
  type: 'GLASS_BEAD' | 'CHARM'
  family: string
  collection: string
  status: 'IN_DESIGN' | 'ACTIVE' | 'DISCONTINUED'
  color: string
  finish: string
  main_dimension_mm: number | null
  /** `design`: SAP has no size yet (a new reservation); taken from the generated files. */
  main_dimension_source: 'sap' | 'design' | null
  current_revision: string
  created_on: string | null
  created_by: string
  generated_revisions: string[]
  /** The revision a new generation gets: after the newest with files (GEN-02, no gaps). */
  next_revision: string
}

export interface GalleryRender {
  file: string
  url: string
  sku: string
  rev: string
  /** A design made for the gallery, not a product of the SAP catalog. */
  showcase?: boolean
  name: string
  collection: string
  family: string
  finish: string
  finish_name: Record<Language, string>
  mass_g: number
  render_s: number
}

export interface Health {
  status: string
  version: string
  llm_provider: string
  /** Why `LLM_PROVIDER=auto` fell to demo mode, else null (decision 0022). */
  llm_note?: string | null
}

/** One event of `POST /api/chat` (server-sent events). */
export type ChatEvent =
  | { type: 'conversation'; data: { id: string } }
  | { type: 'thinking'; data: { content: string } }
  | { type: 'tool_call'; data: { id: string; name: string; arguments: Record<string, unknown> } }
  | {
      type: 'tool_result'
      data: { id: string; name: string; ok: boolean; result: Record<string, unknown> }
    }
  | { type: 'parameter_proposal'; data: { family: string; validation: Validation } }
  | { type: 'preview'; data: Preview }
  | { type: 'pending_action'; data: { action: PendingAction } }
  | { type: 'message'; data: { role: 'assistant'; content: string } }
  | { type: 'error'; data: { message: string } }
  | { type: 'done'; data: { conversation_id?: string; run_id?: number; status: string } }
