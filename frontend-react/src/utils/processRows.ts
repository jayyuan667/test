export interface NormalizedProcessRow {
  code: string
  trade: string
  content: string
}

export function normalizeProcessRows(value: unknown): NormalizedProcessRow[] {
  const rows = parseArray(value)
  return rows
    .map((row, index) => normalizeProcessRow(row, index))
    .filter((row): row is NormalizedProcessRow => !!row && Boolean(row.code || row.trade || row.content))
}

export function displayStepCode(index: number): string {
  return String((index + 1) * 50).padStart(4, '0')
}

export function normalizeStringArray(value: unknown): string[] {
  return parseArray(value)
    .map(item => String(item || '').trim())
    .filter(Boolean)
}

export function normalizeAssetUrls(
  value: unknown,
  taskId: string | undefined,
  getAssetUrl: (taskId: string, filename: string) => string,
): string[] {
  const urls = normalizeStringArray(value)
  if (!taskId) return urls.filter(url => url.startsWith('/api') || /^https?:\/\//i.test(url))
  return urls.map(url => {
    if (url.startsWith('/api') || /^https?:\/\//i.test(url)) return url
    return getAssetUrl(taskId, url)
  })
}

function parseArray(value: unknown): unknown[] {
  if (Array.isArray(value)) return value
  if (typeof value === 'string' && value.trim()) {
    try {
      const parsed = JSON.parse(value)
      if (Array.isArray(parsed)) return parsed
    } catch {
      return value.split(/\r?\n/).filter(Boolean)
    }
  }
  return []
}

function normalizeProcessRow(row: unknown, index: number): NormalizedProcessRow | null {
  if (Array.isArray(row)) {
    const code = String(row[0] || '').trim() || fallbackCode(index)
    if (row.length === 2) {
      const rawContent = String(row[1] || '').trim()
      const tradeMatch = rawContent.match(/^([^@\s]{1,12})@(.+)$/s)
      if (tradeMatch) {
        return {
          code,
          trade: tradeMatch[1].trim(),
          content: tradeMatch[2].trim(),
        }
      }
      return { code, trade: '', content: rawContent }
    }
    return {
      code,
      trade: row.length >= 3 ? String(row[1] || '').trim() : '',
      content: String(row[row.length >= 3 ? 2 : 1] || '').trim(),
    }
  }

  if (row && typeof row === 'object') {
    const obj = row as Record<string, unknown>
    return {
      code: String(obj.code || obj.step_code || '').trim() || fallbackCode(index),
      trade: String(obj.trade || obj.work_type || '').trim(),
      content: String(obj.content || obj.name || obj.description || '').trim(),
    }
  }

  const text = String(row || '').trim()
  if (!text) return null
  const parts = text.split('@')
  if (parts.length >= 3) {
    return { code: parts[0].trim(), trade: parts[1].trim(), content: parts.slice(2).join('@').trim() }
  }
  if (parts.length === 2) {
    return { code: parts[0].trim(), trade: '', content: parts[1].trim() }
  }
  const match = text.match(/^(\d{4})\s*[:：@\-\|,，、]?\s*(.+)$/)
  if (match) return { code: match[1], trade: '', content: match[2].trim() }
  return { code: fallbackCode(index), trade: '', content: text }
}

function fallbackCode(index: number): string {
  return String((index + 1) * 50).padStart(4, '0')
}
