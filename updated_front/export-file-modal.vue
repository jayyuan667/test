<script lang="ts" setup>
import type { FormInstance, SelectProps } from 'ant-design-vue'
import { reactive, ref } from 'vue'
import { jsPDF } from 'jspdf'
import '~/utils/font/OPPOSans-L-normal'

interface CraftRow {
  processNo: string
  stepContent: string
  equipmentModel: string
  workingHours: string
}

interface ExportPayload {
  fileName: string
  modelName?: string
  imageUrl?: string
  promptData?: Record<string, string>
  tableData?: CraftRow[]
  featureList?: string[]
}

const emit = defineEmits(['cancel', 'ok'])

const payloadToExport = ref<ExportPayload | null>(null)
const exporting = ref(false)

const visible = ref(false)
const formRef = ref<FormInstance>()

const formData = reactive({
  fileName: '',
  fileType: 'PDF',
})

const fileTypeOptions = ref<SelectProps['options']>([
  { value: 'PDF', label: 'PDF' },
])

const labelCol = { style: { width: '150px' } }
const wrapperCol = { span: 24 }

const FONT = 'OPPOSans-L'

// A4 portrait in mm
const PAGE_W = 210
const PAGE_H = 297
const MARGIN = 10
const CONTENT_W = PAGE_W - MARGIN * 2

const COLS = [
  { title: '工序号', key: 'processNo', w: 19, align: 'center' as const },
  { title: '工序名称及内容', key: 'stepContent', w: 114, align: 'left' as const },
  { title: '设备型号', key: 'equipmentModel', w: 19, align: 'center' as const },
  { title: '工时', key: 'workingHours', w: 19, align: 'center' as const },
  { title: '特征', key: 'features', w: 19, align: 'left' as const },
]

function open(payload: ExportPayload) {
  visible.value = true
  formData.fileName = payload.fileName ? payload.fileName.split('.')[0] : '工艺卡片'
  payloadToExport.value = payload
}

function drawBoldText(doc: jsPDF, text: string | string[], x: number, y: number, opts?: { align?: 'left' | 'center' | 'right' }) {
  // 用 fillThenStroke 模拟加粗：填充 + 描边都用当前文字色，同时加大线宽
  // 保存当前 draw color / line width，结束后恢复
  const prevDraw = (doc as any).getDrawColor?.() ?? '0 G'
  const prevLineW = (doc as any).getLineWidth?.() ?? 0.2

  // 把描边色设为黑色（和文字色一致）
  doc.setDrawColor(0, 0, 0)
  doc.setLineWidth(0.25)
  doc.text(text as any, x, y, { align: opts?.align, renderingMode: 'fillThenStroke' } as any)

  // 恢复
  if (typeof prevDraw === 'string') {
    // jsPDF 返回的是字符串如 "0 G" / "0.5 0.5 0.5 RG"，无法精确还原；
    // 这里直接恢复成表格使用的灰色边框，避免影响后续 rect 描边
    doc.setDrawColor(191, 191, 191)
  }
  doc.setLineWidth(prevLineW)
}

function getFeatures(row: CraftRow, featureList: string[]): string {
  if (!row.stepContent || !featureList?.length) return ''
  return featureList.filter(f => row.stepContent.includes(f)).join('、')
}

async function loadImage(url: string): Promise<{ dataUrl: string; width: number; height: number; format: 'PNG' | 'JPEG' } | null> {
  try {
    const res = await fetch(url, { mode: 'cors' })
    if (!res.ok) return null
    const blob = await res.blob()
    const dataUrl: string = await new Promise((resolve, reject) => {
      const r = new FileReader()
      r.onloadend = () => resolve(r.result as string)
      r.onerror = reject
      r.readAsDataURL(blob)
    })
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const i = new Image()
      i.onload = () => resolve(i)
      i.onerror = reject
      i.src = dataUrl
    })
    const mime = dataUrl.substring(5, dataUrl.indexOf(';'))
    const format: 'PNG' | 'JPEG' = mime === 'image/jpeg' ? 'JPEG' : 'PNG'
    return { dataUrl, width: img.naturalWidth, height: img.naturalHeight, format }
  } catch (e) {
    console.warn('[export] 图片加载失败:', e)
    return null
  }
}

