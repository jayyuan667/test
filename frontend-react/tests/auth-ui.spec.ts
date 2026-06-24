import { test, expect } from '@playwright/test'

test.describe('auth ui redesign', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/auth/me', async route => {
      await route.fulfill({
        contentType: 'application/json',
        status: 401,
        body: JSON.stringify({ error: '未登录' }),
      })
    })
  })

  test('shows login screen with auth stage and form panel', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByRole('heading', { name: '欢迎登录' })).toBeVisible()
    await expect(page.getByText('二维工艺系统')).toBeVisible()
    await expect(page.getByText('图纸解析与工艺编制控制台')).toBeVisible()
    await expect(page.getByTestId('auth-visual-stage')).toBeVisible()
    await expect(page.getByLabel('用户名')).toBeVisible()
    await expect(page.getByLabel('密码')).toBeVisible()
  })

  test('switches from login to register without losing themed shell', async ({ page }) => {
    await page.goto('/')

    await page.getByRole('button', { name: '立即注册' }).click()

    await expect(page.getByRole('heading', { name: '创建账号' })).toBeVisible()
    await expect(page.getByTestId('auth-visual-stage')).toBeVisible()
    await expect(page.getByLabel('确认密码')).toBeVisible()
  })

  test('keeps form as priority on narrow screens', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/')

    const submit = page.getByRole('button', { name: '登录' })
    await expect(submit).toBeVisible()
    await expect(page.getByLabel('用户名')).toBeVisible()
    await expect(page.getByTestId('auth-visual-stage')).toBeVisible()
  })
})
