const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || body.message || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function uploadFile(file: File): Promise<{ task_id: string; pdf_name: string }> {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: fd })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || body.message || `Upload failed: ${res.status}`)
  }
  return res.json()
}

export async function batchUpload(files: File[]): Promise<{
  batch_task_id: string
  file_count: number
  files: { task_id: string; pdf_name: string; prt_name: string }[]
  message: string
}> {
  const fd = new FormData()
  files.forEach(f => fd.append('files', f))
  const res = await fetch(`${BASE}/batch_upload`, { method: 'POST', body: fd })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || body.message || `Batch upload failed: ${res.status}`)
  }
  return res.json()
}

export async function getStatus(taskId: string) {
  return request<{ task_id: string; status: string; progress: number; pdf_name: string }>(
    `/status/${taskId}`,
  )
}

export async function getResult(taskId: string) {
  return request<Record<string, unknown>>(`/result/${taskId}`)
}

export async function submitReview(taskId: string, payload: { review_text: string; action: string; library_key?: string }) {
  return request<{ message: string; task_id: string }>(`/review/${taskId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function rerunTask(taskId: string, reviewText?: string) {
  return request<{ message: string; task_id: string }>(`/rerun/${taskId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(reviewText ? { review_text: reviewText } : {}),
  })
}

export async function updateProcess(taskId: string, processText: string) {
  return request<Record<string, unknown>>(`/process/${taskId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ process_text: processText }),
  })
}

export async function getHistory(params?: { page?: number; page_size?: number; completed_date?: string }) {
  const qs = new URLSearchParams()
  if (params?.page) qs.set('page', String(params.page))
  if (params?.page_size) qs.set('page_size', String(params.page_size))
  if (params?.completed_date) qs.set('completed_date', params.completed_date)
  return request<Record<string, unknown>>(`/history?${qs}`)
}

export async function deleteTask(taskId: string) {
  return request<{ message: string }>(`/history/${taskId}`, { method: 'DELETE' })
}

export async function getExportData(taskId: string) {
  return request<Record<string, unknown>>(`/export/${taskId}`)
}

export async function downloadExport(taskId: string, format: 'pdf' | 'xlsx', rows?: [string, string, string][]) {
  const body: Record<string, unknown> = {}
  if (rows && rows.length) body.rows = rows
  const res = await fetch(`${BASE}/export/${taskId}?format=${format}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`Export failed: ${res.status}`)
  return res.blob()
}

export function connectSSE(taskId: string, handlers: {
  onEvent?: (type: string, data: Record<string, unknown>) => void
  onComplete?: (data: Record<string, unknown>) => void
  onError?: (data: Record<string, unknown>) => void
  onReviewRequired?: (data: Record<string, unknown>) => void
  onLog?: (data: Record<string, unknown>) => void
  onProcessStream?: (data: Record<string, unknown>) => void
  onPreviewUpdated?: (data: Record<string, unknown>) => void
  onYoloProgress?: (data: Record<string, unknown>) => void
  onStepStart?: (data: Record<string, unknown>) => void
  onStepComplete?: (data: Record<string, unknown>) => void
  onImageReady?: (data: Record<string, unknown>) => void
  onAnnotationRequired?: (data: Record<string, unknown>) => void
}): EventSource {
  const es = new EventSource(`${BASE}/events/${taskId}`)

  es.addEventListener('sse_ready', () => {})

  es.addEventListener('step_start', (e) => {
    const d = JSON.parse(e.data)
    handlers.onStepStart?.(d)
    handlers.onEvent?.('step_start', d)
  })

  es.addEventListener('step_complete', (e) => {
    const d = JSON.parse(e.data)
    handlers.onStepComplete?.(d)
    handlers.onEvent?.('step_complete', d)
  })

  es.addEventListener('log', (e) => {
    const d = JSON.parse(e.data)
    handlers.onLog?.(d)
    handlers.onEvent?.('log', d)
  })

  es.addEventListener('process_stream', (e) => {
    const d = JSON.parse(e.data)
    handlers.onProcessStream?.(d)
    handlers.onEvent?.('process_stream', d)
  })

  es.addEventListener('review_required', (e) => {
    const d = JSON.parse(e.data)
    handlers.onReviewRequired?.(d)
    handlers.onEvent?.('review_required', d)
  })

  es.addEventListener('complete', (e) => {
    const d = JSON.parse(e.data)
    handlers.onComplete?.(d)
    handlers.onEvent?.('complete', d)
    es.close()
  })

  es.addEventListener('error_event', (e) => {
    const d = JSON.parse(e.data)
    handlers.onError?.(d)
    handlers.onEvent?.('error', d)
    es.close()
  })

  es.addEventListener('preview_updated', (e) => {
    const d = JSON.parse(e.data)
    handlers.onPreviewUpdated?.(d)
    handlers.onEvent?.('preview_updated', d)
  })

  es.addEventListener('yolo_progress', (e) => {
    const d = JSON.parse(e.data)
    handlers.onYoloProgress?.(d)
    handlers.onEvent?.('yolo_progress', d)
  })

  es.addEventListener('image_ready', (e) => {
    const d = JSON.parse(e.data)
    handlers.onImageReady?.(d)
    handlers.onEvent?.('image_ready', d)
  })

  es.addEventListener('annotation_required', (e) => {
    const d = JSON.parse(e.data)
    handlers.onAnnotationRequired?.(d)
    handlers.onEvent?.('annotation_required', d)
  })

  es.onerror = () => {
    // EventSource will auto-reconnect
  }

  return es
}

