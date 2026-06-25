import { test, expect } from '@playwright/test'
import type { User } from '../src/types/auth'

const ADMIN = { username: 'admin', password: 'admin123' }
const ASSIGNED_USER: User = {
  id: 21,
  username: 'assigned_user',
  role: 'user',
  enterprise_id: 9,
  enterprise_name: '华东工厂',
  is_active: true,
  created_at: '2026-06-25T00:00:00.000Z',
  grant_expires_at: null,
  quota: {
    total_granted: 20,
    used: 4,
    remaining: 16,
  },
}

const ENTERPRISE_ADMIN_USER: User = {
  id: 22,
  username: 'enterprise_admin',
  role: 'enterprise_admin',
  enterprise_id: 9,
  enterprise_name: '华东工厂',
  is_active: true,
  created_at: '2026-06-25T00:00:00.000Z',
  grant_expires_at: '2027-06-25T00:00:00.000Z',
  quota: {
    total_granted: 120,
    used: 10,
    remaining: 110,
  },
}

const SUPER_ADMIN_USER: User = {
  id: 1,
  username: 'admin',
  role: 'super_admin',
  enterprise_id: null,
  enterprise_name: null,
  is_active: true,
  created_at: '2026-06-25T00:00:00.000Z',
  grant_expires_at: null,
  quota: {
    total_granted: 999999,
    used: 0,
    remaining: 999999,
  },
}

/**
 * ZIP 入库 → 数据库浏览 完整链路测试
 *
 * 覆盖:
 *   1. ZipPage 加载、上传、sessionStorage 解锁
 *   2. DbPage 锁屏 → 解锁 → 记录列表
 *   3. 边界情况: 刷新保持解锁、未入库前锁定、删除记录、删除库
 */

/* ── Test helpers ── */

function createTestZip(): Buffer {
  const content = Buffer.from('mock prt content')
  const filename = Buffer.from('test.1', 'utf8')
  const chunks: Buffer[] = []

  // Local file header
  const locHeader = Buffer.alloc(30)
  locHeader.writeUInt32LE(0x04034b50, 0)
  locHeader.writeUInt16LE(20, 4)
  locHeader.writeUInt32LE(content.length, 18)
  locHeader.writeUInt32LE(content.length, 22)
  locHeader.writeUInt16LE(filename.length, 26)
  chunks.push(locHeader, filename, content)

  // Central directory
  const cd = Buffer.alloc(46)
  cd.writeUInt32LE(0x02014b50, 0)
  cd.writeUInt16LE(20, 4)
  cd.writeUInt16LE(20, 6)
  cd.writeUInt32LE(content.length, 20)
  cd.writeUInt32LE(content.length, 24)
  cd.writeUInt16LE(filename.length, 28)
  cd.writeUInt32LE(30, 42)
  chunks.push(cd, filename)

  // EOCD
  const eocd = Buffer.alloc(22)
  eocd.writeUInt32LE(0x06054b50, 0)
  eocd.writeUInt16LE(1, 8)
  eocd.writeUInt16LE(1, 10)
  eocd.writeUInt32LE(cd.length + filename.length, 12)
  eocd.writeUInt32LE(30 + filename.length + content.length, 16)
  chunks.push(eocd)

  return Buffer.concat(chunks)
}

/** Upload a test ZIP via the file chooser (ZipPage creates file input dynamically) */
async function uploadTestZip(page: import('@playwright/test').Page) {
  const fileChooserPromise = page.waitForEvent('filechooser')
  await page.getByRole('button', { name: '上传工艺包' }).click()
  const fileChooser = await fileChooserPromise
  await fileChooser.setFiles({
    name: 'test-process-package.zip',
    mimeType: 'application/zip',
    buffer: createTestZip(),
  })
}

async function loginAs(page: import('@playwright/test').Page) {
  await page.goto('/')
  await page.getByRole('button', { name: '进入系统' }).click()
  await page.getByLabel('用户名').fill(ADMIN.username)
  await page.locator('#password').fill(ADMIN.password)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByText('工艺生成')).toBeVisible({ timeout: 10000 })
}

async function mockAuthSession(page: import('@playwright/test').Page, user: User) {
  await page.route('**/api/auth/me', async route => {
    await route.fulfill({
      contentType: 'application/json',
      status: 200,
      body: JSON.stringify({ success: true, data: { user } }),
    })
  })
}

async function openZipPage(page: import('@playwright/test').Page) {
  await loginAs(page)
  await page.getByRole('button', { name: /工艺入库/ }).click()
}

