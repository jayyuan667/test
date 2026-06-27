import { expect, test } from '@playwright/test'
import type { User } from '../src/types/auth'

const USER: User = {
  id: 9,
  username: 'annotator',
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

async function mockAnnotationFlow(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    class FakeEventSource extends EventTarget {
      static CONNECTING = 0
      static OPEN = 1
      static CLOSED = 2
      readyState = FakeEventSource.OPEN
      url: string

      constructor(url: string) {
        super()
        this.url = url
        setTimeout(() => {
          this.dispatchEvent(new MessageEvent('annotation_required', {
            data: JSON.stringify({
              task_id: 'task-annotation',
              preview_image_urls: ['/api/result/task-annotation/asset/page-1.svg'],
              summary: {},
            }),
          }))
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
        body: JSON.stringify({ task_id: 'task-annotation', pdf_name: 'test.pdf', message: 'ok' }),
      })
      return
    }

    if (url.pathname.endsWith('/api/annotations/task-annotation')) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ task_id: 'task-annotation', pages: {} }),
      })
      return
    }

    if (url.pathname.endsWith('/api/annotations/task-annotation/save')) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ ok: true }),
      })
      return
    }

    if (url.pathname.endsWith('/api/result/task-annotation/asset/page-1.svg')) {
      await route.fulfill({
        contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><rect width="200" height="100" fill="white"/><path d="M20 50h160" stroke="#94a3b8"/></svg>',
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

test('YOLO 标注拖拽模式使用拖拽鼠标且不会绘制临时框', async ({ page }) => {
  await mockAnnotationFlow(page)
  await page.goto('/')
  await expect(page.getByText('工艺生成')).toBeVisible({ timeout: 10000 })

  const chooserPromise = page.waitForEvent('filechooser')
  await page.getByText('上传 2D 工艺图纸').click()
  const chooser = await chooserPromise
  await chooser.setFiles({
    name: 'test-drawing.pdf',
    mimeType: 'application/pdf',
    buffer: createTestPdf(),
  })

  await expect(page.locator('text=等待人工补全标注')).toBeVisible({ timeout: 10000 })
  await page.locator('button:has-text("开始标注")').click()
  await expect(page.locator('text=标注工具')).toBeVisible({ timeout: 5000 })

  await page.getByRole('button', { name: '✚ 标注' }).click()

  const svg = page.locator('svg.anno-svg')
  await expect(svg).toHaveCSS('cursor', 'grab')

  const box = await svg.boundingBox()
  expect(box).not.toBeNull()
  if (!box) return

  await page.mouse.move(box.x + 20, box.y + 20)
  await page.mouse.down()
  await page.mouse.move(box.x + 90, box.y + 70)
  await expect(page.locator('rect.anno-temp-rect')).toHaveCount(0)
  await expect(svg).toHaveCSS('cursor', 'grabbing')
  await page.mouse.up()
  await expect(svg).toHaveCSS('cursor', 'grab')
})
