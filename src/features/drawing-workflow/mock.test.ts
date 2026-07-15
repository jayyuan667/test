import assert from "node:assert/strict";
import test from "node:test";

import { createMockDrawingWorkflowClient } from "./mock.ts";

test("mock returns the v1 snapshot shape without invented confidence", async () => {
  const snapshot = await createMockDrawingWorkflowClient().getSnapshot("mock-task");

  assert.equal(snapshot.schema_version, "1.0");
  assert.equal(snapshot.task.id, "mock-task");
  assert.ok(Array.isArray(snapshot.process_operations));
  assert.ok(snapshot.features.length > 0);
  assert.equal(snapshot.features[0].confidence, null);
  assert.deepEqual(Object.keys(snapshot).sort(), ["capabilities", "drawing", "features", "process_operations", "reuse_candidates", "review", "schema_version", "task"]);
});
