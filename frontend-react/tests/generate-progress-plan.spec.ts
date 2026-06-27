import { expect, test, type Page } from '@playwright/test'
import type { User } from '../src/types/auth'

const USER: User = {
  id: 17,
  username: 'progress-user',
  role: 'user',
  enterprise_id: 1,
  enterprise_name: '测试企业',
  is_active: true,
  created_at: '2026-06-27T00:00:00.000Z',
  quota: { total_granted: 100, used: 0, remaining: 100 },
}

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

async function mockGenerateProgressFlow(page: Page) {
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
        const dispatchFeatureCache = () => {
          if (this.readyState === FakeEventSource.CLOSED) return
          this.dispatchEvent(new MessageEvent('step_start', {
            data: JSON.stringify({ step_name: '特征提取', message: '缓存命中，恢复上次分析结果' }),
          }))
          setTimeout(() => {
            this.dispatchEvent(new MessageEvent('review_required', {
              data: JSON.stringify({
                task_id: 'task-progress',
                content: '【零件名称】缓存件\n【材料】45钢',
                preview_image_urls: ['/api/result/task-progress/asset/page-1.svg'],
              }),
            }))
          }, 9000)
        }

        setTimeout(() => {
          if (connectionIndex === 1) {
            this.dispatchEvent(new MessageEvent('step_start', {
              data: JSON.stringify({ step_name: 'YOLO 检测', message: '正在自动标注特征' }),
            }))
            setTimeout(() => {
              this.dispatchEvent(new MessageEvent('annotation_required', {
                data: JSON.stringify({
                  task_id: 'task-progress',
                  preview_image_urls: ['/api/result/task-progress/asset/page-1.svg'],
                  summary: {},
                }),
              }))
            }, 120)
            window.addEventListener('mockFinalizeAnnotation', dispatchFeatureCache, { once: true })
          } else {
            dispatchFeatureCache()
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
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ success: true, data: { user: USER } }) })
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
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ task_id: 'task-progress', pdf_name: 'test.pdf', message: 'ok' }) })
      return
    }

    if (url.pathname.endsWith('/api/annotations/task-progress')) {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ task_id: 'task-progress', pages: {} }) })
      return
    }

    if (url.pathname.endsWith('/api/annotations/task-progress/finalize')) {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ ok: true, task_id: 'task-progress', mode: 'finalized' }) })
      return
    }

    if (url.pathname.endsWith('/api/review/task-progress')) {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ message: 'Review accepted', task_id: 'task-progress' }) })
      return
    }

    if (url.pathname.endsWith('/api/result/task-progress/asset/page-1.svg')) {
      await route.fulfill({
        contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><rect width="200" height="100" fill="white"/></svg>',
      })
      return
    }

    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({}) })
  })
}

test('工艺生成进度在 YOLO 审阅停 30，并在特征缓存命中后 10 秒平滑到 70', async ({ page }) => {
  await mockGenerateProgressFlow(page)
  await page.goto('/')
  await expect(page.getByText('工艺生成')).toBeVisible({ timeout: 10000 })

  const chooserPromise = page.waitForEvent('filechooser')
  await page.getByText('上传 2D 工艺图纸').click()
  const chooser = await chooserPromise
  await chooser.setFiles({ name: 'test.pdf', mimeType: 'application/pdf', buffer: createTestPdf() })

  await expect(page.getByText('等待人工补全标注')).toBeVisible({ timeout: 10000 })
  await expect(page.getByText('30%')).toBeVisible()

  await page.waitForTimeout(1800)
  await expect(page.getByText('31%')).not.toBeVisible()
  await expect(page.getByText('35%')).not.toBeVisible()

  await page.getByRole('button', { name: '跳过 YOLO 审阅' }).click()
  await page.evaluate(() => window.dispatchEvent(new Event('mockFinalizeAnnotation')))
  await expect(page.getByText(/命中特征缓存/)).toBeVisible({ timeout: 3000 })
  await expect(page.getByText(/6\d%/)).toBeVisible({ timeout: 9000 })
  await expect(page.getByText('请审阅特征报告')).toBeVisible({ timeout: 12000 })
  await expect(page.getByText('70%')).toBeVisible()

  await page.waitForTimeout(1500)
  await expect(page.getByText('71%')).not.toBeVisible()
})

test('确认特征审阅后不会被后续特征 SSE 事件拉回 30', async ({ page }) => {
  await mockGenerateProgressFlow(page)
  await page.goto('/')
  await expect(page.getByText('工艺生成')).toBeVisible({ timeout: 10000 })

  const chooserPromise = page.waitForEvent('filechooser')
  await page.getByText('上传 2D 工艺图纸').click()
  const chooser = await chooserPromise
  await chooser.setFiles({ name: 'test.pdf', mimeType: 'application/pdf', buffer: createTestPdf() })

  await expect(page.getByText('等待人工补全标注')).toBeVisible({ timeout: 10000 })
  await page.getByRole('button', { name: '跳过 YOLO 审阅' }).click()
  await page.evaluate(() => window.dispatchEvent(new Event('mockFinalizeAnnotation')))
  await expect(page.getByText('请审阅特征报告')).toBeVisible({ timeout: 12000 })
  await expect(page.getByText('70%')).toBeVisible()

  await page.getByRole('button', { name: '确认特征并继续' }).click()
  await expect(page.getByText('正在生成工艺规程...')).toBeVisible({ timeout: 3000 })
  await page.waitForTimeout(1400)

  await expect(page.getByText('30%')).not.toBeVisible()
  await expect(page.getByText(/7\d%|8\d%|9\d%/)).toBeVisible()
})
