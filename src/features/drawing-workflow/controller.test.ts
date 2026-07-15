import assert from "node:assert/strict";
import test from "node:test";

import { createDrawingWorkflowController } from "./controller.ts";
import type { DrawingWorkflowClient, EventConnection, StreamDisconnect, TaskEvent, TaskSnapshot } from "./types.ts";

const snapshot = (id: string, state: TaskSnapshot["task"]["state"] = "processing"): TaskSnapshot => ({
  schema_version: "1.0", task: { id, state, phase: state === "cancelled" ? "done" : "drawing_analysis", progress: 0, revision: 1, created_at: null, updated_at: null, error: null },
  drawing: { name: `${id}.png`, source_kind: "png", page_count: 1, preview_urls: [] }, features: [], review: { status: "not_ready", raw_text: null }, process_operations: [], reuse_candidates: [], capabilities: {},
});

interface TestConnection extends EventConnection { emit(event: TaskEvent): void; disconnect(info?: StreamDisconnect): void; closed: boolean }

function harness(getSnapshot: (id: string) => Promise<TaskSnapshot> = async (id) => snapshot(id)) {
  const afterValues: Array<[string, number]> = [];
  const connections: TestConnection[] = [];
  const client: DrawingWorkflowClient = {
    upload: async () => snapshot("uploaded"), getSnapshot,
    connect: (taskId, after, onEvent, onDisconnect = () => {}) => {
      afterValues.push([taskId, after]);
      const connection: TestConnection = { closed: false, close() { this.closed = true; }, emit: onEvent, disconnect: (info) => onDisconnect(info ?? { retryable: true }) };
      connections.push(connection); return connection;
    },
    finalizeAnnotations: async (id) => snapshot(id), submitReview: async (id) => snapshot(id), cancel: async (id) => snapshot(id, "cancelled"), exportUrl: (id) => `/export/${id}`,
  };
  return { client, afterValues, connections };
}

const progress = (taskId: string, seq: number): TaskEvent => ({ schema_version: "1.0", seq, task_id: taskId, type: "phase_progress", phase: "drawing_analysis", progress: 25, timestamp: "", payload: {} });

test("reconnects after the latest accepted sequence and owns connection cleanup", async () => {
  const { client, afterValues, connections } = harness();
  const controller = createDrawingWorkflowController(client, { scheduleReconnect: (callback) => { callback(); return () => {}; }, random: () => 0 });
  await controller.start("task-1"); connections[0].emit(progress("task-1", 12)); connections[0].disconnect();
  assert.deepEqual(afterValues, [["task-1", 0], ["task-1", 12]]);
  assert.equal(connections[0].closed, true); controller.dispose(); controller.dispose(); assert.equal(connections[1].closed, true);
});

test("switching tasks closes old work, resets sequence, and ignores stale snapshot races", async () => {
  let resolveFirst!: (value: TaskSnapshot) => void;
  const { client, afterValues, connections } = harness((id) => id === "old" ? new Promise((resolve) => { resolveFirst = resolve; }) : Promise.resolve(snapshot(id)));
  const controller = createDrawingWorkflowController(client);
  const first = controller.start("old"); await controller.start("new"); resolveFirst(snapshot("old")); await first;
  assert.equal(controller.getState().snapshot?.task.id, "new");
  assert.deepEqual(afterValues, [["new", 0]]);
  connections[0].emit(progress("old", 99));
  assert.equal(controller.getState().lastSeq, 0);
});

test("terminal events close the stream and never reconnect", async () => {
  const scheduled: Array<() => void> = [];
  const { client, connections } = harness();
  const controller = createDrawingWorkflowController(client, { scheduleReconnect: (callback) => { scheduled.push(callback); return () => {}; } });
  await controller.start("task-1");
  connections[0].emit({ ...progress("task-1", 1), type: "task_completed", phase: "done", progress: 100 });
  connections[0].disconnect();
  assert.equal(connections[0].closed, true);
  assert.equal(scheduled.length, 0);
});

test("reconnect delay grows exponentially and caps deterministically", async () => {
  const delays: number[] = [];
  const callbacks: Array<() => void> = [];
  const { client, connections } = harness();
  const controller = createDrawingWorkflowController(client, { scheduleReconnect: (callback, delay) => { delays.push(delay); callbacks.push(callback); return () => {}; }, random: () => 0, maxReconnectDelay: 4_000 });
  await controller.start("task-1");
  for (let index = 0; index < 4; index += 1) { connections[index].disconnect(); callbacks[index](); }
  assert.deepEqual(delays, [1_000, 2_000, 4_000, 4_000]);
  controller.dispose();
});

test("a cancelled snapshot is terminal and does not open a stream", async () => {
  const { client, connections } = harness(async (id) => snapshot(id, "cancelled"));
  const controller = createDrawingWorkflowController(client);
  await controller.start("task-1");
  assert.equal(controller.getState().connection, "closed");
  assert.equal(connections.length, 0);
});

test("nonretryable auth errors enter state and stop reconnect", async () => {
  const scheduled: Array<() => void> = []; const { client, connections } = harness();
  const controller = createDrawingWorkflowController(client, { scheduleReconnect: (callback) => { scheduled.push(callback); return () => {}; } });
  await controller.start("task-1");
  connections[0].disconnect({ status: 403, retryable: true, error: { code: "QUOTA_EXCEEDED", message: "none", retryable: true, phase: "drawing_analysis", details: { remaining: 0 } } });
  assert.equal(controller.getState().error?.code, "QUOTA_EXCEEDED");
  assert.equal(controller.getState().error?.phase, "drawing_analysis");
  assert.equal(scheduled.length, 0);
});

test("server retry hint becomes reconnect base within the configured cap", async () => {
  const delays: number[] = []; const { client, connections } = harness();
  const controller = createDrawingWorkflowController(client, { scheduleReconnect: (_callback, delay) => { delays.push(delay); return () => {}; }, random: () => 0, maxReconnectDelay: 3_000 });
  await controller.start("task-1");
  connections[0].disconnect({ retryable: true, retryMs: 8_000 });
  assert.deepEqual(delays, [3_000]);
});

test("refreshes the snapshot after legacy transition events without page polling", async () => {
  let reads = 0;
  const { client, connections } = harness(async (id) => {
    reads += 1;
    return reads === 1 ? snapshot(id) : { ...snapshot(id), task: { ...snapshot(id).task, state: "awaiting_annotation", phase: "annotation", revision: 2 } };
  });
  const controller = createDrawingWorkflowController(client);
  await controller.start("task-1");
  connections[0].emit({ ...progress("task-1", 1), payload: { legacy_type: "annotation_required" } });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(controller.getState().snapshot?.task.state, "awaiting_annotation");
  assert.equal(reads, 2);
});
