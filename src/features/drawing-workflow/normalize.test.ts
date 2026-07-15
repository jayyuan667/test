import assert from "node:assert/strict";
import test from "node:test";

import { normalizeTaskEvent, normalizeTaskSnapshot } from "./normalize.ts";

test("normalizes nullable backend collections without inventing confidence", () => {
  const snapshot = normalizeTaskSnapshot({ schema_version: "1.0", task: { id: "t", state: "processing", phase: "drawing_analysis", progress: null, revision: null }, drawing: { name: null, source_kind: null, page_count: null, preview_urls: null }, features: [{ id: "f", kind: null, label: null, source: { method: null }, confidence: null }], review: null, process_operations: null, reuse_candidates: null, capabilities: null });
  assert.ok(snapshot);
  assert.equal(snapshot.task.progress, 0);
  assert.deepEqual(snapshot.process_operations, []);
  assert.equal(snapshot.features[0].confidence, null);
  assert.equal(snapshot.features[0].source.method, null);
});

test("rejects invalid events and defaults nullable progress to a number", () => {
  assert.equal(normalizeTaskEvent({ seq: null, task_id: "t" }), null);
  const event = normalizeTaskEvent({ schema_version: "1.0", seq: 1, task_id: "t", type: "heartbeat", phase: "drawing_analysis", progress: null, timestamp: null, payload: null });
  assert.equal(event?.progress, 0);
  assert.deepEqual(event?.payload, {});
});

test("normalizes invalid enum and numeric wire values to approved fallbacks", () => {
  const snapshot = normalizeTaskSnapshot({ schema_version: "1.0", task: { id: "t", state: "alien", phase: "alien", progress: Infinity, revision: -1 }, drawing: { source_kind: "exe", page_count: -2 }, features: [{ kind: "alien", confidence: 2, review_status: "alien", source: { method: "guess", page: -1, bbox: [1, 2, Infinity, 4] } }], review: { status: "alien" }, process_operations: [{ status: "alien", duration_minutes: -5 }] });
  assert.ok(snapshot);
  assert.equal(snapshot.task.state, "pending"); assert.equal(snapshot.task.phase, "upload"); assert.equal(snapshot.task.progress, 0); assert.equal(snapshot.task.revision, 0);
  assert.equal(snapshot.drawing.source_kind, "unknown"); assert.equal(snapshot.drawing.page_count, 1);
  assert.equal(snapshot.features[0].kind, "unknown"); assert.equal(snapshot.features[0].confidence, null); assert.equal(snapshot.features[0].source.bbox, null); assert.equal(snapshot.features[0].source.page, null);
  assert.equal(snapshot.features[0].review_status, "unreviewed"); assert.equal(snapshot.review.status, "not_ready");
  assert.equal(snapshot.process_operations[0].status, "draft"); assert.equal(snapshot.process_operations[0].duration_minutes, null);
});

test("omits an invalid nested snapshot and accepts canonical cancelled status", () => {
  const event = normalizeTaskEvent({ schema_version: "1.0", seq: 1, task_id: "t", type: "task_failed", phase: "done", progress: 0, timestamp: "", payload: { status: "cancelled", snapshot: { nope: true } } });
  assert.equal(event?.payload.status, "cancelled");
  assert.equal(Object.hasOwn(event?.payload ?? {}, "snapshot"), false);
});
