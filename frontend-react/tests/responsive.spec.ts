import { test, expect } from '@playwright/test'

const BASE = 'http://localhost:3200'

// 8 key viewports covering phone 鈫?2K desktop
const VIEWPORTS = [
  { w: 375,  h: 667,  name: 'iPhone_SE' },
  { w: 390,  h: 844,  name: 'iPhone_14' },
  { w: 768,  h: 1024, name: 'iPad_Portrait' },
  { w: 1024, h: 768,  name: 'iPad_Landscape' },
  { w: 1280, h: 800,  name: 'Laptop_1280' },
  { w: 1366, h: 768,  name: 'Laptop_HD' },
  { w: 1920, h: 1080, name: 'Desktop_FHD' },
  { w: 2560, h: 1440, name: 'Desktop_2K' },
]

// Navigate by clicking sidebar nav buttons (they contain title text in nested divs)
async function goToPage(page: import('@playwright/test').Page, titleText: string) {
  // Use getByRole to find button whose accessible name includes the text
  const btn = page.getByRole('button', { name: titleText })
  await btn.click()
  await page.waitForTimeout(600)
}

// Measure horizontal overflow
async function hasOverflow(page: import('@playwright/test').Page) {
  return page.evaluate(() => {
    const doc = document.documentElement
    return doc.scrollWidth > doc.clientWidth + 1
  })
}

// 鈹€鈹€ Main test suite 鈹€鈹€

test.describe('Horizontal Overflow - GeneratePage', () => {
  for (const vp of VIEWPORTS) {
    test(`${vp.name} (${vp.w}脳${vp.h})`, async ({ page }) => {
      await page.setViewportSize({ width: vp.w, height: vp.h })
      await page.goto(BASE)
      await page.waitForTimeout(800)
      const overflow = await hasOverflow(page)
      expect(overflow, `Overflow at ${vp.w}px`).toBe(false)
    })
  }
})

test.describe('Horizontal Overflow - ZipPage', () => {
  for (const vp of VIEWPORTS) {
    test(`${vp.name} (${vp.w}脳${vp.h})`, async ({ page }) => {
      await page.setViewportSize({ width: vp.w, height: vp.h })
      await page.goto(BASE)
      await page.waitForTimeout(300)
      await goToPage(page, '宸ヨ壓鍏ュ簱')
      const overflow = await hasOverflow(page)
      expect(overflow, `Overflow at ${vp.w}px`).toBe(false)
    })
  }
})

test.describe('Horizontal Overflow - HistoryPage', () => {
  for (const vp of VIEWPORTS) {
    test(`${vp.name} (${vp.w}脳${vp.h})`, async ({ page }) => {
      await page.setViewportSize({ width: vp.w, height: vp.h })
      await page.goto(BASE)
      await page.waitForTimeout(300)
      await goToPage(page, '鍘嗗彶璁板綍')
      const overflow = await hasOverflow(page)
      expect(overflow, `Overflow at ${vp.w}px`).toBe(false)
    })
  }
})

test.describe('Horizontal Overflow - DbPage', () => {
  for (const vp of VIEWPORTS) {
    test(`${vp.name} (${vp.w}脳${vp.h})`, async ({ page }) => {
      await page.setViewportSize({ width: vp.w, height: vp.h })
      await page.goto(BASE)
      await page.waitForTimeout(300)
      await goToPage(page, '鏁版嵁搴撴祻瑙?)
      await page.waitForTimeout(500)
      const overflow = await hasOverflow(page)
      expect(overflow, `Overflow at ${vp.w}px`).toBe(false)
    })
  }
})

// 鈹€鈹€ Sidebar behavior 鈹€鈹€

test.describe('Sidebar Auto-Collapse', () => {
  test('collapses at 800px', async ({ page }) => {
    await page.setViewportSize({ width: 800, height: 600 })
    await page.goto(BASE)
    await page.waitForTimeout(500)
    const sidebar = page.locator('aside').first()
    const box = await sidebar.boundingBox()
    expect(box).toBeTruthy()
    expect(box!.width).toBeLessThanOrEqual(80)
  })

  test('stays expanded at 1920px', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 })
    await page.goto(BASE)
    await page.waitForTimeout(500)
    const sidebar = page.locator('aside').first()
    const box = await sidebar.boundingBox()
    expect(box).toBeTruthy()
    expect(box!.width).toBeGreaterThan(150)
  })
})

// 鈹€鈹€ Content cards visibility 鈹€鈹€

test.describe('Cards Within Viewport', () => {
  for (const vp of VIEWPORTS) {
    test(`${vp.name} - GeneratePage cards`, async ({ page }) => {
      await page.setViewportSize({ width: vp.w, height: vp.h })
      await page.goto(BASE)
      await page.waitForTimeout(600)
      const cards = page.locator('.card-solid')
      const count = await cards.count()
      expect(count).toBeGreaterThanOrEqual(2)
      // First 2 cards must be within viewport
      for (let i = 0; i < 2; i++) {
        const box = await cards.nth(i).boundingBox()
        expect(box, `card[${i}] not found`).toBeTruthy()
        expect(box!.x, `card[${i}] left overflow`).toBeGreaterThanOrEqual(-1)
        expect(box!.x + box!.width, `card[${i}] right overflow`).toBeLessThanOrEqual(vp.w + 2)
      }
    })
  }
})

// 鈹€鈹€ ZipPage toolbar text visibility 鈹€鈹€

test.describe('ZipPage Toolbar Not Clipped', () => {
  for (const vp of VIEWPORTS) {
    test(`${vp.name}`, async ({ page }) => {
      await page.setViewportSize({ width: vp.w, height: vp.h })
      await page.goto(BASE)
      await page.waitForTimeout(300)
      await goToPage(page, '宸ヨ壓鍏ュ簱')
      await page.waitForTimeout(300)

      // "宸ヨ壓鍏ュ簱宸ヤ綔鍙? text should be visible and not clipped
      const toolbarText = page.locator('text=宸ヨ壓鍏ュ簱宸ヤ綔鍙?).first()
      const visible = await toolbarText.isVisible().catch(() => false)
      if (visible) {
        const box = await toolbarText.boundingBox()
        if (box) {
          expect(box.x + box.width, 'toolbar text clipped right').toBeLessThanOrEqual(vp.w + 2)
          expect(box.x, 'toolbar text clipped left').toBeGreaterThanOrEqual(-1)
        }
      }
    })
  }
})