async function openZipPageAs(page: import('@playwright/test').Page, user: User) {
  await mockAuthSession(page, user)
  await page.goto('/')
  await expect(page.getByText('工艺生成')).toBeVisible({ timeout: 10000 })
  await page.getByRole('button', { name: /工艺入库/ }).click()
}

async function openDbPage(page: import('@playwright/test').Page) {
  await loginAs(page)
  await page.getByRole('button', { name: /知识库浏览/ }).click()
}

/* ── Mock data ── */

const MOCK_ZIP_REPORT = {
  batch_id: 'test-batch-001',
  zip_name: 'test-process-package.zip',
  conflict_mode: 'replace',
  library_mode: 'private_seed_public',
  summary: {
    total_files: 3, prt_count: 1, pdf_count: 1, image_count: 0, xlsx_count: 1,
    matched_pairs: 1, imported_count: 1, skipped_count: 0, error_count: 0,
  },
  matched_pairs: [{
    prefix: 'TEST-181200A001', status: 'imported',
    existing: null,
    draft: {
      process_summary: '0010 备料 | 0020 车', context: '测试工艺',
      process_list: [{ code: '0010', trade: '备料', content: '备料' }, { code: '0020', trade: '车', content: '车外圆' }],
      pdf_page_count: 1,
    },
    prt_names: ['test.1'], pdf_names: ['test.pdf'], xlsx_names: ['test.xlsx'],
    conflict_mode: 'replace',
  }],
  unmatched_pdfs: [], unmatched_xlsx: [], unmatched_prts: [], unmatched_images: [], errors: [],
  target_library: { library_key: '__new_test_lib', library_name: '我的工艺库' },
  created_at: '2026-06-21T00:00:00',
}

const MOCK_SCOPES_BEFORE = {
  items: [
    { library_key: 'public', library_name: '公共工艺库', scope_type: 'public', record_count: 0 },
    { library_key: 'private-huadong', library_name: '华东工厂知识库', scope_type: 'private', record_count: 0 },
  ],
  can_browse_db: false, imported_batches: 0,
}

const MOCK_SCOPES_AFTER = {
  items: [
    { library_key: '__new_test_lib', library_name: '我的工艺库', scope_type: 'private', record_count: 1 },
    { library_key: 'public', library_name: '公共工艺库', scope_type: 'public', record_count: 0 },
  ],
  can_browse_db: true, imported_batches: 1,
}

const MOCK_RECORD = {
  id: 1, prefix: 'TEST-181200A001', product_type: '轴类',
  process_summary: '0010 备料 | 0020 车', context: '',
  tech_requirement: '调质处理 HB 240-280', created_at: '2026-06-21T00:00:00',
  process_count: 2, content: '[]',
  process_list: [{ code: '0010', trade: '备料', content: '备料' }, { code: '0020', trade: '车', content: '车外圆' }],
  trades: ['备料', '车'], source_type: 'zip_import', source_task_id: 'test-batch-001',
  preview_task_id: '', preview_total_pages: 0, preview_image_urls: [],
  feature_report_text: '', feature_report_path: '', feature_report_json: {}, real: 1,
}

const MOCK_RECORDS_RES = {
  items: [MOCK_RECORD], page: 1, page_size: 3, total: 1, total_pages: 1,
  product_types: ['轴类'],
  active_scope: { library_key: '__new_test_lib', library_name: '我的工艺库', scope_type: 'private' },
}

/* ── Route helpers ── */

async function mockScopes(page: import('@playwright/test').Page, data = MOCK_SCOPES_BEFORE) {
  await page.route('**/api/library/scopes', async route => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) })
  })
}

async function mockRecords(page: import('@playwright/test').Page, data = MOCK_RECORDS_RES) {
  await page.route('**/api/library/records?**', async route => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) })
  })
}

/* ── Tests ── */

