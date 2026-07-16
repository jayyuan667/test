import { expect, test } from '@playwright/test'
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises'
import { assertEvidenceClean, sanitizeEvent, sanitizeEvidence } from '../src/features/drawing-workflow/evidence'

const fixture = process.env.FORGE_E2E_FIXTURE || '/Users/caojiayuan/Documents/测试包/drawing/test.png'
const evidenceDir = process.env.FORGE_E2E_EVIDENCE_DIR || '/tmp/forge-v1-evidence'
const apiBase = process.env.FORGE_E2E_API_BASE || 'http://localhost:5390'
const username = process.env.FORGE_E2E_USERNAME || 'test'
const password = process.env.FORGE_E2E_PASSWORD || 'test123'

test('real v1 drawing workflow resumes and exports structured data', async ({ page }) => {
  test.setTimeout(20 * 60 * 1000)
  await mkdir(evidenceDir, { recursive: true })
  const diagnostics: string[] = []
  page.on('console', (message) => diagnostics.push(`console:${message.type()}:${message.text()}`))
  page.on('requestfailed', (request) => diagnostics.push(`requestfailed:${request.method()}:${new URL(request.url()).pathname}:${request.failure()?.errorText}`))

  await page.goto('/')
  await page.getByText('进入系统').first().click()
  await page.locator('#username').fill(username)
  await page.locator('#pwd').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByText('控制台').first()).toBeVisible({ timeout: 20_000 })
  await page.getByText('工艺生成').first().click()
  await expect(page.getByTestId('v1-workflow')).toBeVisible()
  const steps = page.getByRole('navigation', { name: '工艺生成步骤' })
  await expect(steps).toBeVisible()
  await expect(steps.getByRole('button', { name: /上传图纸/ })).toHaveAttribute('aria-current', 'step')

  await page.getByTestId('drawing-upload').setInputFiles(fixture)
  await page.getByTestId('start-analysis').click()
  await expect(steps.getByRole('button', { name: /特征标注/ })).toHaveAttribute('aria-current', 'step', { timeout: 8 * 60 * 1000 })
  await expect(page.getByRole('img', { name: /test\.png/ })).toBeVisible()
  const taskId = await page.evaluate(() => localStorage.getItem('forge-v1-active-task') || '')
  expect(taskId).toBeTruthy()
  await writeFile(`${evidenceDir}/task-id.txt`, `${taskId}\n`)
  await page.screenshot({ path: `${evidenceDir}/01-real-phase.png`, fullPage: true })
  const finalize = page.getByTestId('finalize-annotations')
  try { await expect(finalize).toBeVisible({ timeout: 8 * 60 * 1000 }) }
  finally { await writeFile(`${evidenceDir}/browser-diagnostics.txt`, `${diagnostics.join('\n')}\n`) }
  await expect(page.getByTestId('drawing-preview')).toBeVisible()
  await finalize.click()
  await expect(steps.getByRole('button', { name: /审阅确认/ })).toHaveAttribute('aria-current', 'step', { timeout: 8 * 60 * 1000 })
  await expect(page.getByTestId('feature-row').first()).toBeVisible()
  const featureCount = await page.getByTestId('feature-row').count(); expect(featureCount).toBeGreaterThan(0)
  await expect(page.getByTestId('feature-confidence')).toHaveText(Array(featureCount).fill('未提供'))
  await expect(page.getByTestId('feature-row').first()).toContainText(/(vlm|ocr|yolo|geometry|combined|legacy_text)/)

  await expect(page.getByTestId('confirm-review')).toBeVisible()
  await page.getByTestId('confirm-review').click()
  await expect(steps.getByRole('button', { name: /工艺生成/ })).toHaveAttribute('aria-current', 'step', { timeout: 8 * 60 * 1000 })
  await expect(page.getByTestId('operation-row').first()).toBeVisible({ timeout: 8 * 60 * 1000 })
  await expect(page.getByTestId('operation-table')).not.toContainText('```')
  const operationCount = await page.getByTestId('operation-row').count(); expect(operationCount).toBeGreaterThan(0)
  await expect(page.getByText(/未提供/).first()).toBeVisible()
  await expect(page.getByTestId('workflow-phase')).toHaveAttribute('data-phase', 'done', { timeout: 8 * 60 * 1000 })
  await expect(page.getByTestId('workflow-progress-value')).toHaveText('完成度 100%')
  await expect(page.getByTestId('download-export')).toBeVisible()
  await page.screenshot({ path: `${evidenceDir}/02-structured-operation.png`, fullPage: true })

  await steps.getByRole('button', { name: /上传图纸/ }).click()
  await expect(page.getByRole('region', { name: '上传工程图纸' }).getByText('test.png', { exact: false })).toBeVisible()
  await expect(page.getByText(/closed\s*·\s*seq/i)).toHaveCount(0)
  await steps.getByRole('button', { name: /工艺生成/ }).click()
  await expect(page.getByTestId('operation-row')).toHaveCount(operationCount)

  await page.reload()
  await page.getByText('工艺生成').first().click()
  await expect.poll(() => page.evaluate(() => localStorage.getItem('forge-v1-active-task') || ''), { timeout: 30_000 }).toBe(taskId)
  await expect(page.getByTestId('operation-row')).toHaveCount(operationCount, { timeout: 3 * 60 * 1000 })

  const artifacts = await page.evaluate(async ({ id, api }) => {
    const token = localStorage.getItem('forge-token'); const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {}
    const snapshot = await (await fetch(`${api}/api/v1/tasks/${id}`, { headers })).json()
    const wire = await (await fetch(`${api}/api/v1/tasks/${id}/events?after=0`, { headers })).text()
    const events = wire.split(/\r?\n\r?\n/).map((frame) => frame.split(/\r?\n/).filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trim()).join('\n')).filter(Boolean).map((data) => JSON.parse(data))
    return { snapshot, events }
  }, { id: taskId, api: apiBase })
  const cleanSnapshot = sanitizeEvidence(artifacts.snapshot)
  const cleanEvents = artifacts.events.map(sanitizeEvent)
  assertEvidenceClean(cleanSnapshot); assertEvidenceClean(cleanEvents)
  await writeFile(`${evidenceDir}/final-snapshot.json`, JSON.stringify(cleanSnapshot, null, 2))
  await writeFile(`${evidenceDir}/events-sanitized.json`, JSON.stringify(cleanEvents, null, 2))

  const downloadPromise = page.waitForEvent('download'); const exportResponse = page.waitForResponse((response) => response.url().includes(`/api/v1/tasks/${taskId}/export`))
  await page.getByTestId('download-export').click()
  const [download, response] = await Promise.all([downloadPromise, exportResponse])
  expect(response.headers()['content-type']).toContain('application/pdf')
  expect(download.suggestedFilename()).toMatch(/\.pdf$/i)
  const exportPath = `${evidenceDir}/${download.suggestedFilename()}`; await download.saveAs(exportPath)
  expect((await stat(exportPath)).size).toBeGreaterThan(4); expect((await readFile(exportPath)).subarray(0, 4).toString()).toBe('%PDF')
  await page.screenshot({ path: `${evidenceDir}/03-resumed-complete.png`, fullPage: true })
})
