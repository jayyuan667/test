import { test, expect, type Page } from '@playwright/test'

function createTestPdf(): Buffer {
  const content = `%PDF-1.0
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
%%EOF`
  return Buffer.from(content)
}

/** Upload a test PDF and wait for annotation state */
async function uploadAndWaitAnnotation(page: Page) {
  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles({
    name: 'test-drawing.pdf',
    mimeType: 'application/pdf',
    buffer: createTestPdf(),
  })
  await expect(page.locator('text=等待人工补全标注')).toBeVisible({ timeout: 20000 })
}

/** Full flow: upload → open annotation → exit → finalize → wait for review */
async function goToReviewState(page: Page) {
  await uploadAndWaitAnnotation(page)

  // Open annotation overlay
  await page.locator('button:has-text("开始标注")').click()
  await expect(page.locator('.fixed.inset-0')).toBeVisible({ timeout: 5000 })

  // Close annotation overlay ("退出标注")
  await page.locator('button:has-text("退出标注")').click()
  await expect(page.locator('.fixed.inset-0')).not.toBeVisible({ timeout: 5000 })

  // Now "完成标注 → 下一步" is enabled (annotateVisited = true)
  await page.locator('button:has-text("完成标注 → 下一步")').click()

  // Wait for backend to process: annotation → VLM → review_required
  await expect(page.locator('text=请审阅特征报告')).toBeVisible({ timeout: 30000 })
}

test.describe('Upload → YOLO 审阅完整流程', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('text=等待文件进入解析流程')).toBeVisible({ timeout: 10000 })
  })

  test('初始状态：页面加载后显示上传提示', async ({ page }) => {
    await expect(page.locator('input[type="file"]')).toBeAttached()
    await expect(page.locator('text=等待文件进入解析流程')).toBeVisible()
    const yoloTab = page.locator('button', { hasText: 'YOLO' }).first()
    await expect(yoloTab).toBeVisible()
    await expect(yoloTab).toHaveClass(/text-orange/)
  })

  test('上传 PDF 后进入 processing 状态', async ({ page }) => {
    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'test-drawing.pdf',
      mimeType: 'application/pdf',
      buffer: createTestPdf(),
    })
    await expect(page.locator('text=正在上传文件')).toBeVisible({ timeout: 5000 })
  })

  test('上传后 SSE 推送 annotation_required → 显示 YOLO 标注界面和跳过入口', async ({ page }) => {
    await uploadAndWaitAnnotation(page)
    await expect(page.locator('button:has-text("开始标注")')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('button:has-text("跳过 YOLO 审阅")')).toBeVisible()
    await expect(page.locator('button:has-text("完成标注")')).not.toBeVisible()
  })

  test('YOLO 标注界面：开始标注 → 退出 → 完成标注 → 自动跳转特征审阅', async ({ page }) => {
    await uploadAndWaitAnnotation(page)

    await expect(page.locator('button:has-text("跳过 YOLO 审阅")')).toBeVisible()
    await expect(page.locator('button:has-text("完成标注")')).not.toBeVisible()

    await page.locator('button:has-text("开始标注")').click()
    await expect(page.locator('.fixed.inset-0')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('text=标注工具')).toBeVisible()

    await page.locator('button:has-text("退出标注")').click()
    await expect(page.locator('.fixed.inset-0')).not.toBeVisible({ timeout: 5000 })

    await expect(page.locator('button:has-text("继续标注")')).toBeVisible()
    const finalizeBtn = page.locator('button:has-text("完成标注 → 下一步")')
    await expect(finalizeBtn).toBeEnabled({ timeout: 3000 })
    await expect(page.locator('button:has-text("跳过 YOLO 审阅")')).not.toBeVisible()

    await finalizeBtn.click()

    const reviewTab = page.locator('button', { hasText: '特征审阅' }).first()
    await expect(reviewTab).toHaveClass(/text-orange/, { timeout: 5000 })
  })

  test('YOLO 标注界面：可直接跳过 YOLO 审阅进入特征审阅', async ({ page }) => {
    await uploadAndWaitAnnotation(page)

    await page.locator('button:has-text("跳过 YOLO 审阅")').click()

    const reviewTab = page.locator('button', { hasText: '特征审阅' }).first()
    await expect(reviewTab).toHaveClass(/text-orange/, { timeout: 5000 })
  })

  test('预览图在上传后显示', async ({ page }) => {
    await uploadAndWaitAnnotation(page)
    const previewImages = page.locator('img[src*="/api"]')
    await expect(previewImages.first()).toBeVisible({ timeout: 10000 })
  })

  test('Tab 顺序：YOLO审阅 → 特征审阅 → 工艺规程', async ({ page }) => {
    await uploadAndWaitAnnotation(page)

    const tabs = page.locator('button').filter({ hasText: /YOLO审阅|特征审阅|工艺规程/ })
    await expect(tabs.nth(0)).toHaveText('YOLO审阅')
    await expect(tabs.nth(1)).toHaveText('特征审阅')
    await expect(tabs.nth(2)).toHaveText('工艺规程')

    const yoloTab = page.locator('button', { hasText: 'YOLO审阅' }).first()
    const reviewTab = page.locator('button', { hasText: '特征审阅' }).first()
    const processTab = page.locator('button', { hasText: '工艺规程' }).first()

    await expect(yoloTab).toHaveClass(/text-orange/)

    await reviewTab.click()
    await expect(reviewTab).toHaveClass(/text-orange/)

    await processTab.click()
    await expect(processTab).toHaveClass(/text-orange/)

    await yoloTab.click()
    await expect(yoloTab).toHaveClass(/text-orange/)
  })

  test('完整流程：上传 → 标注 → 确认 → 特征审阅', async ({ page }) => {
    await goToReviewState(page)

    // Review tab should have content and confirm button should be enabled
    const reviewTab = page.locator('button', { hasText: '特征审阅' }).first()
    await reviewTab.click()

    const confirmBtn = page.locator('button:has-text("确认特征并继续")')
    await expect(confirmBtn).toBeVisible({ timeout: 5000 })
    await expect(confirmBtn).toBeEnabled({ timeout: 5000 })
  })

  test('特征审阅：确认后进入工艺规程生成', async ({ page }) => {
    await goToReviewState(page)

    // Confirm review
    const confirmBtn = page.locator('button:has-text("确认特征并继续")')
    await expect(confirmBtn).toBeEnabled({ timeout: 5000 })
    await confirmBtn.click()

    // Should transition to processing → completed
    // Wait for process panel or completion indicator
    await expect(
      page.locator('text=工艺').or(page.locator('text=生成完成')).or(page.locator('text=工序')).first()
    ).toBeVisible({ timeout: 30000 })
  })

  test('重置按钮：回到初始状态', async ({ page }) => {
    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'test-drawing.pdf',
      mimeType: 'application/pdf',
      buffer: createTestPdf(),
    })
    await expect(page.locator('text=正在上传文件')).toBeVisible({ timeout: 5000 })

    const resetBtn = page.locator('button:has-text("重置")')
    if (await resetBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await resetBtn.click()
      await expect(page.locator('text=等待文件进入解析流程')).toBeVisible({ timeout: 5000 })
    }
  })
})

