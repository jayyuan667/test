import { expect, test } from '@playwright/test'
import type { User } from '../src/types/auth'

const ENTERPRISE_ADMIN: User = {
  id: 7,
  username: 'enterprise_admin',
  role: 'enterprise_admin',
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

test('enterprise admin can claim an unassigned user from admin console', async ({ page }) => {
  let memberUsers = [
    {
      id: 11,
      username: 'factory_user',
      role: 'user',
      enterprise_id: 3,
      enterprise_name: '华东工厂',
      is_active: true,
      created_at: '2026-06-25T00:00:00.000Z',
      quota_total: 80,
      quota_used: 12,
    },
  ]
  let unassignedUsers = [
    {
      id: 42,
      username: 'new_user',
      role: 'user',
      enterprise_id: null,
      enterprise_name: null,
      is_active: true,
      created_at: '2026-06-25T00:00:00.000Z',
      quota_total: 10,
      quota_used: 0,
    },
  ]

  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url())
    if (!url.pathname.startsWith('/api/')) {
      await route.fallback()
      return
    }

    if (url.pathname.endsWith('/api/auth/me')) {
      await route.fulfill({
        contentType: 'application/json',
        status: 200,
        body: JSON.stringify({ success: true, data: { user: ENTERPRISE_ADMIN } }),
      })
      return
    }

    if (url.pathname.endsWith('/api/admin/users') && route.request().method() === 'GET') {
      const users = url.searchParams.get('scope') === 'unassigned' ? unassignedUsers : memberUsers
      await route.fulfill({
        contentType: 'application/json',
        status: 200,
        body: JSON.stringify({ success: true, data: { users } }),
      })
      return
    }

    if (/\/api\/admin\/users\/\d+$/.test(url.pathname) && route.request().method() === 'PUT') {
      const payload = route.request().postDataJSON() as { enterprise_id?: number }
      const targetId = Number(url.pathname.split('/').pop())
      const claimedUser = unassignedUsers.find(user => user.id === targetId)

      if (claimedUser && payload.enterprise_id === ENTERPRISE_ADMIN.enterprise_id) {
        unassignedUsers = unassignedUsers.filter(user => user.id !== targetId)
        const updatedUser = {
          ...claimedUser,
          enterprise_id: ENTERPRISE_ADMIN.enterprise_id,
          enterprise_name: ENTERPRISE_ADMIN.enterprise_name,
        }
        memberUsers = [...memberUsers, updatedUser]
        await route.fulfill({
          contentType: 'application/json',
          status: 200,
          body: JSON.stringify({ success: true, data: { user: updatedUser } }),
        })
        return
      }

      await route.fulfill({
        contentType: 'application/json',
        status: 403,
        body: JSON.stringify({ success: false, error: { code: 'FORBIDDEN', message: '只能分配未分配用户到本企业' } }),
      })
      return
    }

    if (url.pathname.endsWith('/api/admin/quotas')) {
      await route.fulfill({
        contentType: 'application/json',
        status: 200,
        body: JSON.stringify({ success: true, data: { quotas: [] } }),
      })
      return
    }

    await route.fulfill({
      contentType: 'application/json',
      status: 200,
      body: JSON.stringify({ success: true, data: {} }),
    })
  })

  await page.goto('/')
  await page.locator('button').filter({ hasText: '管理后台' }).first().click()

  await expect(page.getByRole('button', { name: '未分配用户' })).toBeVisible()
  await page.getByRole('button', { name: '未分配用户' }).click()

  await expect(page.getByText('new_user')).toBeVisible()
  await page.getByRole('button', { name: '分配到本企业' }).click()

  await expect(page.getByText('new_user')).not.toBeVisible()
  await expect(page.getByText('暂无用户')).toBeVisible()
})