test.describe('ZIP 入库 → 数据库浏览 完整链路', () => {

  test('regular assigned user defaults to personal library target', async ({ page }) => {
    await mockScopes(page)

    await openZipPageAs(page, ASSIGNED_USER)

    await expect(page.locator('#zip-target-library')).not.toContainText('公共工艺库')
    await expect(page.locator('#zip-target-library')).toContainText('华东工厂知识库')
    await expect(page.getByText('默认推荐先写入我的工艺库，确认后再决定共享。', { exact: true })).toBeVisible()
  })

  test('enterprise admin sees enterprise-only helper copy without platform governance wording', async ({ page }) => {
    await mockScopes(page)

    await openZipPageAs(page, ENTERPRISE_ADMIN_USER)

    await expect(page.getByText('本阶段企业范围仅做界面引导；真实入库仍写入你当前可用的个人工艺库。')).toBeVisible()
    await expect(page.getByText(/平台|全部企业|跨企业治理/)).not.toBeVisible()
  })

  test('super admin can still choose public baseline target', async ({ page }) => {
    await page.addInitScript(() => sessionStorage.clear())
    await mockScopes(page)

    let submittedMode = ''
    let submittedKey = ''
    await page.route('**/api/kb/import_zip', async route => {
      const body = route.request().postData() || ''
      submittedMode = body.includes('name="library_mode"\r\n\r\npublic') ? 'public' : ''
      submittedKey = body.includes('name="library_key"\r\n\r\npublic') ? 'public' : ''
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(MOCK_ZIP_REPORT) })
    })

    await openZipPageAs(page, SUPER_ADMIN_USER)

    await expect(page.locator('#zip-target-library')).toContainText('公共工艺库（平台基线库 · 0条）')
    await page.selectOption('#zip-target-library', 'public')
    await uploadTestZip(page)

    await expect(page.getByText('入库完成')).toBeVisible({ timeout: 10000 })
    expect(submittedMode).toBe('public')
    expect(submittedKey).toBe('public')
  })

  test('1. ZipPage 加载后显示下载示例 ZIP 按钮和上传区域', async ({ page }) => {
    await mockScopes(page)

    await openZipPage(page)

    await expect(page.getByText('上传一个 ZIP')).toBeVisible()
    await expect(page.getByText('下载示例 ZIP')).toBeVisible()
    await expect(page.locator('text=拖拽 ZIP 工艺包到此处')).toBeVisible()
    await expect(page.getByText('入库目标')).toBeVisible()
  })

  test('2. 未入库前，数据库浏览页显示锁屏', async ({ page }) => {
    // Ensure clean session
    await page.addInitScript(() => sessionStorage.clear())
    await mockScopes(page)

    await openDbPage(page)

    await expect(page.getByText('数据库未解锁')).toBeVisible()
    await expect(page.getByText('请先完成知识库导入操作后再浏览数据库')).toBeVisible()
    await expect(page.getByRole('button', { name: '前往导入' })).toBeVisible()
    await expect(page.getByRole('button', { name: '查看公共库' })).toBeVisible()
  })

  test('3. 锁屏中点击"查看公共库"→ sessionStorage 解锁 → 数据库浏览', async ({ page }) => {
    await page.addInitScript(() => sessionStorage.clear())
    await mockScopes(page, { ...MOCK_SCOPES_BEFORE, can_browse_db: true })
    await mockRecords(page)

    await openDbPage(page)

    await expect(page.getByText('数据库未解锁')).toBeVisible()

    // Click "查看公共库" — this sets sessionStorage and navigates
    await page.getByRole('button', { name: '查看公共库' }).click()

    await expect(page.getByText('数据库未解锁')).not.toBeVisible()
    await expect(page.getByText('记录列表')).toBeVisible()
  })

  test('4. ZIP 入库成功后 sessionStorage 解锁标记被设置（修复验证）', async ({ page }) => {
    await page.addInitScript(() => sessionStorage.clear())
    await mockScopes(page)
    await page.route('**/api/kb/import_zip', async route => {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(MOCK_ZIP_REPORT) })
    })

    await openZipPage(page)
    await uploadTestZip(page)

    await expect(page.getByText('入库完成')).toBeVisible({ timeout: 10000 })

    // ★ KEY ASSERTION: the fix ensures sessionStorage flag is set after success
    const unlocked = await page.evaluate(() => sessionStorage.getItem('zip_unlocked'))
    expect(unlocked).toBe('true')
  })

  test('5. 入库成功后导航到数据库浏览页 → 直接显示记录列表（不锁屏）', async ({ page }) => {
    await page.addInitScript(() => sessionStorage.clear())

    let scopeCall = 0
    await page.route('**/api/library/scopes', async route => {
      scopeCall++
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(scopeCall >= 2 ? MOCK_SCOPES_AFTER : MOCK_SCOPES_BEFORE),
      })
    })
    await page.route('**/api/kb/import_zip', async route => {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(MOCK_ZIP_REPORT) })
    })
    await mockRecords(page)

    await openZipPage(page)
    await uploadTestZip(page)
    await expect(page.getByText('入库完成')).toBeVisible({ timeout: 10000 })

    // Navigate to DB — should NOT show lock screen
    await page.getByRole('button', { name: /知识库浏览/ }).click()

    await expect(page.getByText('数据库未解锁')).not.toBeVisible()
    await expect(page.getByText('记录列表')).toBeVisible()
    // ZipPage matched-pair card is hidden after navigation; DbPage list is the visible one
    await expect(page.locator('text=TEST-181200A001').last()).toBeVisible()
    // "轴类" appears in filter dropdown + record card; use .last() for the card span
    await expect(page.getByText('轴类').last()).toBeVisible()
  })

  test('6. 页面刷新后解锁状态保持（sessionStorage 持久化）', async ({ page }) => {
    // Pre-set sessionStorage (simulates coming from a successful import)
    await page.addInitScript(() => sessionStorage.setItem('zip_unlocked', 'true'))
    await mockScopes(page, MOCK_SCOPES_AFTER)
    await mockRecords(page)

    await openDbPage(page)

    await expect(page.getByText('数据库未解锁')).not.toBeVisible()
    await expect(page.getByText('记录列表')).toBeVisible()
  })

  test('7. 入库后记录详情可查看', async ({ page }) => {
    await page.addInitScript(() => sessionStorage.setItem('zip_unlocked', 'true'))
    await mockScopes(page, MOCK_SCOPES_AFTER)
    await mockRecords(page)

    // Mock single record fetch
    await page.route('**/api/library/records/1**', async route => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ contentType: 'application/json', body: JSON.stringify(MOCK_RECORD) })
      } else {
        await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ ok: true }) })
      }
    })

    await openDbPage(page)
    await expect(page.getByText('记录列表')).toBeVisible()

    // Click on record card
    await page.locator('text=TEST-181200A001').first().click()

    // Detail view: look for the process table section header (specific selector avoids hidden tab buttons)
    await expect(page.locator('div.text-flame-600:has-text("工艺规程")')).toBeVisible()
    // Use getByRole for table cells to avoid strict-mode from summary text
    await expect(page.getByRole('cell', { name: '0010' })).toBeVisible()
    await expect(page.getByRole('cell', { name: '0020' })).toBeVisible()
    await expect(page.getByText('调质处理 HB 240-280')).toBeVisible()
    await expect(page.getByText('来源：工艺入库')).toBeVisible()
  })

  test('8. 删除记录：确认弹窗 → 确认删除 → 列表刷新', async ({ page }) => {
    await page.addInitScript(() => sessionStorage.setItem('zip_unlocked', 'true'))
    await mockScopes(page, MOCK_SCOPES_AFTER)

    let deleteCalled = false

    // Intercept records list: return items normally, empty only after deletion confirmed
    await page.route('**/api/library/records?**', async route => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(
          deleteCalled ? { ...MOCK_RECORDS_RES, items: [], total: 0 } : MOCK_RECORDS_RES,
        ),
      })
    })

    // Single record GET/DELETE
    await page.route('**/api/library/records/*', async route => {
      if (route.request().method() === 'DELETE') {
        deleteCalled = true
        await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ ok: true }) })
      } else {
        await route.fulfill({ contentType: 'application/json', body: JSON.stringify(MOCK_RECORD) })
      }
    })

    await openDbPage(page)

    await expect(page.getByText('TEST-181200A001')).toBeVisible({ timeout: 5000 })

    // Click record to view detail
    await page.locator('text=TEST-181200A001').last().click()

    // Wait for detail view to fully render (the "编辑记录" button confirms it)
    await expect(page.getByRole('button', { name: '编辑记录' })).toBeVisible({ timeout: 5000 })

    // Click delete button in detail view (use exact match to avoid "删除当前数据库")
    await page.getByRole('button', { name: '删除', exact: true }).click()

    // Confirmation modal
    await expect(page.getByText('确认删除记录')).toBeVisible()
    await expect(page.getByText('此操作不可恢复')).toBeVisible()

    // Confirm
    await page.getByRole('button', { name: '确认删除' }).click()

    expect(deleteCalled).toBe(true)

    // List should refresh to empty
    await expect(page.getByText('暂无记录')).toBeVisible({ timeout: 5000 })
  })

  test('9. 入库结果页展示已匹配记录和未匹配项', async ({ page }) => {
    await page.addInitScript(() => sessionStorage.clear())
    await mockScopes(page)
    await page.route('**/api/kb/import_zip', async route => {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(MOCK_ZIP_REPORT) })
    })

    await openZipPage(page)
    await uploadTestZip(page)
    await expect(page.getByText('入库完成')).toBeVisible({ timeout: 10000 })

    // Check result tabs
    await expect(page.getByText('已匹配记录')).toBeVisible()
    await expect(page.getByText('未匹配项')).toBeVisible()
    await expect(page.getByText('批次日志')).toBeVisible()

    // Check matched record
    await expect(page.getByText('TEST-181200A001')).toBeVisible()
    await expect(page.getByText('已导入')).toBeVisible()
    await expect(page.getByText('0010 备料 | 0020 车')).toBeVisible()
  })

  test('10. 入库失败时显示错误状态，不设置解锁标记', async ({ page }) => {
    await page.addInitScript(() => sessionStorage.clear())
    await mockScopes(page)
    await page.route('**/api/kb/import_zip', async route => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: '服务器内部错误：数据库写入失败' }),
      })
    })

    await openZipPage(page)
    await uploadTestZip(page)

    // Should show error
    await expect(page.getByText('入库失败')).toBeVisible({ timeout: 10000 })

    // sessionStorage should NOT be unlocked on error
    const unlocked = await page.evaluate(() => sessionStorage.getItem('zip_unlocked'))
    expect(unlocked).toBeNull()

    await expect(page.getByText('再次上传')).toBeVisible()
  })

  test('11. 删除当前数据库：确认弹窗 → 确认', async ({ page }) => {
    await page.addInitScript(() => sessionStorage.setItem('zip_unlocked', 'true'))
    await mockScopes(page, MOCK_SCOPES_AFTER)
    await mockRecords(page)

    let deleteLibraryCalled = false
    // Mock DELETE on specific scope endpoint
    await page.route('**/api/library/scopes/__new_test_lib', async route => {
      if (route.request().method() === 'DELETE') {
        deleteLibraryCalled = true
        await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ ok: true }) })
      }
    })

    await openDbPage(page)
    await expect(page.getByText('记录列表')).toBeVisible()

    // "删除当前数据库" button — it's disabled for public libraries but our scope is private
    await page.getByRole('button', { name: '删除当前数据库' }).click()

    // Confirmation modal — heading + button both contain the text, use .first()
    await expect(page.getByRole('heading', { name: '确认删除当前数据库' })).toBeVisible()

    // Confirm
    await page.getByRole('button', { name: '确认删除当前数据库' }).click()

    // Give it a moment for the async handler to fire
    await page.waitForTimeout(500)
    expect(deleteLibraryCalled).toBe(true)
  })
})

