import { test, expect } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  // Unlock DbPage database browse before navigation, otherwise it renders the
  // "数据库未解锁" lock screen and never shows the record list.
  await page.addInitScript(() => {
    sessionStorage.setItem('zip_unlocked', 'true')
  })

  await page.route('**/api/library/scopes', async route => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: [{ library_key: 'public', library_name: '公共工艺库', scope_type: 'public', record_count: 2 }],
        can_browse_db: true,
        active_scope: 'public',
      }),
    })
  })

  await page.route('**/api/library/records?**', async route => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: 1,
            prefix: 'D125A-181200A003',
            product_type: '轴类',
            process_summary: '0010 车 车外圆',
            context: '',
            tech_requirement: '',
            created_at: '2026-06-20T00:00:00',
            process_count: 1,
            content: '[]',
            process_list: [{ code: '0010', trade: '车', content: '车外圆' }],
            trades: ['车'],
            source_type: 'web_upload',
            source_task_id: 'task-1',
            preview_task_id: 'task-1',
            preview_total_pages: 1,
            preview_image_urls: ['/api/result/task-1/asset/page-1.png'],
            feature_report_text: '【零件名称】D125A-181200A003',
            feature_report_path: '',
            feature_report_json: {},
            real: 1,
          },
          {
            id: 2,
            prefix: 'NO-PREVIEW',
            product_type: '未知',
            process_summary: '',
            context: '',
            tech_requirement: '',
            created_at: '2026-06-20T00:00:00',
            process_count: 0,
            content: '[]',
            process_list: [],
            trades: [],
            source_type: 'web_upload',
            source_task_id: '',
            preview_task_id: '',
            preview_total_pages: 0,
            preview_image_urls: [],
            feature_report_text: '',
            feature_report_path: '',
            feature_report_json: {},
            real: 1,
          },
        ],
        page: 1,
        page_size: 3,
        total: 2,
        total_pages: 1,
        product_types: ['轴类'],
        active_scope: { library_key: 'public', library_name: '公共工艺库', scope_type: 'public' },
      }),
    })
  })

  await page.route('**/api/library/records/1?**', async route => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        id: 1,
        prefix: 'D125A-181200A003',
        product_type: '轴类',
        process_summary: '0010 车 车外圆',
        context: '',
        tech_requirement: '',
        created_at: '2026-06-20T00:00:00',
        process_count: 1,
        content: '[]',
        process_list: [{ code: '0010', trade: '车', content: '车外圆' }],
        trades: ['车'],
        source_type: 'web_upload',
        source_task_id: 'task-1',
        preview_task_id: 'task-1',
        preview_total_pages: 1,
        preview_image_urls: ['/api/result/task-1/asset/page-1.png'],
        feature_report_text: '【零件名称】D125A-181200A003',
        feature_report_path: '',
        feature_report_json: {},
        real: 1,
      }),
    })
  })
})

test('database list shows thumbnail and opens snapshot modal', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /知识库浏览/ }).click()

  const thumbnail = page.locator('button[aria-label="查看 D125A-181200A003 图纸快照"]')
  await expect(thumbnail).toBeVisible()
  await expect(thumbnail.locator('img')).toHaveAttribute('src', '/api/result/task-1/asset/page-1.png')

  await thumbnail.click()

  await expect(page.locator('text=库记录快照')).toBeVisible()
  await expect(page.locator('img[alt="快照"]')).toHaveAttribute('src', '/api/result/task-1/asset/page-1.png')
})

test('database list shows placeholder when preview images are missing', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /知识库浏览/ }).click()

  const placeholder = page.locator('button[aria-label="NO-PREVIEW 暂无图纸快照"]')
  await expect(placeholder).toBeVisible()
  await expect(placeholder.locator('text=暂无预览')).toBeVisible()
})
