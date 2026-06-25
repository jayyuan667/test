import { test, expect } from '@playwright/test'

const UNASSIGNED_USER = {
  id: 42,
  username: 'unassigned_user',
  role: 'user' as const,
  enterprise_id: null,
  enterprise_name: null,
  is_active: true,
  created_at: '2026-06-25T00:00:00.000Z',
  grant_expires_at: null,
  quota: {
    total_granted: 10,
    used: 0,
    remaining: 10,
  },
}

const ENTERPRISE_ADMIN_USER = {
  id: 7,
  username: 'enterprise_admin',
  role: 'enterprise_admin' as const,
  enterprise_id: 3,
  enterprise_name: '华东工厂',
  is_active: true,
  created_at: '2026-06-25T00:00:00.000Z',
  grant_expires_at: '2027-06-25T00:00:00.000Z',
  quota: {
    total_granted: 120,
    used: 30,
    remaining: 90,
  },
}

const SUPER_ADMIN_USER = {
  id: 1,
  username: 'admin',
  role: 'super_admin' as const,
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

async function mockAuthSession(page: import('@playwright/test').Page, user: typeof UNASSIGNED_USER) {
  await page.route('**/api/auth/me', async route => {
    await route.fulfill({
      contentType: 'application/json',
      status: 200,
      body: JSON.stringify({ success: true, data: { user } }),
    })
  })
}

async function mockAdminApis(page: import('@playwright/test').Page) {
  await page.route('**/api/admin/users**', async route => {
    await route.fulfill({
      contentType: 'application/json',
      status: 200,
      body: JSON.stringify({
        success: true,
        data: {
          users: [
            {
              id: 11,
              username: 'factory_user',
              role: 'user',
              enterprise_id: 3,
              enterprise_name: '华东工厂',
              is_active: true,
              created_at: '2026-06-25T00:00:00.000Z',
              grant_expires_at: null,
              quota_total: 80,
              quota_used: 12,
            },
          ],
        },
      }),
    })
  })

  await page.route('**/api/admin/quotas', async route => {
    await route.fulfill({
      contentType: 'application/json',
      status: 200,
      body: JSON.stringify({
        success: true,
        data: {
          quotas: [
            {
              user_id: 11,
              username: 'factory_user',
              role: 'user',
              total_granted: 80,
              used: 12,
              remaining: 68,
            },
          ],
        },
      }),
    })
  })

  await page.route('**/api/admin/enterprises', async route => {
    await route.fulfill({
      contentType: 'application/json',
      status: 200,
      body: JSON.stringify({
        success: true,
        data: {
          enterprises: [
            {
              id: 3,
              name: '华东工厂',
              is_active: true,
              created_at: '2026-06-25T00:00:00.000Z',
              user_count: 8,
            },
          ],
        },
      }),
    })
  })
}

async function openAdminConsole(page: import('@playwright/test').Page) {
  await page.goto('/')
  await page.locator('button').filter({ hasText: '管理后台' }).first().click()
}

test.describe('auth entry scene', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/auth/me', async route => {
      await route.fulfill({
        contentType: 'application/json',
        status: 401,
        body: JSON.stringify({ error: '未登录' }),
      })
    })
  })

  test('starts in minimal home state before auth is opened', async ({ page }) => {
    await page.goto('/')

    const title = page.getByRole('heading', { name: '2D i' })
    await expect(title).toBeVisible()
    await expect(title).toHaveCSS('color', 'rgb(5, 5, 5)')
    await expect(page.getByRole('button', { name: '进入系统' })).toBeVisible()
    await expect(page.getByText('聚焦当前图纸，进入工艺编制与检视控制台。')).toBeVisible()
    await expect(page.getByLabel('用户名')).not.toBeVisible()
    await expect(page.getByRole('heading', { name: '欢迎登录' })).not.toBeVisible()
  })

  test('opens auth surface when enter button is clicked', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: '进入系统' }).click()

    await expect(page.getByRole('heading', { name: '欢迎登录' })).toBeVisible()
    await expect(page.getByLabel('用户名')).toBeVisible()
    await expect(page.locator('#password')).toBeVisible()
    await expect(page.getByRole('button', { name: '返回首页' })).toBeVisible()
  })

  test('switches from login to register inside auth surface', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: '进入系统' }).click()
    await page.getByRole('button', { name: '立即注册' }).click()

    await expect(page.getByRole('heading', { name: '创建账号' })).toBeVisible()
    await expect(page.getByLabel('确认密码')).toBeVisible()
    await expect(page.getByRole('button', { name: '返回首页' })).toBeVisible()
  })

  test('returns to home state after closing auth surface', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: '进入系统' }).click()
    await page.getByRole('button', { name: '返回首页' }).click()

    await expect(page.getByRole('heading', { name: '2D i' })).toBeVisible()
    await expect(page.getByText('聚焦当前图纸，进入工艺编制与检视控制台。')).toBeVisible()
    await expect(page.getByLabel('用户名')).not.toBeVisible()
  })

  test('reveals and moves the title blob with pointer hover', async ({ page }) => {
    await page.goto('/')

    const before = await page.locator('.auth-entry-cursor-blob').evaluate(element => {
      const styles = getComputedStyle(element)
      return {
        opacity: styles.opacity,
        transform: styles.transform,
      }
    })

    await page.locator('.auth-entry-copy').hover({
      position: { x: 220, y: 90 },
    })
    await page.waitForTimeout(350)

    const after = await page.locator('.auth-entry-cursor-blob').evaluate(element => {
      const styles = getComputedStyle(element)
      return {
        opacity: styles.opacity,
        transform: styles.transform,
      }
    })

    expect(Number(before.opacity)).toBeLessThan(0.05)
    expect(Number(after.opacity)).toBeGreaterThan(0.8)
    expect(after.transform).not.toBe(before.transform)
  })
})

