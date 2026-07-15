/**
 * 统一服务接口定义
 * Mock 和真实 API 都实现这些接口
 */

// ═══ Dashboard ═══
export interface DashboardStats {
  todayGenerated: number
  totalRecords: number
  processingTasks: number
  successRate: number
}

export interface RecentTask {
  id: string
  name: string
  status: 'completed' | 'running' | 'failed'
  time: string
  processCount: number
}

export interface SystemStatus {
  apiLatency: string
  gpuLoad: string
  queueDepth: number
  storageUsage: string
}

export interface DashboardService {
  getStats(): Promise<DashboardStats>
  getRecentTasks(): Promise<RecentTask[]>
  getSystemStatus(): Promise<SystemStatus>
}

// ═══ Process Generation ═══
export interface Feature {
  id: string
  name: string
  confidence: number
  type: string
}

export interface ProcessRow {
  no: string
  name: string
  equip: string
  time: string
  params: string
  note: string
  status: 'done' | 'streaming' | 'pending'
}

export interface ProcessResult {
  taskId: string
  features: Feature[]
  processRows: ProcessRow[]
  reviewText: string
}

export interface ProcessService {
  uploadDrawing(file: File): Promise<{ taskId: string }>
  getFeatures(taskId: string): Promise<Feature[]>
  submitReview(taskId: string, reviewText: string): Promise<void>
  getProcessRows(taskId: string): Promise<ProcessRow[]>
  onProgress(taskId: string, callback: (progress: number, stage: string) => void): () => void
}

export type {
  DrawingWorkflowClient,
  Feature as WorkflowFeature,
  ProcessOperation,
  TaskSnapshot,
  WorkflowState,
} from '@/features/drawing-workflow/types'

// ═══ Knowledge Base ═══
export interface LibraryScope {
  key: string
  name: string
  type: 'public' | 'personal'
  recordCount: number
}

export interface KnowledgeRecord {
  id: string
  name: string
  productType: string
  processes: number
  status: 'available' | 'imported' | 'draft'
  source: string
  date: string
}

export interface KnowledgeService {
  getScopes(): Promise<LibraryScope[]>
  getRecords(params: { scope?: string; page?: number; pageSize?: number; query?: string }): Promise<{ items: KnowledgeRecord[]; total: number }>
  getRecord(id: string): Promise<KnowledgeRecord | null>
}

// ═══ History ═══
export interface HistoryEntry {
  taskId: string
  fileName: string
  status: 'completed' | 'failed' | 'cancelled' | 'running'
  createdAt: string
  completedAt?: string
  processCount: number
}

export interface HistoryService {
  getHistory(params?: { page?: number; status?: string }): Promise<{ items: HistoryEntry[]; total: number }>
  deleteTask(taskId: string): Promise<void>
}

// ═══ ZIP Import ═══
export interface ZipImportService {
  importZip(file: File, libraryKey?: string): Promise<{ runId: string }>
  getImportStatus(runId: string): Promise<{ status: string; progress: number; matched: number; unmatched: number }>
}
