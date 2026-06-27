import { expect, test, type Page } from '@playwright/test'
import type { User } from '../src/types/auth'

const USER: User = {
  id: 7,
  username: 'process-editor',
  role: 'user',
  enterprise_id: 1,
  enterprise_name: '测试企业',
  is_active: true,
  created_at: '2026-06-26T00:00:00.000Z',
  quota: {
    total_granted: 100,
    used: 1,
    remaining: 99,
  },
}

const PROCESS_ROWS = [
  { code: '0010', trade: '车', content: '粗车外圆' },
  { code: '0020', trade: '检验', content: '检验尺寸' },
]

function createTestPdf(): Buffer {
  return Buffer.from(`%PDF-1.0
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 200 100]/Parent 2 0 R>>endobj
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

async function mockCompletedProcessFlow(page: Page) {
  await page.addInitScript(() => {
    class FakeEventSource extends EventTarget {
      static CONNECTING = 0
      static OPEN = 1
      static CLOSED = 2
      static connectionCount = 0
      readyState = FakeEventSource.OPEN
      url: string

      constructor(url: string) {
        super()
        this.url = url
        FakeEventSource.connectionCount += 1
        const connectionIndex = FakeEventSource.connectionCount
        setTimeout(() => {
          if (connectionIndex === 1) {
            this.dispatchEvent(new MessageEvent('review_required', {
              data: JSON.stringify({
                task_id: 'task-process',
                content: '【零件名称】测试件',
              }),
            }))
          } else {
            this.dispatchEvent(new MessageEvent('complete', {
              data: JSON.stringify({ task_id: 'task-process' }),
            }))
          }
        }, 50)
      }

      close() {
        this.readyState = FakeEventSource.CLOSED
      }
    }

    Object.defineProperty(window, 'EventSource', {
      configurable: true,
      writable: true,
      value: FakeEventSource,
    })
  })

  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url())
    if (!url.pathname.startsWith('/api/')) {
      await route.fallback()
      return
    }

    if (url.pathname.endsWith('/api/auth/me')) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: { user: USER } }),
      })
      return
    }

    if (url.pathname.endsWith('/api/library/scopes')) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [{ library_key: 'public', library_name: '公共工艺库', scope_type: 'public' }] }),
      })
      return
    }

    if (url.pathname.endsWith('/api/upload_drawing')) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ task_id: 'task-process', pdf_name: 'test.pdf', message: 'ok' }),
      })
      return
    }

    if (url.pathname.endsWith('/api/review/task-process')) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Review accepted', task_id: 'task-process' }),
      })
      return
    }

    if (url.pathname.endsWith('/api/status/task-process')) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ task_id: 'task-process', status: 'completed', progress: 100, pdf_name: 'test.pdf' }),
      })
      return
    }

    if (url.pathname.endsWith('/api/result/task-process')) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          task_id: 'task-process',
          pdf_name: 'test.pdf',
          process_flow: { data: PROCESS_ROWS },
        }),
      })
      return
    }

    await route.fulfill({
      contentType: 'application/json',
      status: 200,
      body: JSON.stringify({}),
    })
  })
}

test('final process table shows an inserted blank row immediately', async ({ page }) => {
  await mockCompletedProcessFlow(page)

  await page.goto('/')
  await expect(page.getByText('等待文件进入解析流程')).toBeVisible({ timeout: 10000 })

  await page.locator('input[type="file"]').setInputFiles({
    name: 'test.pdf',
    mimeType: 'application/pdf',
    buffer: createTestPdf(),
  })
  await expect(page.getByText('请审阅特征报告')).toBeVisible({ timeout: 10000 })

  await page.getByRole('button', { name: '确认特征并继续' }).click()
  await expect(page.getByText('工艺生成完成，共 2 道工序')).toBeVisible({ timeout: 10000 })

  const tableRows = page.locator('[data-active-tab="process"] .data-table-wrap table.data-table tbody tr')
  await expect(tableRows).toHaveCount(2)

  await page.locator('button[title="在下方插入"]').first().click()

  await expect(tableRows).toHaveCount(3)
  await expect(tableRows.nth(1).locator('.cell-editable')).toHaveText('')
})
