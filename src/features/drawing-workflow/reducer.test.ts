import assert from "node:assert/strict";
import test from "node:test";

import { createInitialWorkflowState, reduceWorkflowState } from "./reducer.ts";
import type { ProcessOperation, TaskEvent, TaskSnapshot } from "./types.ts";

const operation = (content: string): ProcessOperation => ({
  id: "op-1",
  code: "0050",
  trade: "车工",
  content,
  equipment: [],
  duration_minutes: null,
  parameters: [],
  note: null,
  evidence_features: [],
  status: "streaming",
});

const operationEvent = (seq: number, content: string): TaskEvent => ({
  schema_version: "1.0",
  seq,
  task_id: "task-1",
  type: "operation_upserted",
  phase: "process_generation",
  progress: 50,
  timestamp: "2026-07-15T00:00:00Z",
  payload: { operation: operation(content) },
});

test("ignores an event whose sequence is not newer", () => {
  const state = { ...createInitialWorkflowState(), lastSeq: 8 };

  assert.strictEqual(reduceWorkflowState(state, operationEvent(8, "ignored")), state);
});

test("initializes the event cursor from the snapshot revision", () => {
  const snapshot: TaskSnapshot = { schema_version: "1.0", task: { id: "task-1", state: "processing", phase: "drawing_analysis", progress: 10, revision: 42, created_at: null, updated_at: null, error: null }, drawing: { name: "x", source_kind: "png", page_count: 1, preview_urls: [] }, features: [], review: { status: "not_ready", raw_text: null }, process_operations: [], reuse_candidates: [], capabilities: {} };
  assert.equal(createInitialWorkflowState(snapshot).lastSeq, 42);
});

test("replaces an operation with the same id without appending a row", () => {
  const first = reduceWorkflowState(createInitialWorkflowState(), operationEvent(1, "粗车外圆"));
  const second = reduceWorkflowState(first, operationEvent(2, "精车外圆"));

  assert.deepEqual(second.operationOrder, ["op-1"]);
  assert.equal(second.operationsById["op-1"].content, "精车外圆");
});

test("replaces a snapshot only when its revision is higher", () => {
  const makeSnapshot = (revision: number, name: string): TaskSnapshot => ({
    schema_version: "1.0",
    task: { id: "task-1", state: "processing", phase: "drawing_analysis", progress: 10, revision, created_at: null, updated_at: null, error: null },
    drawing: { name, source_kind: "png", page_count: 1, preview_urls: [] },
    features: [], review: { status: "not_ready", raw_text: null }, process_operations: [], reuse_candidates: [], capabilities: {},
  });
  const current = createInitialWorkflowState(makeSnapshot(2, "current.png"));

  const sameRevision = reduceWorkflowState(current, { type: "snapshot_received", snapshot: makeSnapshot(2, "stale.png") });
  const higherRevision = reduceWorkflowState(current, { type: "snapshot_received", snapshot: makeSnapshot(3, "new.png") });

  assert.strictEqual(sameRevision, current);
  assert.equal(higherRevision.snapshot?.drawing.name, "new.png");
});

test("upserts a feature into the snapshot on feature_ready", () => {
  const initial = createInitialWorkflowState({
    schema_version: "1.0", task: { id: "task-1", state: "processing", phase: "drawing_analysis", progress: 0, revision: 1, created_at: null, updated_at: null, error: null },
    drawing: { name: "x", source_kind: "unknown", page_count: 1, preview_urls: [] }, features: [], review: { status: "not_ready", raw_text: null }, process_operations: [], reuse_candidates: [], capabilities: {},
  });
  const feature = { id: "f-1", kind: "thread" as const, label: "M3", value: "M3", unit: null, tolerance: { upper: null, lower: null, text: null }, source: { method: "legacy_text" as const, page: null, bbox: null, evidence_text: null }, confidence: null, review_status: "unreviewed" as const, missing_reason: null };
  const event: TaskEvent = { schema_version: "1.0", seq: 2, task_id: "task-1", type: "feature_ready", phase: "drawing_analysis", progress: 25, timestamp: "", payload: { feature } };

  const next = reduceWorkflowState(initial, event);
  assert.deepEqual(next.snapshot?.features, [feature]);
});

