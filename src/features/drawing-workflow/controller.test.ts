import assert from "node:assert/strict";
import test from "node:test";

import { createDrawingWorkflowController } from "./controller.ts";
import type { DrawingWorkflowClient, EventConnection, TaskEvent, TaskSnapshot } from "./types.ts";

const snapshot: TaskSnapshot = {
  schema_version: "1.0",
  task: { id: "task-1", state: "processing", phase: "drawing_analysis", progress: 0, revision: 1, created_at: null, updated_at: null, error: null },
  drawing: { name: "part.png", source_kind: "png", page_count: 1, preview_urls: [] },
  features: [], review: { status: "not_ready", raw_text: null }, process_operations: [], reuse_candidates: [], capabilities: {},
};

test("reconnects after the latest accepted sequence and owns connection cleanup", async () => {
  const afterValues: number[] = [];
  const connections: Array<EventConnection & { emit(event: TaskEvent): void; disconnect(): void; closed: boolean }> = [];
  const client = {
    getSnapshot: async () => snapshot,
    connect: (_taskId: string, after: number, onEvent: (event: TaskEvent) => void, onDisconnect = () => {}) => {
      afterValues.push(after);
      const connection = { closed: false, close() { this.closed = true; }, emit: onEvent, disconnect: onDisconnect };
      connections.push(connection);
      return connection;
    },
  } as DrawingWorkflowClient;
  const controller = createDrawingWorkflowController(client, { scheduleReconnect: (callback) => { callback(); return () => {}; } });

  await controller.start("task-1");
  connections[0].emit({ schema_version: "1.0", seq: 12, task_id: "task-1", type: "phase_progress", phase: "drawing_analysis", progress: 25, timestamp: "2026-07-15T00:00:00Z", payload: {} });
  connections[0].disconnect();

  assert.deepEqual(afterValues, [0, 12]);
  assert.equal(connections[0].closed, true);
  controller.dispose();
  assert.equal(connections[1].closed, true);
});
