export interface FeatureField {
  label: string
  value: string
}

const HIDDEN_LABELS = new Set([
  '报告名称', '页数', '图号', '图号保留',
])

function isHidden(label: string): boolean {
  return HIDDEN_LABELS.has(label) || /^第\d+页摘要$/.test(label)
}

/**
 * Parse feature report text (【字段】值 format) into structured fields.
 * Matches H5's parseReviewFields() logic.
 */
export function parseReviewFields(text: string): FeatureField[] {
  const fields: FeatureField[] = []
  let current: FeatureField | null = null

  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim()
      .replace(/^#+\s*/, '')
      .replace(/#{2,}/g, '')
      .replace(/^[-=*_]{3,}$/, '')
      .trim()
    if (!line) continue

    const match = line.match(/^【([^】]+)】\s*(.*)$/)
    if (match) {
      const label = match[1].trim()
      if (isHidden(label)) { current = null; continue }
      current = { label, value: match[2].trim().replace(/^[：:]\s*/, '') }
      fields.push(current)
    } else if (current) {
      current.value = current.value ? current.value + '\n' + line : line
    }
  }

  if (fields.length === 0) {
    const raw = text.trim()
    if (raw) fields.push({ label: '审阅内容', value: raw })
  }

  return fields
}

/**
 * Serialize fields back to 【字段】值 format.
 */
export function serializeReviewFields(fields: FeatureField[]): string {
  return fields
    .map(f => `【${f.label || '未命名'}】${f.value || ''}`)
    .join('\n')
}

/**
 * Filter feature_report_text to keep only the 4 info fields for export display.
 * Matches H5's filterInfoFields().
 */
export function filterInfoFields(text: string): string {
  const keepFields = ['零件名称', '形态', '类型', '技术要求']
  const sections = text.split(/(?=【)/)
  const kept: string[] = []
  for (const s of sections) {
    const trimmed = s.trim()
    if (!trimmed) continue
    for (const field of keepFields) {
      if (trimmed.startsWith(`【${field}】`)) {
        kept.push(trimmed)
        break
      }
    }
  }
  return kept.join('\n')
}