/**
 * Draw a row of table cells at y, return height consumed.
 * Handles multi-line wrapping within each cell and vertical borders.
 */
function drawTableRow(
  doc: jsPDF,
  y: number,
  values: string[],
  opts: { header?: boolean; zebra?: boolean; fontSize: number }
): number {
  const padX = 1.6
  const padY = 2
  doc.setFont(FONT, 'normal')
  doc.setFontSize(opts.fontSize)

  const linesPerCol: string[][] = values.map((raw, i) => {
    const text = raw == null ? '' : String(raw)
    const maxW = COLS[i].w - padX * 2
    const split = doc.splitTextToSize(text || ' ', maxW)
    return Array.isArray(split) ? split : [split]
  })
  const maxLines = Math.max(1, ...linesPerCol.map(l => l.length))
  const lineH = opts.fontSize * 0.42 // mm per line, empirically matches OPPOSans at given pt
  const rowH = Math.max(6, maxLines * lineH + padY * 2)

  // background
  if (opts.header) {
    doc.setFillColor(240, 247, 255)
    doc.rect(MARGIN, y, CONTENT_W, rowH, 'F')
  } else if (opts.zebra) {
    doc.setFillColor(250, 250, 250)
    doc.rect(MARGIN, y, CONTENT_W, rowH, 'F')
  }

  // cell borders + text
  doc.setDrawColor(191, 191, 191)
  doc.setLineWidth(0.15)
  doc.setTextColor(0, 0, 0)

  let x = MARGIN
  for (let i = 0; i < COLS.length; i++) {
    const col = COLS[i]
    doc.rect(x, y, col.w, rowH)
    const lines = linesPerCol[i]
    const totalTextH = lines.length * lineH
    const startBaseline = y + (rowH - totalTextH) / 2 + lineH * 0.78
    // 表头一律居中；数据行按列对齐方式
    const cellAlign: 'left' | 'center' = opts.header ? 'center' : col.align
    for (let li = 0; li < lines.length; li++) {
      const baseline = startBaseline + li * lineH
      const tx = cellAlign === 'center' ? x + col.w / 2 : x + padX
      if (opts.header) {
        doc.setTextColor(0, 0, 0)
        drawBoldText(doc, lines[li], tx, baseline, { align: 'center' })
      } else if (cellAlign === 'center') {
        doc.text(lines[li], tx, baseline, { align: 'center' })
      } else {
        doc.text(lines[li], tx, baseline)
      }
    }
    x += col.w
  }
  return rowH
}

function drawTableHeader(doc: jsPDF, y: number): number {
  const titles = COLS.map(c => c.title)
  return drawTableRow(doc, y, titles, { header: true, fontSize: 9 })
}