export function getAssetUrl(taskId: string, filename: string): string {
  return `${BASE}/result/${taskId}/asset/${filename}`
}

/* ── Library / ZIP Import ── */

export interface LibraryScope {
  library_key: string
  library_name: string
  scope_type: 'public' | 'private'
  record_count?: number
  batch_count?: number
}

export interface LibraryScopesResponse {
  items: LibraryScope[]
  can_browse_db?: boolean
  active_scope?: string
}

export interface ZipImportReport {
  batch_id: string
  zip_name: string
  conflict_mode: string
  library_mode: string
  summary: {
    total_files: number
    prt_count: number
    pdf_count: number
    image_count: number
    xlsx_count: number
    matched_pairs: number
    imported_count: number
    skipped_count: number
    error_count: number
  }
  matched_pairs: {
    prefix: string
    status: string
    existing?: { process_summary?: string; context?: string }
    draft?: { process_summary?: string; context?: string; process_list?: unknown[]; pdf_page_count?: number }
    prt_names?: string[]
    pdf_names?: string[]
    xlsx_names?: string[]
    conflict_mode?: string
  }[]
  unmatched_pdfs: string[]
  unmatched_xlsx: string[]
  unmatched_prts: string[]
  unmatched_images: string[]
  errors: { prefix?: string; pdf_name?: string; prt_name?: string; error?: string; message?: string }[]
  target_library?: { library_key: string; library_name: string }
  created_at: string
}

export async function getLibraryScopes(): Promise<LibraryScopesResponse> {
  return request<LibraryScopesResponse>('/library/scopes')
}

export async function importZipZip(params: {
  file: File
  conflict_mode: 'replace' | 'keep'
  library_mode: string
  library_name?: string
  library_key?: string
}): Promise<ZipImportReport> {
  const fd = new FormData()
  fd.append('zip_file', params.file)
  fd.append('conflict_mode', params.conflict_mode)
  fd.append('library_mode', params.library_mode)
  if (params.library_name) fd.append('library_name', params.library_name)
  if (params.library_key) fd.append('library_key', params.library_key)
  const res = await fetch(`${BASE}/kb/import_zip`, { method: 'POST', body: fd })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || body.message || `Import failed: ${res.status}`)
  }
  return res.json()
}

export function getSampleZipUrl(): string {
  return `${BASE}/kb/sample_zip`
}

/* ── Library Records ── */

export interface LibraryRecord {
  id: number
  prefix: string
  product_type: string
  process_summary: string
  context: string
  tech_requirement: string
  created_at: string
  process_count: number
  content: string
  process_list: string[]
  trades: string[]
  source_type: string
  source_task_id: string
  preview_task_id: string
  preview_total_pages: number
  preview_image_urls: string
  feature_report_text: string
  feature_report_path: string
  feature_report_json: Record<string, unknown>
  real?: number
}

export interface LibraryRecordsResponse {
  items: LibraryRecord[]
  page: number
  page_size: number
  total: number
  total_pages: number
  product_types: string[]
  active_scope: { library_key: string; library_name: string; scope_type: string }
}

export async function getLibraryRecords(params?: {
  page?: number
  page_size?: number
  query?: string
  product_type?: string
  library_key?: string
}): Promise<LibraryRecordsResponse> {
  const qs = new URLSearchParams()
  if (params?.page) qs.set('page', String(params.page))
  if (params?.page_size) qs.set('page_size', String(params.page_size))
  if (params?.query) qs.set('query', params.query)
  if (params?.product_type) qs.set('product_type', params.product_type)
  if (params?.library_key) qs.set('library_key', params.library_key)
  return request<LibraryRecordsResponse>(`/library/records?${qs}`)
}

