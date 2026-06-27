import { test, expect } from '@playwright/test'

const USER = {
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

function createZipWithFiles(count: number): Buffer {
  const chunks: Buffer[] = []
  const centralDirectory: Buffer[] = []
  let offset = 0

  for (let index = 0; index < count; index += 1) {
    const content = Buffer.from(`0010 sample ${index}`)
    const filename = Buffer.from(`file_${index}.txt`, 'utf8')

    const localHeader = Buffer.alloc(30)
    localHeader.writeUInt32LE(0x04034b50, 0)
    localHeader.writeUInt16LE(20, 4)
    localHeader.writeUInt32LE(content.length, 18)
    localHeader.writeUInt32LE(content.length, 22)
    localHeader.writeUInt16LE(filename.length, 26)
    chunks.push(localHeader, filename, content)

    const centralHeader = Buffer.alloc(46)
    centralHeader.writeUInt32LE(0x02014b50, 0)
    centralHeader.writeUInt16LE(20, 4)
    centralHeader.writeUInt16LE(20, 6)
    centralHeader.writeUInt32LE(content.length, 20)
    centralHeader.writeUInt32LE(content.length, 24)
    centralHeader.writeUInt16LE(filename.length, 28)
    centralHeader.writeUInt32LE(offset, 42)
    centralDirectory.push(centralHeader, filename)

    offset += localHeader.length + filename.length + content.length
  }

  const centralDirectoryOffset = offset
  const centralDirectorySize = centralDirectory.reduce((total, chunk) => total + chunk.length, 0)
  const endOfCentralDirectory = Buffer.alloc(22)
  endOfCentralDirectory.writeUInt32LE(0x06054b50, 0)
  endOfCentralDirectory.writeUInt16LE(count, 8)
  endOfCentralDirectory.writeUInt16LE(count, 10)
  endOfCentralDirectory.writeUInt32LE(centralDirectorySize, 12)
  endOfCentralDirectory.writeUInt32LE(centralDirectoryOffset, 16)

  return Buffer.concat([...chunks, ...centralDirectory, endOfCentralDirectory])
}

async function openZipPage(page: import('@playwright/test').Page) {
  await page.route('**/api/auth/me', async route => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { user: USER } }),
    })
  })
  await page.route('**/api/library/scopes', async route => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: [{ library_key: 'private-demo', library_name: '演示工艺库', scope_type: 'private', record_count: 0 }],
      }),
    })
  })

  await page.goto('/')
  await expect(page.getByText('工艺生成')).toBeVisible({ timeout: 10000 })
  await page.getByRole('button', { name: /工艺入库/ }).click()
}

test('ZIP import progress estimates time instead of jumping to 30 percent while the request is pending', async ({ page }) => {
  await openZipPage(page)

  await page.route('**/api/kb/import_zip', async route => {
    await new Promise(resolve => setTimeout(resolve, 6000))
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        batch_id: 'progress-test',
        zip_name: 'progress-test.zip',
        conflict_mode: 'replace',
        library_mode: 'private_empty',
        summary: {
          total_files: 10,
          prt_count: 0,
          pdf_count: 0,
          image_count: 0,
          xlsx_count: 10,
          matched_pairs: 5,
          imported_count: 5,
          skipped_count: 0,
          error_count: 0,
        },
        matched_pairs: [],
        unmatched_pdfs: [],
        unmatched_xlsx: [],
        unmatched_prts: [],
        unmatched_images: [],
        errors: [],
        created_at: '2026-06-27T00:00:00',
      }),
    })
  })

  const fileChooserPromise = page.waitForEvent('filechooser')
  await page.getByRole('button', { name: '上传工艺包' }).click()
  const fileChooser = await fileChooserPromise
  await fileChooser.setFiles({
    name: 'progress-test.zip',
    mimeType: 'application/zip',
    buffer: createZipWithFiles(10),
  })

  await expect(page.getByText(/正在提取工艺与图片特征/)).toBeVisible()
  await page.waitForTimeout(1200)
  await expect(page.getByText('30%')).not.toBeVisible()
})
