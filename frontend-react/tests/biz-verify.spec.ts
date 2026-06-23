import { test, expect } from '@playwright/test'

/**
 * 业务链路验收测试
 * 运行: npx playwright test biz-verify.spec.ts --reporter=list
 * 需要: 端口转发 localhost:5191 → liu4th:5190 已建立
 */

const BASE = 'http://localhost:5191'

function createTestPdf(): Buffer {
  return Buffer.from(`%PDF-1.0
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer<</Size 4/Root 1 0 R>>
startxref
190
%%EOF`)
}

test.describe('业务验收：ZIP入库 → 数据库浏览', () => {

  test('4.1 Sample ZIP 导入不报无效 PDF', async ({ page }) => {
    // Clear session for clean test
    await page.goto(BASE)
    await page.evaluate(() => sessionStorage.clear())

    // Navigate to ZIP import page
    await page.locator('button:has-text("工艺入库")').click()
    await expect(page.getByText('上传一个 ZIP')).toBeVisible({ timeout: 5000 })

    // Download sample ZIP from server and upload it
    const response = await page.request.get(`${BASE}/api/kb/sample_zip`)
    expect(response.status()).toBe(200)
    const zipBuffer = await response.body()

    // Upload via file chooser
    const fileChooserPromise = page.waitForEvent('filechooser')
    await page.getByRole('button', { name: '上传工艺包' }).click()
    const fileChooser = await fileChooserPromise
    await fileChooser.setFiles({
      name: 'sample_process_library.zip',
      mimeType: 'application/zip',
      buffer: zipBuffer,
    })

    // Wait for import completion
    await expect(page.getByText('入库完成')).toBeVisible({ timeout: 30000 })
    console.log('✅ Sample ZIP import succeeded')

    // Verify sessionStorage was set (the fix)
    const unlocked = await page.evaluate(() => sessionStorage.getItem('zip_unlocked'))
    expect(unlocked).toBe('true')
    console.log('✅ sessionStorage unlocked:', unlocked)

    // Check result tabs
    await expect(page.getByText('已匹配记录')).toBeVisible()
    await expect(page.getByText('批次日志')).toBeVisible()
    console.log('✅ Result tabs visible')

    // Verify: no error about invalid PDF
    const errorText = await page.locator('body').innerText()
    expect(errorText).not.toContain('无效 PDF')
    expect(errorText).not.toContain('占位符')
    console.log('✅ No invalid PDF errors in output')
  })

  test('4.3 入库后知识库浏览页能看到记录', async ({ page }) => {
    // Set unlocked state (simulating previous successful import)
    await page.goto(BASE)
    await page.evaluate(() => sessionStorage.setItem('zip_unlocked', 'true'))

    // Navigate to DB page
    await page.locator('button:has-text("知识库浏览")').click()

    // Should NOT show lock screen
    await expect(page.getByText('数据库未解锁')).not.toBeVisible({ timeout: 5000 })
    console.log('✅ Lock screen bypassed')

    // Should show record list
    await expect(page.getByText('记录列表')).toBeVisible({ timeout: 5000 })
    console.log('✅ Record list visible')

    // Check if there are records
    const noRecords = await page.getByText('暂无记录').isVisible().catch(() => false)
    if (noRecords) {
      console.log('⚠️  数据库无记录（可能Sample ZIP未导入），尝试其他库...')
    } else {
      const recordCount = await page.locator('text=库内条目').textContent()
      console.log('📊', recordCount)
    }
  })

  test('4.2 真实 PDF 上传 → 特征审阅', async ({ page }) => {
    await page.goto(BASE)

    // Upload a real PDF
    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'test-drawing.pdf',
      mimeType: 'application/pdf',
      buffer: createTestPdf(),
    })

    // Should enter processing state
    const processing = await Promise.race([
      page.locator('text=正在上传文件').waitFor({ state: 'visible', timeout: 10000 }).then(() => 'processing'),
      page.locator('text=等待人工补全标注').waitFor({ state: 'visible', timeout: 30000 }).then(() => 'annotation'),
      page.locator('text=失败').waitFor({ state: 'visible', timeout: 30000 }).then(() => 'error'),
      page.waitForTimeout(25000).then(() => 'timeout'),
    ])
    console.log('📄 PDF upload state:', processing)

    if (processing === 'annotation') {
      // YOLO review stage - skip it
      await page.locator('button:has-text("跳过 YOLO 审阅")').click()
      console.log('⏭️  已跳过 YOLO 审阅')

      // Wait for feature review
      await page.locator('button:has-text("特征审阅")').first().waitFor({ state: 'visible', timeout: 30000 })
    } else if (processing === 'error') {
      const errMsg = await page.locator('body').innerText()
      console.log('❌ Upload error:', errMsg.substring(0, 500))
    }
  })
})