export async function getLibraryRecord(id: number, libraryKey?: string): Promise<LibraryRecord> {
  const qs = libraryKey ? `?library_key=${encodeURIComponent(libraryKey)}` : ''
  return request<LibraryRecord>(`/library/records/${id}${qs}`)
}

export async function updateLibraryRecord(id: number, payload: Partial<LibraryRecord> & { library_key?: string }): Promise<LibraryRecord> {
  return request<LibraryRecord>(`/library/records/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function deleteLibraryRecord(id: number, libraryKey?: string): Promise<{ message: string }> {
  const qs = libraryKey ? `?library_key=${encodeURIComponent(libraryKey)}` : ''
  return request<{ message: string }>(`/library/records/${id}${qs}`, { method: 'DELETE' })
}

export async function deleteLibraryScope(libraryKey: string): Promise<{ message: string }> {
  return request<{ message: string }>(`/library/scopes/${encodeURIComponent(libraryKey)}`, { method: 'DELETE' })
}

export interface CommitDraft {
  prefix: string
  content: string
  process_summary: string
  feature_report_text: string
  preview_image_urls: string[]
  source_type: string
  source_task_id: string
  process_list: { code: string; trade: string; content: string }[]
  tech_requirement: string
  product_type: string
}

export async function commitToLibrary(params: {
  draft: CommitDraft
  action: 'replace' | 'keep'
  library_key: string
}): Promise<{ message: string; record_id?: number }> {
  return request('/library/commit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
}

export async function getLibraryStatus(libraryKey?: string): Promise<{
  ready: boolean
  record_count: number
  can_browse: boolean
  imported_batches: string[]
  scopes: LibraryScope[]
  active_scope: { library_key: string; library_name: string; scope_type: string }
}> {
  const qs = libraryKey ? `?library_key=${encodeURIComponent(libraryKey)}` : ''
  return request(`/library/status${qs}`)
}

/* ── Config ── */

export interface SystemConfig {
  vision_api_key: string
  vision_api_base: string
  vision_model_id: string
  llm_api_key: string
  llm_base_url: string
  llm_model: string
  vision_mode: string
  poppler_path: string
  creo_exe: string
  creo_base_dir: string
  creo_out_dir: string
}

export async function getConfig(): Promise<SystemConfig> {
  return request<SystemConfig>('/config')
}

export async function updateConfig(payload: Partial<SystemConfig>): Promise<{ message: string }> {
  return request<{ message: string }>('/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

/* ── 2D Drawing Upload ── */

export async function uploadDrawing(file: File): Promise<{ task_id: string; pdf_name: string; message: string }> {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(`${BASE}/upload_drawing`, { method: 'POST', body: fd })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error?.message || body.error || body.message || `Upload failed: ${res.status}`)
  }
  return res.json()
}

/* ── Annotations ── */

export interface AnnotationShapeBE {
  label: string
  points: [[number, number], [number, number]]
  shape_type?: string
  [key: string]: unknown
}

export interface AnnotationPageBE {
  shapes: AnnotationShapeBE[]
  imageWidth?: number
  imageHeight?: number
  imagePath?: string
}

export async function getAnnotations(taskId: string): Promise<Record<string, AnnotationPageBE>> {
  const res = await request<{ task_id: string; pages: Record<string, AnnotationPageBE> }>(`/annotations/${taskId}`)
  return res.pages || {}
}

export async function saveAnnotation(taskId: string, payload: {
  page: number
  shapes: AnnotationShapeBE[]
  imageWidth: number
  imageHeight: number
  imagePath: string
}): Promise<{ ok: boolean; json_path?: string; txt_path?: string }> {
  const res = await fetch(`${BASE}/annotations/${taskId}/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    console.error(`[saveAnnotation] ${res.status}:`, body, 'payload:', JSON.stringify(payload).slice(0, 500))
    throw new Error(body || `Save failed: ${res.status}`)
  }
  return res.json()
}

export async function finalizeAnnotation(taskId: string): Promise<{ ok: boolean; task_id: string; mode: string }> {
  return request(`/annotations/${taskId}/finalize`, { method: 'POST' })
}

export async function exportAnnotations(taskId: string): Promise<Blob> {
  const res = await fetch(`${BASE}/annotations/${taskId}/export`)
  if (!res.ok) throw new Error(`Export failed: ${res.status}`)
  return res.blob()
}