test.describe('authenticated shell guards', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/auth/me', async route => {
      await route.fulfill({
        contentType: 'application/json',
        status: 200,
        body: JSON.stringify({ success: true, data: { user: UNASSIGNED_USER } }),
      })
    })
  })

  test('unassigned user only gets profile and limited entry states', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByRole('heading', { name: '修改密码' })).toBeVisible()
    await expect(page.getByText('个人中心')).toBeVisible()
    await expect(page.getByText('未分配企业')).toBeVisible()
    await expect(page.getByText('工艺生成')).not.toBeVisible()
    await expect(page.getByText('工艺入库')).not.toBeVisible()
    await expect(page.getByText('历史记录')).not.toBeVisible()
    await expect(page.getByText('知识库浏览')).not.toBeVisible()
    await expect(page.getByText('管理后台')).not.toBeVisible()
    await expect(page.getByText('上传 2D 工艺图纸')).toHaveCount(0)
  })
})

test.describe('admin console role wording', () => {
  test('enterprise admin sees enterprise console wording only', async ({ page }) => {
    await mockAuthSession(page, ENTERPRISE_ADMIN_USER)
    await mockAdminApis(page)

    await openAdminConsole(page)

    await expect(page.getByRole('heading', { name: '企业运营台' })).toBeVisible()
    await expect(page.getByText('管理本企业成员、配额与授权状态。')).toBeVisible()
    await expect(page.getByRole('tab', { name: '用户管理' })).toBeVisible()
    await expect(page.getByRole('tab', { name: '配额概览' })).toBeVisible()
    await expect(page.getByRole('tab', { name: '企业管理' })).toHaveCount(0)
    await expect(page.getByText('成员列表')).toBeVisible()
    await expect(page.getByText('平台管理')).toHaveCount(0)
    await expect(page.getByText('全部企业')).toHaveCount(0)
    await expect(page.getByText('跨企业治理')).toHaveCount(0)
  })

  test('super admin sees enterprise governance tab', async ({ page }) => {
    await mockAuthSession(page, SUPER_ADMIN_USER)
    await mockAdminApis(page)

    await openAdminConsole(page)

    await expect(page.getByRole('heading', { name: '平台管理' })).toBeVisible()
    await expect(page.getByText('管理企业、用户与平台配额。')).toBeVisible()
    await expect(page.getByRole('tab', { name: '企业管理' })).toBeVisible()
    await page.getByRole('tab', { name: '配额概览' }).click()
    await expect(page.getByText('平台配额概览')).toBeVisible()
  })
})
