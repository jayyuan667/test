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
    await expect(page.locator('.auth-kicker')).toHaveText('二维工艺系统')
    await expect(page.getByText('图纸解析与工艺编制控制台')).toBeVisible()
    await expect(page.getByText('进入图纸检视台，继续你的工艺流程。')).toBeVisible()
    await expect(page.getByTestId('auth-visual-stage')).toBeVisible()
    await expect(page.locator('.auth-grid')).toBeVisible()
    await expect(page.getByLabel('用户名', { exact: true })).toBeVisible()
    await expect(page.getByLabel('密码', { exact: true })).toBeVisible()
  })

  test('switches from login to register form', async ({ page }) => {
    await page.goto('/')

    await page.getByRole('button', { name: '立即注册' }).click()

    await expect(page.getByRole('heading', { name: '创建账号' })).toBeVisible()
    await expect(page.getByText('注册后可申请企业授权并继续工艺入库与生成流程。')).toBeVisible()
    await expect(page.locator('.auth-shell')).toBeVisible()
    await expect(page.getByLabel('确认密码')).toBeVisible()
  })

  test('keeps form as priority on narrow screens', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/')

    const submit = page.getByRole('button', { name: '登录' })
    const stage = page.getByTestId('auth-visual-stage')
    const username = page.getByLabel('用户名')

    await expect(submit).toBeVisible()
    await expect(username).toBeVisible()
    await expect(stage).toBeVisible()

    const layout = await page.evaluate(() => {
      const readRect = (selector: string) => {
        const element = document.querySelector(selector)
        if (!element) {
          return null
        }

        const rect = element.getBoundingClientRect()
        return {
          top: rect.top,
          bottom: rect.bottom,
          height: rect.height,
        }
      }

      return {
        stage: readRect('[data-testid="auth-visual-stage"]'),
        panel: readRect('.auth-panel'),
        username: readRect('#username'),
        viewportHeight: window.innerHeight,
      }
    })

    expect(layout.stage).not.toBeNull()
    expect(layout.panel).not.toBeNull()
    expect(layout.username).not.toBeNull()

    expect(layout.stage!.height).toBeLessThan(180)
    expect(layout.stage!.bottom).toBeLessThan(layout.viewportHeight * 0.34)
    expect(layout.panel!.top).toBeLessThan(layout.viewportHeight * 0.46)
    expect(layout.username!.top).toBeLessThan(layout.viewportHeight * 0.66)
  })
})
