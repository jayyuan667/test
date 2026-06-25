import { test, expect } from '@playwright/test'

const SUPER_ADMIN_USER = {
  id: 1,
  username: 'admin',
  role: 'super_admin',
  enterprise_id: null,
  enterprise_name: null,
  is_active: true,
  created_at: '2026-06-20T00:00:00',
}

const ENTERPRISE_ADMIN_USER = {
  id: 2,
  username: 'factory-admin',
  role: 'enterprise_admin',
  enterprise_id: 9,
  enterprise_name: '演示企业',
  is_active: true,
  created_at: '2026-06-20T00:00:00',
}

const ASSIGNED_USER = {
  id: 3,
  username: 'worker',
  role: 'user',
  enterprise_id: 9,
  enterprise_name: '演示企业',
  is_active: true,
  created_at: '2026-06-20T00:00:00',
}

async function mockAuthenticatedUser(
  page: import('@playwright/test').Page,
  user: typeof SUPER_ADMIN_USER | typeof ENTERPRISE_ADMIN_USER | typeof ASSIGNED_USER = SUPER_ADMIN_USER,
) {
  await page.route('**/api/auth/me', async route => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: { user },
      }),
    })
  })
}

async function openDbPage(page: import('@playwright/test').Page) {
  await page.goto('/')
  await expect(page.getByText('工艺生成')).toBeVisible({ timeout: 10000 })
  await page.getByRole('button', { name: /知识库浏览/ }).click()
}

test.beforeEach(async ({ page }) => {
  // Unlock DbPage database browse before navigation, otherwise it renders the
  // "数据库未解锁" lock screen and never shows the record list.
  await page.addInitScript(() => {
    sessionStorage.setItem('zip_unlocked', 'true')
  })

  await mockAuthenticatedUser(page)

  await page.route('**/api/library/scopes', async route => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          { library_key: 'public', library_name: '公共工艺库', scope_type: 'public', record_count: 2 },
          { library_key: 'private', library_name: '我的工艺库', scope_type: 'private', record_count: 1 },
        ],
        can_browse_db: true,
        active_scope: 'public',
      }),
    })
  })

  await page.route('**/api/library/records?**', async route => {
    const url = new URL(route.request().url())
    const libraryKey = url.searchParams.get('library_key') || 'public'
    const activeScope = libraryKey === 'private'
      ? { library_key: 'private', library_name: '我的工艺库', scope_type: 'private' }
      : { library_key: 'public', library_name: '公共工艺库', scope_type: 'public' }

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
        active_scope: activeScope,
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

  // Mock the preview image asset so the thumbnail img element loads successfully
  // instead of triggering onError (which swaps the aria-label to "暂无图纸快照").
  await page.route('**/api/result/task-1/asset/page-1.png', async route => {
    await route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><rect width="80" height="80" fill="#e2e8f0"/><text x="8" y="44" font-size="10" fill="#94a3b8">preview</text></svg>',
    })
  })
})

test('database list shows thumbnail and opens snapshot modal', async ({ page }) => {
  await openDbPage(page)

  const thumbnail = page.locator('button[aria-label="查看 D125A-181200A003 图纸快照"]')
  await expect(thumbnail).toBeVisible()
  await expect(thumbnail.locator('img')).toHaveAttribute('src', '/api/result/task-1/asset/page-1.png')

  await thumbnail.click()

  await expect(page.locator('text=库记录快照')).toBeVisible()
  await expect(page.locator('img[alt="快照"]')).toHaveAttribute('src', '/api/result/task-1/asset/page-1.png')
})

test('database list shows placeholder when preview images are missing', async ({ page }) => {
  await openDbPage(page)

  const placeholder = page.locator('button[aria-label="NO-PREVIEW 暂无图纸快照"]')
  await expect(placeholder).toBeVisible()
  await expect(placeholder.locator('text=暂无预览')).toBeVisible()
  await expect(placeholder).toHaveCSS('border-top-color', 'rgb(255, 209, 168)')
})

test('super admin can distinguish platform library from personal library', async ({ page }) => {
  await openDbPage(page)

  const scopeSelect = page.locator('select').first()

  await expect(page.getByText('查看平台与个人工艺记录。')).toBeVisible()
  await expect(scopeSelect).toContainText('平台工艺库')
  await expect(scopeSelect).toContainText('个人工艺库')
})

test('enterprise admin does not see platform governance copy in db page', async ({ page }) => {
  await mockAuthenticatedUser(page, ENTERPRISE_ADMIN_USER)

  await openDbPage(page)

  await expect(page.getByText('查看企业复用相关记录与个人工艺库。')).toBeVisible()
  await expect(page.getByText('查看平台与个人工艺记录。')).toHaveCount(0)
  await expect(page.getByText('跨企业治理')).toHaveCount(0)
})

test('public scope keeps record detail actions read-only for super admin', async ({ page }) => {
  await openDbPage(page)

  await page.getByText('D125A-181200A003').click()

  await expect(page.getByRole('button', { name: '编辑记录' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '删除', exact: true })).toHaveCount(0)
  await expect(page.getByText('只读浏览')).toBeVisible()
})

test('assigned user cannot edit or delete records even in private scope', async ({ page }) => {
  await mockAuthenticatedUser(page, ASSIGNED_USER)

  await openDbPage(page)
  await page.locator('select').first().selectOption('private')
  await page.getByText('D125A-181200A003').click()

  await expect(page.getByRole('button', { name: '编辑记录' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '删除', exact: true })).toHaveCount(0)
  await expect(page.getByText('只读浏览')).toBeVisible()
})
