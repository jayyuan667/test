import assert from "node:assert/strict";
import test from "node:test";

import { DrawingWorkflowApiError, createDrawingWorkflowClient } from "./api.ts";
import type { TaskSnapshot } from "./types.ts";

const snapshot: TaskSnapshot = {
  schema_version: "1.0",
  task: { id: "task-1", state: "pending", phase: "upload", progress: 0, revision: 0, created_at: null, updated_at: null, error: null },
  drawing: { name: "part.png", source_kind: "png", page_count: 1, preview_urls: [] },
  features: [],
  review: { status: "not_ready", raw_text: null },
  process_operations: [],
  reuse_candidates: [],
  capabilities: {},
};

test("uses v1 URLs and Bearer authentication for HTTP requests", async () => {
  const calls: Array<[RequestInfo | URL, RequestInit | undefined]> = [];
  const client = createDrawingWorkflowClient({
    apiBase: "https://forge.example/api",
    getToken: () => "secret-token",
    fetchImpl: async (input, init) => {
      calls.push([input, init]);
      return new Response(JSON.stringify(snapshot), { status: 200, headers: { "Content-Type": "application/json" } });
    },
    eventSourceFactory: () => { throw new Error("unused"); },
  });

  await client.getSnapshot("task 1");

  assert.equal(calls[0][0], "https://forge.example/api/v1/tasks/task%201");
  assert.equal(new Headers(calls[0][1]?.headers).get("Authorization"), "Bearer secret-token");
});

test("preserves structured metadata on a 403 response", async () => {
  const client = createDrawingWorkflowClient({
    apiBase: "/api",
    getToken: () => "token",
    fetchImpl: async () => new Response(JSON.stringify({ error: {
      code: "QUOTA_EXCEEDED", message: "推理次数已用完", retryable: false,
      phase: "drawing_analysis", details: { remaining: 0 },
    } }), { status: 403, headers: { "Content-Type": "application/json" } }),
    eventSourceFactory: () => { throw new Error("unused"); },
  });

  await assert.rejects(client.getSnapshot("task-1"), (error: unknown) => {
    assert.ok(error instanceof DrawingWorkflowApiError);
    assert.equal(error.status, 403);
    assert.equal(error.metadata.code, "QUOTA_EXCEEDED");
    assert.deepEqual(error.metadata.details, { remaining: 0 });
    return true;
  });
});

test("notifies the shared unauthorized handler on a 401 response", async () => {
  let unauthorized = false;
  const client = createDrawingWorkflowClient({
    apiBase: "/api",
    getToken: () => "expired",
    onUnauthorized: () => { unauthorized = true; },
    fetchImpl: async () => new Response(JSON.stringify({ error: { code: "UNAUTHORIZED", message: "登录已过期" } }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    }),
    eventSourceFactory: () => { throw new Error("unused"); },
  });

  await assert.rejects(client.getSnapshot("task-1"), DrawingWorkflowApiError);
  assert.equal(unauthorized, true);
});

test("connect includes the last sequence and query token in the SSE URL", () => {
  let url = "";
  const client = createDrawingWorkflowClient({
    apiBase: "https://forge.example/api/",
    getToken: () => "token with spaces",
    fetchImpl: async () => { throw new Error("unused"); },
    eventSourceFactory: (input) => {
      url = input;
      return { close() {}, onmessage: null, onerror: null };
    },
  });

  client.connect("task-1", 19, () => {});

  assert.equal(url, "https://forge.example/api/v1/tasks/task-1/events?after=19&token=token+with+spaces");
});