test("preserves cancelled terminal state and clears completion errors", () => {
  const failed = { code: "X", message: "x", retryable: false, phase: "drawing_analysis" as const, details: {} };
  const base = createInitialWorkflowState({ schema_version: "1.0", task: { id: "task-1", state: "processing", phase: "drawing_analysis", progress: 0, revision: 1, created_at: null, updated_at: null, error: failed }, drawing: { name: "x", source_kind: "unknown", page_count: 1, preview_urls: [] }, features: [], review: { status: "not_ready", raw_text: null }, process_operations: [], reuse_candidates: [], capabilities: {} });
  const completed = reduceWorkflowState(base, { schema_version: "1.0", seq: 2, task_id: "task-1", type: "task_completed", phase: "done", progress: 100, timestamp: "", payload: {} });
  const cancelled = reduceWorkflowState(base, { schema_version: "1.0", seq: 2, task_id: "task-1", type: "task_failed", phase: "done", progress: 10, timestamp: "", payload: { status: "cancelled", error: failed } });

  assert.equal(completed.snapshot?.task.error, null);
  assert.equal(cancelled.snapshot?.task.state, "cancelled");
});

test("real legacy fixture sequence never regresses phase or progress on unknown values", () => {
  let state = createInitialWorkflowState({ schema_version: "1.0", task: { id: "task-1", state: "processing", phase: "drawing_analysis", progress: 20, revision: 1, created_at: null, updated_at: null, error: null }, drawing: { name: "x", source_kind: "png", page_count: 1, preview_urls: [] }, features: [], review: { status: "not_ready", raw_text: null }, process_operations: [], reuse_candidates: [], capabilities: {} });
  const fixture: TaskEvent[] = [
    { ...operationEvent(2, "unused"), type: "phase_progress", phase: "annotation", progress: 45, payload: { legacy_type: "annotation_required" } },
    { ...operationEvent(3, "unused"), type: "heartbeat", phase: "drawing_analysis", progress: 0, payload: { legacy_type: "unknown" } },
    { ...operationEvent(4, "unused"), type: "phase_progress", phase: "feature_review", progress: 60, payload: { legacy_type: "review_required" } },
    { ...operationEvent(5, "unused"), type: "phase_progress", phase: "process_generation", progress: 75, payload: { legacy_type: "process_stream" } },
  ];
  for (const event of fixture) state = reduceWorkflowState(state, event);
  assert.equal(state.snapshot?.task.phase, "process_generation");
  assert.equal(state.snapshot?.task.progress, 75);
});

test("task_failed preserves the structured payload error and checkpoint", () => {
  const base = createInitialWorkflowState({ schema_version: "1.0", task: { id: "task-1", state: "processing", phase: "drawing_analysis", progress: 38, revision: 1, created_at: null, updated_at: null, error: null }, drawing: { name: "x", source_kind: "png", page_count: 1, preview_urls: [] }, features: [], review: { status: "not_ready", raw_text: null }, process_operations: [], reuse_candidates: [], capabilities: {} });
  const error = { code: "VLM_TIMEOUT", message: "timeout", retryable: true, phase: "drawing_analysis" as const, details: { checkpoint: "page-2" } };
  const next = reduceWorkflowState(base, { schema_version: "1.0", seq: 2, task_id: "task-1", type: "task_failed", phase: "drawing_analysis", progress: 38, timestamp: "", payload: { error, checkpoint: "page-2" } });
  assert.deepEqual(next.snapshot?.task.error, error);
  assert.equal(next.snapshot?.task.progress, 38);
});
