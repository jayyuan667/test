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
