import { test, expect, type Page } from '@playwright/test'

function createTestPdf(): Buffer {
  return Buffer.from(`%PDF-1.0
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer<</Size 4/Root 1 0 R>>
startxref
190
%%EOF`)
}

/** Inject SSE monitor that hooks ALL EventSource instances via prototype */
async function injectSSEMonitor(page: Page) {
  await page.evaluate(() => {
    ;(window as any).__sseAllEvents = []
    const origAdd = EventSource.prototype.addEventListener
    EventSource.prototype.addEventListener = function (type: string, listener: any, ...args: any[]) {
      const wrapped = function (e: any) {
        ;(window as any).__sseAllEvents.push({
          t: Date.now(),
          type,
          len: e.data?.length || 0,
          preview: e.data?.slice(0, 120) || '',
        })
        return typeof listener === 'function' ? listener(e) : listener?.handleEvent?.(e)
      }
      return origAdd.call(this, type, wrapped, ...args)
    }
  })
}

/** Full flow: upload → annotate → finalize → review → confirm */
async function runFullFlow(page: Page) {
  await page.goto('/')
  await expect(page.locator('text=等待文件进入解析流程')).toBeVisible({ timeout: 10000 })

  await page.locator('input[type="file"]').setInputFiles({
    name: 'test.pdf', mimeType: 'application/pdf', buffer: createTestPdf(),
  })
  await expect(page.locator('text=等待人工补全标注')).toBeVisible({ timeout: 20000 })

  await page.locator('button:has-text("开始标注")').click()
  await expect(page.locator('.fixed.inset-0')).toBeVisible({ timeout: 5000 })
  await page.locator('button:has-text("退出标注")').click()
  await expect(page.locator('.fixed.inset-0')).not.toBeVisible({ timeout: 5000 })

  await page.locator('button:has-text("完成标注")').click()
  await expect(page.locator('text=请审阅特征报告')).toBeVisible({ timeout: 30000 })
}

test('SSE 全量事件追踪（含确认后）', async ({ page }) => {
  await injectSSEMonitor(page)
  await runFullFlow(page)

  // Clear events from the first connection, keep only post-confirm
  await page.evaluate(() => { (window as any).__sseAllEvents = [] })

  // Confirm review
  await page.locator('button:has-text("确认特征并继续")').click()

  // Wait for completion or timeout
  let reached = false
  try {
    await expect(
      page.locator('text=工艺').or(page.locator('text=生成完成')).or(page.locator('text=工序')).first()
    ).toBeVisible({ timeout: 60000 })
    reached = true
  } catch { /* timeout */ }

  await page.waitForTimeout(3000)

  const events = await page.evaluate(() => (window as any).__sseAllEvents)

  console.log('\n========== 确认后 SSE 事件 ==========')
  console.log(`到达工艺页面: ${reached}`)
  console.log(`事件总数: ${events.length}`)

  if (events.length > 0) {
    const groups = new Map<string, number>()
    for (const e of events) groups.set(e.type, (groups.get(e.type) || 0) + 1)
    console.log('\n类型统计:')
    for (const [type, count] of groups) console.log(`  ${type}: ${count}`)

    console.log('\n时间线 (前30):')
    for (const e of events.slice(0, 30)) {
      console.log(`  +${e.t}ms [${e.type}] len=${e.len} "${e.preview}"`)
    }

    const ps = events.filter((e: any) => e.type === 'process_stream')
    if (ps.length > 0) {
      console.log(`\n=== process_stream ===`)
      console.log(`事件数: ${ps.length}, 跨度: ${ps[ps.length - 1].t - ps[0].t}ms`)
      const intervals = []
      for (let i = 1; i < ps.length; i++) intervals.push(ps[i].t - ps[i - 1].t)
      if (intervals.length > 0) {
        const avg = intervals.reduce((a: number, b: number) => a + b, 0) / intervals.length
        const sorted = [...intervals].sort((a: number, b: number) => a - b)
        console.log(`间隔: 平均=${avg.toFixed(0)}ms 中位=${sorted[Math.floor(sorted.length / 2)]}ms 最小=${sorted[0]}ms 最大=${sorted[sorted.length - 1]}ms`)
        console.log(`前15间隔: ${intervals.slice(0, 15).join(', ')} ms`)
      }
    } else {
      console.log('\n⚠️ 无 process_stream 事件')
    }

    const complete = events.filter((e: any) => e.type === 'complete')
    console.log(`\ncomplete: ${complete.length}`)
    if (complete.length > 0) console.log(`  ${complete[0].preview}`)
  } else {
    console.log('\n⚠️ 确认后无任何 SSE 事件！新 EventSource 未收到数据。')
  }

  // Page state
  const state = await page.evaluate(() => ({
    rows: document.querySelectorAll('tbody tr').length,
    text: document.body.innerText.slice(0, 400),
  }))
  console.log(`\n=== 页面 ===`)
  console.log(`行数: ${state.rows}`)
  console.log(`文本: ${state.text.slice(0, 300)}`)

  expect(reached).toBe(true)
})
