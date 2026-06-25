export interface AnnotationShape {
  id: string
  label: string
  x: number
  y: number
  width: number
  height: number
}

export interface AnnotationPage {
  pageNumber: number
  shapes: AnnotationShape[]
  imageWidth: number
  imageHeight: number
  imagePath: string
}

export interface AnnotationLabel {
  name: string
  color: string
  borderStyle: string
  isCustom: boolean
}

export const BUILT_IN_LABELS: AnnotationLabel[] = [
  { name: 'code_hole',      color: '#3b82f6', borderStyle: 'solid', isCustom: false },
  { name: 'through_hole',   color: '#22c55e', borderStyle: 'solid', isCustom: false },
  { name: 'blind_hole',     color: '#ef4444', borderStyle: 'solid', isCustom: false },
  { name: 'threaded_hole',  color: '#6366f1', borderStyle: '6,3',   isCustom: false },
  { name: 'chamfer',        color: '#f59e0b', borderStyle: 'solid', isCustom: false },
  { name: 'counterbore',    color: '#f97316', borderStyle: 'solid', isCustom: false },
  { name: 'countersink',    color: '#8b5cf6', borderStyle: 'solid', isCustom: false },
]

export const CUSTOM_LABEL_COLORS = ['#ec4899', '#14b8a6', '#f97316', '#8b5cf6', '#06b6d4']

export const LABEL_DISPLAY_NAMES: Record<string, string> = {
  code_hole: '编码孔',
  through_hole: '通孔',
  blind_hole: '盲孔',
  threaded_hole: '螺纹孔',
  chamfer: '倒角',
  counterbore: '沉头孔',
  countersink: '锥口孔',
}
