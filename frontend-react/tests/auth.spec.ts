import { test, expect } from '@playwright/test'

const ADMIN = { username: 'admin', password: 'admin123' }

async function loginAs(page: any, username: string, password: string) {
  await page.goto('/')
  await page.getByRole('button', { name: '进入系统' }).click()
  await page.getByLabel('用户名').fill(username)
  await page.locator('#password').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
}

test.describe('auth pages', () => {
  test('login page renders', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'DiMo' })).toBeVisible()
    await expect(page.getByRole('button', { name: '进入系统' })).toBeVisible()
    await expect(page.getByLabel('用户名')).not.toBeVisible()
  })

  test('register page renders', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: '进入系统' }).click()
    await page.getByText('立即注册').click()
    await expect(page.getByText('创建账号')).toBeVisible()
    await expect(page.locator('#reg-confirm-password')).toBeVisible()
    await expect(page.getByRole('button', { name: '注册' })).toBeVisible()
  })

  test('login rejects bad credentials', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: '进入系统' }).click()
    await page.getByLabel('用户名').fill('no_such_user_xyz')
    await page.locator('#password').fill('badpass')
    await page.getByRole('button', { name: '登录' }).click()
    // Should still be on login page (not redirected to main app)
    await expect(page.locator('#password')).toBeVisible({ timeout: 10000 })
    await expect(page.getByText('工艺生成')).not.toBeVisible()
  })

  test('admin can login and see main app', async ({ page }) => {
    await loginAs(page, ADMIN.username, ADMIN.password)
    await expect(page.getByText('工艺生成')).toBeVisible({ timeout: 10000 })
  })

  test('register new account redirects to login', async ({ page }) => {
    const testUser = `e2e_${Date.now()}`
    await page.goto('/')
    await page.getByRole('button', { name: '进入系统' }).click()
    await page.getByText('立即注册').click()
    await page.getByLabel('用户名').fill(testUser)
    await page.locator('#reg-password').fill('test123456')
    await page.locator('#reg-confirm-password').fill('test123456')
    await page.getByRole('button', { name: '注册' }).click()
    // After registration, should be on login page
    await expect(page.locator('#password')).toBeVisible({ timeout: 10000 })
  })
})

test.describe('authenticated flows', () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, ADMIN.username, ADMIN.password)
    await expect(page.getByText('工艺生成')).toBeVisible({ timeout: 10000 })
  })

  test('profile page loads', async ({ page }) => {
    // Profile link in sidebar navigation
    await page.click('button:has-text("个人中心")')
    await expect(page.getByRole('heading', { name: '修改密码' })).toBeVisible({ timeout: 10000 })
  })

  test('admin page shows tabs', async ({ page }) => {
    await page.locator('button').filter({ hasText: '管理后台' }).first().click()
    await expect(page.getByText('用户管理')).toBeVisible({ timeout: 8000 })
  })

  test('admin quotas tab loads', async ({ page }) => {
    await page.locator('button').filter({ hasText: '管理后台' }).first().click()
    // Wait for admin page to load
    await expect(page.getByText('配额概览')).toBeVisible({ timeout: 8000 })
    await page.getByText('配额概览').click()
    // Quota tab shows user listing
    await expect(page.locator('table')).toBeVisible({ timeout: 8000 })
  })

  test('logout returns to login', async ({ page }) => {
    await page.getByText('退出登录').click()
    await expect(page.getByRole('button', { name: '进入系统' })).toBeVisible({ timeout: 8000 })
  })
})

test.describe('unauthenticated', () => {
  test('shows login page not main app', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('button', { name: '进入系统' })).toBeVisible()
    await expect(page.getByText('工艺生成')).not.toBeVisible()
  })
})