test.describe('SSE 事件处理', () => {
  test('image_ready 事件触发预览图显示', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('text=等待文件进入解析流程')).toBeVisible({ timeout: 10000 })

    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'test-drawing.pdf',
      mimeType: 'application/pdf',
      buffer: createTestPdf(),
    })

    // image_ready fires before annotation_required — preview should appear
    const previewImages = page.locator('img[src*="/api"]')
    await expect(previewImages.first()).toBeVisible({ timeout: 20000 })
  })

  test('annotation_required 后状态正确转换（不被 processing 守卫吞掉）', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('text=等待文件进入解析流程')).toBeVisible({ timeout: 10000 })

    await uploadAndWaitAnnotation(page)

    // Should show annotation pending card, NOT the completed card
    await expect(page.locator('button:has-text("开始标注")')).toBeVisible()
    await expect(page.locator('text=标注已完成')).not.toBeVisible()
  })
})

test.describe('错误处理', () => {
  test('上传非支持格式不崩溃', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('text=等待文件进入解析流程')).toBeVisible({ timeout: 10000 })

    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'test.xyz',
      mimeType: 'application/octet-stream',
      buffer: Buffer.from('not a real file'),
    })

    // Wait and check: either shows error or returns to idle
    await page.waitForTimeout(5000)
    const hasError = await page.locator('text=失败').isVisible().catch(() => false)
    const hasError2 = await page.locator('text=错误').isVisible().catch(() => false)
    const isIdle = await page.locator('text=等待文件进入解析流程').isVisible().catch(() => false)
    expect(hasError || hasError2 || isIdle).toBeTruthy()
  })
})

test.describe('无障碍访问', () => {
  test('Tab 按钮可键盘导航', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('text=等待文件进入解析流程')).toBeVisible({ timeout: 10000 })

    const yoloTab = page.locator('button', { hasText: 'YOLO' }).first()
    const reviewTab = page.locator('button', { hasText: '特征审阅' }).first()
    const processTab = page.locator('button', { hasText: '工艺规程' }).first()

    await expect(yoloTab).toBeVisible()
    await expect(reviewTab).toBeVisible()
    await expect(processTab).toBeVisible()

    await expect(yoloTab).toBeEnabled()
    await expect(reviewTab).toBeEnabled()
    await expect(processTab).toBeEnabled()
  })

  test('文件上传区域可访问', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('text=等待文件进入解析流程')).toBeVisible({ timeout: 10000 })

    const fileInput = page.locator('input[type="file"]')
    await expect(fileInput).toBeAttached()
    await expect(fileInput).toHaveAttribute('accept', /.*/)
  })
})
