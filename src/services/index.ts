/**
 * 服务层统一导出
 * 根据 NEXT_PUBLIC_USE_MOCK 环境变量切换 Mock / 真实 API
 *
 * 使用方式：
 *   import { dashboardService, processService } from '@/services'
 *   const stats = await dashboardService.getStats()
 */

import type { DashboardService, ProcessService, KnowledgeService, HistoryService } from './types'

import { mockDashboardService } from './mock/dashboard'
import { mockProcessService } from './mock/process'
import { mockKnowledgeService } from './mock/knowledge'
import { mockHistoryService } from './mock/history'

import { apiDashboardService } from './api/dashboard'
import { apiProcessService } from './api/process'
import { apiKnowledgeService } from './api/knowledge'
import { apiHistoryService } from './api/history'
import { createDrawingWorkflowClient } from '@/features/drawing-workflow/api'
import { createMockDrawingWorkflowClient } from '@/features/drawing-workflow/mock'

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK !== 'false' // 默认 Mock

export const dashboardService: DashboardService = USE_MOCK ? mockDashboardService : apiDashboardService
export const processService: ProcessService = USE_MOCK ? mockProcessService : apiProcessService
export const knowledgeService: KnowledgeService = USE_MOCK ? mockKnowledgeService : apiKnowledgeService
export const historyService: HistoryService = USE_MOCK ? mockHistoryService : apiHistoryService
export const workflowService = USE_MOCK
  ? createMockDrawingWorkflowClient()
  : createDrawingWorkflowClient({
      apiBase: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5390'}/api`,
      getToken: () => typeof window === 'undefined' ? null : localStorage.getItem('forge-token'),
    })

// 导出类型
export type { DashboardStats, RecentTask, SystemStatus, Feature, ProcessRow, LibraryScope, KnowledgeRecord, HistoryEntry } from './types'
export type { WorkflowFeature, ProcessOperation, TaskSnapshot, WorkflowState } from './types'