async function handleOk() {
  if (exporting.value) return
  try {
    await formRef.value?.validate()
    const payload = payloadToExport.value
    if (!payload) throw new Error('没有可导出的数据')

    exporting.value = true

    const imgInfo = payload.imageUrl ? await loadImage(payload.imageUrl) : null

    const doc = new jsPDF({ unit: 'mm', format: 'a4', compress: true })
    doc.setFont(FONT, 'normal')

    // ===== Title =====
    doc.setFontSize(16)
    doc.setTextColor(0, 0, 0)
    doc.text('工艺规程卡片', PAGE_W / 2, 16, { align: 'center' })
    doc.setDrawColor(24, 144, 255)
    doc.setLineWidth(0.6)
    doc.line(MARGIN, 19, PAGE_W - MARGIN, 19)

    // ===== Top block: image (left) + info (right) =====
    const topY = 24
    // 图片在原 2/3 宽 68mm 高的盒子中等比缩放后得到显示尺寸，再放大 15%。
    // 图片所在格子的宽高即为图片显示宽高，右侧其余宽度留给基本信息。
    const DEFAULT_IMG_BOX_W = Math.round((CONTENT_W * 2) / 3)
    const DEFAULT_IMG_BOX_H = 68
    const MIN_INFO_W = 50 // 信息区至少保留 50mm
    const MAX_TOP_H = 110 // 顶部高度硬上限，避免占掉整页

    let imgDrawW: number
    let imgDrawH: number

    if (imgInfo) {
      const baseScale = Math.min(DEFAULT_IMG_BOX_W / imgInfo.width, DEFAULT_IMG_BOX_H / imgInfo.height)
      const scale = baseScale * 1.15
      imgDrawW = imgInfo.width * scale
      imgDrawH = imgInfo.height * scale

      // 保底：保证信息区宽度与整体高度不越界
      const maxW = CONTENT_W - MIN_INFO_W
      if (imgDrawW > maxW) {
        const k = maxW / imgDrawW
        imgDrawW *= k
        imgDrawH *= k
      }
      if (imgDrawH > MAX_TOP_H) {
        const k = MAX_TOP_H / imgDrawH
        imgDrawW *= k
        imgDrawH *= k
      }
    } else {
      imgDrawW = DEFAULT_IMG_BOX_W
      imgDrawH = DEFAULT_IMG_BOX_H
    }

    const topH = imgDrawH
    const imgBoxW = imgDrawW
    const infoX = MARGIN + imgBoxW
    const infoW = CONTENT_W - imgBoxW

    // outer border + divider
    doc.setDrawColor(191, 191, 191)
    doc.setLineWidth(0.2)
    doc.rect(MARGIN, topY, CONTENT_W, topH)
    doc.line(infoX, topY, infoX, topY + topH)

    // 图片格子：刚好等于图片尺寸，因此直接贴满
    if (imgInfo) {
      doc.addImage(imgInfo.dataUrl, imgInfo.format, MARGIN, topY, imgBoxW, topH, undefined, 'FAST')
    } else {
      doc.setFillColor(250, 250, 250)
      doc.rect(MARGIN + 0.15, topY + 0.15, imgBoxW - 0.3, topH - 0.3, 'F')
      doc.setFontSize(10)
      doc.setTextColor(153, 153, 153)
      doc.text(payload.modelName || '无预览图', MARGIN + imgBoxW / 2, topY + topH / 2, { align: 'center' })
    }

    // info area —— 画成两列的表格：左列键，右列值，一行一个属性
    const infoEntries = Object.entries(payload.promptData || {})
    if (payload.modelName && !infoEntries.some(([k]) => k === '模型名称' || k === '模型')) {
      infoEntries.unshift(['模型名称', payload.modelName])
    }

    doc.setFont(FONT, 'normal')
    doc.setFontSize(9)
    doc.setDrawColor(191, 191, 191)
    doc.setLineWidth(0.15)

    // 属性名列原先为 min(22, infoW*0.4)，分割线往右移动 20%（即 +20% infoW）
    const rawKeyW = Math.min(22, infoW * 0.4) + infoW * 0.2
    const infoKeyW = Math.min(Math.max(rawKeyW, 12), infoW - 16) // 保证值列至少 16mm
    const infoValW = infoW - infoKeyW
    const infoCellPadX = 1.6
    const infoCellPadY = 1.8
    const infoLineH = 9 * 0.42

    // 计算每行高度（值列可能换行）
    const infoRowHeights: number[] = []
    const infoValueLines: string[][] = []
    for (const [, v] of infoEntries) {
      const lines = doc.splitTextToSize(v || ' ', infoValW - infoCellPadX * 2) as string[]
      const arr = Array.isArray(lines) ? lines : [lines]
      infoValueLines.push(arr)
      infoRowHeights.push(Math.max(6, arr.length * infoLineH + infoCellPadY * 2))
    }

    // 适配高度：所有行总高 ≤ topH，否则按比例缩减最后几行的可见数（这里简单截断超出的行）
    let rowY = topY
    const infoBottom = topY + topH
    for (let ri = 0; ri < infoEntries.length; ri++) {
      const rowH = infoRowHeights[ri]
      if (rowY + rowH > infoBottom) {
        // 剩余空间不足，画一个截断标记行
        const remain = infoBottom - rowY
        if (remain > 4) {
          doc.rect(infoX, rowY, infoKeyW, remain)
          doc.rect(infoX + infoKeyW, rowY, infoValW, remain)
          doc.setTextColor(153, 153, 153)
          doc.text('…', infoX + infoCellPadX, rowY + remain / 2 + 1.2)
        }
        break
      }

      const [k] = infoEntries[ri]
      const valueLines = infoValueLines[ri]

      // 单元格背景：键列浅灰
      doc.setFillColor(248, 250, 252)
      doc.rect(infoX, rowY, infoKeyW, rowH, 'F')

      // 边框
      doc.rect(infoX, rowY, infoKeyW, rowH)
      doc.rect(infoX + infoKeyW, rowY, infoValW, rowH)

      // 键文本（加粗 + 居中 + 黑色）
      doc.setTextColor(0, 0, 0)
      drawBoldText(doc, k, infoX + infoKeyW / 2, rowY + rowH / 2 + infoLineH * 0.3, { align: 'center' })

      // 值文本（可能多行，垂直居中）
      doc.setTextColor(0, 0, 0)
      const totalTextH = valueLines.length * infoLineH
      const startBaseline = rowY + (rowH - totalTextH) / 2 + infoLineH * 0.78
      valueLines.forEach((line, li) => {
        doc.text(line, infoX + infoKeyW + infoCellPadX, startBaseline + li * infoLineH)
      })

      rowY += rowH
    }

    // ===== Table =====
    let y = topY + topH + 8
    doc.setFont(FONT, 'normal')
    doc.setFontSize(11)
    doc.setTextColor(24, 144, 255)
    doc.text('工艺规程', MARGIN, y - 1)
    doc.setTextColor(0, 0, 0)
    y += 2

    y += drawTableHeader(doc, y)

    const rows = payload.tableData || []
    const pageBottom = PAGE_H - MARGIN

    if (rows.length === 0) {
      doc.setFontSize(9)
      doc.setTextColor(153, 153, 153)
      doc.setDrawColor(191, 191, 191)
      doc.setLineWidth(0.15)
      const emptyH = 10
      doc.rect(MARGIN, y, CONTENT_W, emptyH)
      doc.text('暂无工艺数据', PAGE_W / 2, y + emptyH / 2 + 1.5, { align: 'center' })
    } else {
      for (let i = 0; i < rows.length; i++) {
        const r = rows[i]
        const values = [
          r.processNo || '',
          r.stepContent || '',
          r.equipmentModel || '',
          r.workingHours || '',
          getFeatures(r, payload.featureList || []),
        ]

        // probe row height by pre-splitting
        const probeLineH = 9 * 0.42
        const probeLines = values.map((v, ci) => {
          const split = doc.splitTextToSize(v || ' ', COLS[ci].w - 3.2)
          return (Array.isArray(split) ? split : [split]).length
        })
        const probeRowH = Math.max(6, Math.max(...probeLines) * probeLineH + 4)

        if (y + probeRowH > pageBottom) {
          doc.addPage()
          y = MARGIN
          y += drawTableHeader(doc, y)
        }

        const h = drawTableRow(doc, y, values, { zebra: i % 2 === 1, fontSize: 9 })
        y += h
      }
    }

    doc.save(`${formData.fileName || 'craft'}.pdf`)
    emit('ok')
    visible.value = false
  } catch (errorInfo) {
    console.log('导出失败:', errorInfo)
  } finally {
    exporting.value = false
  }
}

function handleCancel() {
  formRef.value?.resetFields()
  payloadToExport.value = null
  emit('cancel')
  visible.value = false
}

defineExpose({
  open,
})
</script>

<template>
  <a-modal v-model:open="visible" title="导出文件" :centered="true" width="646px" :mask-closable="!exporting" @cancel="handleCancel">
    <a-form ref="formRef" :model="formData" class="w-full" :label-col="labelCol" :wrapper-col="wrapperCol" layout="vertical">
      <a-form-item name="fileName" label="文件名称" :rules="[{ required: true, message: '请输入文件名称' }]">
        <a-input v-model:value="formData.fileName" placeholder="请输入文件名称" />
      </a-form-item>
      <a-form-item name="fileType" label="文件格式" :rules="[{ required: true, message: '请选择文件格式' }]">
        <a-select v-model:value="formData.fileType" :options="fileTypeOptions" />
      </a-form-item>
    </a-form>
    <template #footer>
      <a-button key="cancel" :disabled="exporting" @click="handleCancel">
        取消
      </a-button>
      <a-button key="submit" type="primary" :loading="exporting" @click="handleOk">
        导出
      </a-button>
    </template>
  </a-modal>
</template>