test.describe('边界情况', () => {

  test('空数据库时显示"暂无记录"', async ({ page }) => {
    await page.addInitScript(() => sessionStorage.setItem('zip_unlocked', 'true'))
    await mockScopes(page, MOCK_SCOPES_AFTER)
    await mockRecords(page, { ...MOCK_RECORDS_RES, items: [], total: 0, product_types: [] })

    await openDbPage(page)

    await expect(page.getByText('暂无记录')).toBeVisible()
    await expect(page.getByText('调整筛选条件或先完成工艺入库')).toBeVisible()
  })

  test('只读模式（can_browse_db=false）显示 banner', async ({ page }) => {
    await page.addInitScript(() => sessionStorage.setItem('zip_unlocked', 'true'))
    await mockScopes(page, { ...MOCK_SCOPES_AFTER, can_browse_db: false })
    await mockRecords(page)

    await openDbPage(page)

    // Read-only banner
    await expect(page.getByText('只读浏览模式')).toBeVisible()
    await expect(page.getByText('TEST-181200A001')).toBeVisible()

    // Click record → detail shows "只读浏览" chip
    await page.locator('text=TEST-181200A001').first().click()

    // Use exact match to avoid the banner text
    await expect(page.getByText('只读浏览', { exact: true })).toBeVisible()
  })

  test('scopes API 失败时显示锁屏（ready=false）', async ({ page }) => {
    // Must set zip_unlocked to bypass LockShell and reach the ready=false state
    await page.addInitScript(() => sessionStorage.setItem('zip_unlocked', 'true'))
    await page.route('**/api/library/scopes', async route => {
      await route.abort('failed')
    })

    await openDbPage(page)

    // When ready === false, DbPage shows the fallback lock screen
    await expect(page.getByText('请先完成知识入库')).toBeVisible()
  })
})
