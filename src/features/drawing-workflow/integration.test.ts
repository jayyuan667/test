import assert from "node:assert/strict";
import test from "node:test";

import { createDrawingWorkflowController } from "./controller.ts";
import type { DrawingWorkflowClient, EventConnection, Feature, ProcessOperation, TaskEvent, TaskSnapshot } from "./types.ts";

const feature: Feature = {
  id: "feature-thread", kind: "thread", label: "M115×3-6g", value: "M115×3-6g", unit: null,
  tolerance: { upper: null, lower: null, text: "6g" },
  source: { method: "vlm", page: 1, bbox: null, evidence_text: "M115×3-6g" },
  confidence: null, review_status: "unreviewed", missing_reason: null,
};
const operation: ProcessOperation = {
  id: "operation-10", code: "0010", trade: "车工", content: "粗车外圆", equipment: ["数控车床"],
  duration_minutes: null, parameters: [], note: null, evidence_features: [], status: "complete",
};

function snapshot(state: TaskSnapshot["task"]["state"] = "processing"): TaskSnapshot {
  return {
    schema_version: "1.0", task: { id: "task-real", state, phase: "drawing_analysis", progress: 0, revision: 1, created_at: null, updated_at: null, error: null },
    drawing: { name: "test.png", source_kind: "png", page_count: 1, preview_urls: [] }, features: [],
    review: { status: "not_ready", raw_text: null }, process_operations: [], reuse_candidates: [], capabilities: {},
  };
}

test("controller owns upload, feature review, operation upsert, and completion without markdown parsing", async () => {
  let emit!: (event: TaskEvent) => void;
  const reviews: unknown[] = [];
  const client: DrawingWorkflowClient = {
    upload: async () => snapshot(), getSnapshot: async () => snapshot(),
    getAsset: async () => new Blob(["preview"]),
    connect: (_taskId, _after, onEvent): EventConnection => { emit = onEvent; return { close() {} }; },
    finalizeAnnotations: async () => ({ ...snapshot("awaiting_review"), features: [feature], review: { status: "pending", raw_text: null } }),
    submitReview: async (_taskId, body) => { reviews.push(body); return { ...snapshot(), task: { ...snapshot().task, phase: "process_generation", progress: 65 } }; },
    cancel: async () => snapshot("cancelled"), exportUrl: (id) => `/api/v1/tasks/${id}/export?format=pdf`,
  };
  const controller = createDrawingWorkflowController(client);

  await controller.upload(new Blob(["drawing"]));
  emit({ schema_version: "1.0", seq: 2, task_id: "task-real", type: "feature_ready", phase: "feature_review", progress: 60, timestamp: "", payload: { feature } });
  await controller.finalizeAnnotations();
  await controller.submitReview({ features: [feature] });
  emit({ schema_version: "1.0", seq: 3, task_id: "task-real", type: "operation_upserted", phase: "process_generation", progress: 85, timestamp: "", payload: { operation } });
  emit({ schema_version: "1.0", seq: 4, task_id: "task-real", type: "task_completed", phase: "done", progress: 100, timestamp: "", payload: {} });

  const state = controller.getState();
  assert.equal(state.snapshot?.features[0], feature);
  assert.equal(state.operationsById[operation.id], operation);
  assert.equal(state.snapshot?.task.progress, 100);
  assert.equal(state.snapshot?.task.state, "completed");
  assert.deepEqual(reviews, [{ features: [feature] }]);
  assert.equal(controller.exportUrl(), "/api/v1/tasks/task-real/export?format=pdf");
});
