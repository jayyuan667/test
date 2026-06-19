export interface Task {
  task_id: string
  status: 'pending' | 'processing' | 'awaiting_review' | 'awaiting_annotation' | 'completed' | 'error' | 'cancelled'
  progress: number
  pdf_name: string
  error?: string
}

export interface ProcessStep {
  code: string
  content: string
}

export interface TaskResult {
  task_id: string
  pdf_name: string
  source_name?: string
  file_count: number
  total_pages: number
  upload_mode: string
  upload_mode_label: string
  can_paginate: boolean
  png_count: number
  expert_judgment: string
  process_flow: {
    data: string[][]
    raw: string
    columns: string[]
    format: string
  }
  process_flow_raw: string
  vision_descriptions: { description: string; _page_number: number }[]
  vision_failures: string[]
  raw_review_text: string
  review_text: string
  feature_report: string
  feature_report_json: Record<string, unknown>
  feature_report_text: string
  feature_report_path: string
  preview_image_urls: string[]
  preview_images: string[]
  image_url: string
  gltf_url?: string
}

export interface SSEEvent {
  type: string
  data: Record<string, unknown>
}

export interface ReviewPayload {
  review_text: string
  action: 'continue' | 'rerun'
  library_key?: string
}

export type PageId = 'generate' | 'zip' | 'history' | 'db'
