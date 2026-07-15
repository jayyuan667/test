import type { DrawingWorkflowClient, TaskSnapshot } from "./types.ts";

function mockSnapshot(taskId: string): TaskSnapshot {
  return {
    schema_version: "1.0",
    task: { id: taskId, state: "awaiting_review", phase: "feature_review", progress: 60, revision: 1, created_at: null, updated_at: null, error: null },
    drawing: { name: "mock-drawing.png", source_kind: "png", page_count: 1, preview_urls: [] },
    features: [{
      id: "feature-1", kind: "thread", label: "M115×3-6g", value: "M115×3-6g", unit: null,
      tolerance: { upper: null, lower: null, text: "6g" },
      source: { method: "legacy_text", page: null, bbox: null, evidence_text: "【螺纹与螺孔】M115×3-6g" },
      confidence: null, review_status: "unreviewed", missing_reason: null,
    }],
    review: { status: "pending", raw_text: "【螺纹与螺孔】M115×3-6g" },
    process_operations: [], reuse_candidates: [], capabilities: {},
  };
}

export function createMockDrawingWorkflowClient(): DrawingWorkflowClient {
  return {
    upload: async () => mockSnapshot("mock-task"),
    getSnapshot: async (taskId) => mockSnapshot(taskId),
    connect: () => ({ close() {} }),
    finalizeAnnotations: async (taskId) => mockSnapshot(taskId),
    submitReview: async (taskId) => mockSnapshot(taskId),
    cancel: async (taskId) => ({ ...mockSnapshot(taskId), task: { ...mockSnapshot(taskId).task, state: "cancelled", phase: "done" } }),
    exportUrl: (taskId) => `/api/v1/tasks/${encodeURIComponent(taskId)}/export`,
  };
}
