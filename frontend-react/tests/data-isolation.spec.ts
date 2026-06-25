import { test, expect } from '@playwright/test'
import type { User } from '../src/types/auth'

const ENTERPRISE_A_ADMIN: User = {
  id: 10,
  username: 'ent_admin_a',
  role: 'enterprise_admin',
  enterprise_id: 1,
  enterprise_name: '测试企业A',
  is_active: true,
  created_at: '2026-06-25T00:00:00.000Z',
  grant_expires_at: '2027-06-25T00:00:00.000Z',
  quota: {
    total_granted: 100,
    used: 10,
    remaining: 90,
  },
}

const ENTERPRISE_B_ADMIN: User = {
  id: 20,
  username: 'ent_admin_b',
  role: 'enterprise_admin',
  enterprise_id: 2,
  enterprise_name: '测试企业B',
  is_active: true,
  created_at: '2026-06-25T00:00:00.000Z',
  grant_expires_at: '2027-06-25T00:00:00.000Z',
  quota: {
    total_granted: 100,
    used: 5,
    remaining: 95,
  },
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

async function mockScopesWithEnterpriseScopes(page: import('@playwright/test').Page) {
  await page.route('**/api/library/scopes', async route => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          { library_key: 'public', library_name: '公共工艺库', scope_type: 'public', record_count: 10 },
          { library_key: 'enterprise-a', library_name: '企业A工艺库', scope_type: 'private', record_count: 3 },
        ],
        can_browse_db: true,
      }),
    })
  })
}

test.describe('Data Isolation - Frontend Defaults', () => {

  test('DbPage defaults to private scope not public library', async ({ page }) => {
    // Mock auth: enterprise_admin with enterprise_id=1 (企业A)
    await mockAuthSession(page, ENTERPRISE_A_ADMIN)

    // Mock scopes: public + enterprise A private scope
    await mockScopesWithEnterpriseScopes(page)

    // Unlock DbPage via sessionStorage
    await page.addInitScript(() => {
      sessionStorage.setItem('zip_unlocked', 'true')
    })

    // Navigate to DbPage
    await page.goto('/')
    await expect(page.getByText('工艺生成')).toBeVisible({ timeout: 10000 })
    await page.getByRole('button', { name: /知识库浏览/ }).click()

    // Wait for DbPage to render with scopes
    await expect(page.getByText('记录列表')).toBeVisible({ timeout: 10000 })

    // The first chip in the toolbar shows the current scope label
    // DbPage prefers non-public scope on load, so it should show "个人工艺库"
    const scopeChip = page.locator('.chip').first()
    const text = await scopeChip.textContent()

    // Should NOT say "平台工艺库" (the public label)
    expect(text).not.toContain('平台工艺库')

    // Should default to private scope label
    expect(text).toContain('个人工艺库')
  })

  test('ZipPage new library defaults to empty not seeded from public', async ({ page }) => {
    // Mock auth: enterprise_admin with enterprise_id=1
    await mockAuthSession(page, ENTERPRISE_A_ADMIN)

    // Mock scopes
    await mockScopesWithEnterpriseScopes(page)

    // Navigate to ZipPage
    await page.goto('/')
    await expect(page.getByText('工艺生成')).toBeVisible({ timeout: 10000 })
    await page.getByRole('button', { name: /工艺入库/ }).click()

    // Wait for ZipPage to render
    await expect(page.getByText('上传一个 ZIP')).toBeVisible({ timeout: 10000 })

    // The default selectedScope is '__new__' which shows the new library section
    // Check the "复制公共工艺库基线（推荐）" checkbox is unchecked
    const seedCheckbox = page.locator('label').filter({ hasText: '复制公共工艺库基线' }).locator('input[type="checkbox"]')
    await expect(seedCheckbox).toBeVisible()
    const isChecked = await seedCheckbox.isChecked()
    expect(isChecked).toBe(false)
  })

  test('enterprise A admin cannot see enterprise B history', async ({ page }) => {
    // This test requires the backend isolation to be active and test data seeding
    // Mock: login as enterprise A admin, check history list
    // History entries with enterprise_id != A should not appear
    test.skip();
  })

  test('enterprise A admin cannot browse enterprise B private library', async ({ page }) => {
    // This test requires the backend isolation to be active and test data seeding
    // Mock: login as enterprise A admin, check library scopes
    // enterprise B's private scopes should not appear
    test.skip();
  })
})
