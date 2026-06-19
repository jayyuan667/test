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
  { name: 'threaded_hole',    color: '#6366f1', borderStyle: '6,3',   isCustom: false },
  { name: 'circle_hole',      color: '#22c55e', borderStyle: 'solid', isCustom: false },
  { name: 'rivet_hole',       color: '#ec4899', borderStyle: 'solid', isCustom: false },
  { name: 'pin_hole',         color: '#14b8a6', borderStyle: 'solid', isCustom: false },
  { name: 'through_hole',     color: '#3b82f6', borderStyle: 'solid', isCustom: false },
  { name: 'countersunk_hole', color: '#f97316', borderStyle: '6,3',   isCustom: false },
  { name: 'thread_through',   color: '#8b5cf6', borderStyle: '6,3',   isCustom: false },
  { name: 'chamfer',          color: '#f59e0b', borderStyle: 'solid', isCustom: false },
  { name: 'emboss',           color: '#10b981', borderStyle: 'solid', isCustom: false },
  { name: 'flanged_hole',     color: '#06b6d4', borderStyle: 'solid', isCustom: false },
  { name: 'deep_draw',        color: '#ef4444', borderStyle: 'solid', isCustom: false },
]

export const CUSTOM_LABEL_COLORS = ['#ec4899', '#14b8a6', '#f97316', '#8b5cf6', '#06b6d4']

export const LABEL_DISPLAY_NAMES: Record<string, string> = {
  threaded_hole: '螺纹孔',
  circle_hole: '圆孔',
  rivet_hole: '铆钉孔',
  pin_hole: '销钉孔',
  through_hole: '过孔',
  countersunk_hole: '沉头孔',
  thread_through: '螺纹过孔',
  chamfer: '倒角',
  emboss: '压印',
  flanged_hole: '翻边孔',
  deep_draw: '拉深',
}
