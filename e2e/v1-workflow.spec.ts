import { expect, test } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'

const fixture = '/Users/caojiayuan/Documents/测试包/drawing/test.png'
const evidenceDir = '/tmp/forge-v1-evidence'

test('real v1 drawing workflow resumes and exports structured data', async ({ page }) => {
  test.setTimeout(20 * 60 * 1000)
  await mkdir(evidenceDir, { recursive: true })
  const diagnostics: string[] = []
  page.on('console', (message) => diagnostics.push(`console:${message.type()}:${message.text()}`))
  page.on('requestfailed', (request) => diagnostics.push(`requestfailed:${request.method()}:${new URL(request.url()).pathname}:${request.failure()?.errorText}`))

  await page.goto('/')
  await page.getByText('进入系统').first().click()
  await page.locator('#username').fill('test')
  await page.locator('#pwd').fill('test123')
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByText('控制台').first()).toBeVisible({ timeout: 20_000 })
  await page.getByText('工艺生成').first().click()
  await expect(page.getByTestId('v1-workflow')).toBeVisible()

  await page.getByTestId('drawing-upload').setInputFiles(fixture)
  await page.getByTestId('start-analysis').click()
  await expect(page.getByTestId('workflow-status')).toBeVisible({ timeout: 30_000 })
  const taskId = await page.getByTestId('task-id').innerText()
  expect(taskId).toBeTruthy()
  await writeFile(`${evidenceDir}/task-id.txt`, `${taskId}\n`)
  await page.screenshot({ path: `${evidenceDir}/01-real-phase.png`, fullPage: true })
  const streamProbe = await page.evaluate(async (id) => {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 5_000)
    try {
      const token = localStorage.getItem('forge-token')
      const response = await fetch(`http://localhost:5390/api/v1/tasks/${id}/events?after=0`, { headers: token ? { Authorization: `Bearer ${token}` } : {}, signal: controller.signal })
      const reader = response.body?.getReader(); const decoder = new TextDecoder(); let text = ''
      while (reader && text.length < 10_000 && !text.includes('annotation_required')) { const part = await reader.read(); if (part.done) break; text += decoder.decode(part.value) }
      return { status: response.status, text }
    } finally { clearTimeout(timer); controller.abort() }
  }, taskId)
  await writeFile(`${evidenceDir}/browser-sse-probe.json`, JSON.stringify(streamProbe, null, 2))

  const finalize = page.getByTestId('finalize-annotations')
  try { await expect(finalize).toBeVisible({ timeout: 8 * 60 * 1000 }) }
  finally { await writeFile(`${evidenceDir}/browser-diagnostics.txt`, `${diagnostics.join('\n')}\n`) }
  await finalize.click()
  await expect(page.getByTestId('feature-row').first()).toBeVisible({ timeout: 8 * 60 * 1000 })
  await expect(page.getByTestId('feature-source').first()).toContainText('来源：')
  await expect(page.getByTestId('feature-confidence').first()).toContainText(/(未提供|\d+%)/)

  await expect(page.getByTestId('confirm-review')).toBeVisible({ timeout: 3 * 60 * 1000 })
  await page.getByTestId('confirm-review').click()
  await expect(page.getByTestId('operation-row').first()).toBeVisible({ timeout: 8 * 60 * 1000 })
  await page.screenshot({ path: `${evidenceDir}/02-structured-operation.png`, fullPage: true })

  await page.reload()
  await page.getByText('工艺生成').first().click()
  await expect(page.getByTestId('task-id')).toHaveText(taskId, { timeout: 30_000 })
  await expect(page.getByTestId('operation-row').first()).toBeVisible({ timeout: 3 * 60 * 1000 })

  const downloadPromise = page.waitForEvent('download')
  await page.getByTestId('download-export').click()
  const download = await downloadPromise
  await download.saveAs(`${evidenceDir}/${download.suggestedFilename()}`)
  await page.screenshot({ path: `${evidenceDir}/03-resumed-complete.png`, fullPage: true })
})
