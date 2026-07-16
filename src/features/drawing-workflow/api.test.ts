import assert from "node:assert/strict";
import test from "node:test";

import { DrawingWorkflowApiError, createDrawingWorkflowClient } from "./api.ts";
import type { TaskEvent, TaskSnapshot } from "./types.ts";

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
  });

  await assert.rejects(client.getSnapshot("task-1"), DrawingWorkflowApiError);
  assert.equal(unauthorized, true);
});

test("connect passes the last sequence and token to the injected stream transport", () => {
  const requests: Array<{ url: string; token: string | null; after: number }> = [];
  const client = createDrawingWorkflowClient({
    apiBase: "https://forge.example/api/",
    getToken: () => "token with spaces",
    fetchImpl: async () => { throw new Error("unused"); },
    streamTransport: (input) => { requests.push(input); return { close() {} }; },
  });

  client.connect("task-1", 19, () => {});

  assert.equal(requests[0].url, "https://forge.example/api/v1/tasks/task-1/events");
  assert.equal(requests[0].token, "token with spaces");
  assert.equal(requests[0].after, 19);
});

test("default stream sends Bearer auth, parses named frames, and aborts", async () => {
  let signal: AbortSignal | undefined;
  let authorization: string | null = null;
  const encoder = new TextEncoder();
  const frames = [": keepalive\nretry: 2500\nid: 7\nevent: phase_progress\ndata: {\"schema_version\":\"1.0\",\"seq\":999,\"task_id\":\"task-1\",\"type\":\"heartbeat\",\"phase\":\"drawing_analysis\",\"progress\":42,\"timestamp\":\"now\",\"payload\":{}}\n\n"];
  const client = createDrawingWorkflowClient({ apiBase: "/api", getToken: () => "secret", fetchImpl: async (_input, init) => {
    signal = init?.signal ?? undefined;
    authorization = new Headers(init?.headers).get("Authorization");
    return new Response(new ReadableStream({ start(controller) { frames.forEach((frame) => controller.enqueue(encoder.encode(frame))); controller.close(); } }), { status: 200, headers: { "Content-Type": "text/event-stream" } });
  }});
  const events: TaskEvent[] = [];
  const connection = client.connect("task-1", 6, (event) => events.push(event));
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.equal(authorization, "Bearer secret");
  assert.equal(events[0]?.seq, 7);
  assert.equal(events[0]?.type, "phase_progress");
  connection.close();
  assert.equal(signal?.aborted, true);
});

test("default stream invokes browser fetch without binding the transport request as this", async () => {
  let receiver: unknown = "not-called";
  const fetchImpl = async function (this: unknown) {
    // eslint-disable-next-line @typescript-eslint/no-this-alias
    receiver = this;
    return new Response(new ReadableStream({ start(controller) { controller.close(); } }), { status: 200 });
  } as typeof fetch;
  const client = createDrawingWorkflowClient({ apiBase: "/api", getToken: () => null, fetchImpl });
  client.connect("task-1", 0, () => {});
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(receiver, undefined);
});

test("stream ignores malformed JSON and reports HTTP auth errors", async () => {
  let disconnected: unknown; let unauthorizedCalls = 0;
  const client = createDrawingWorkflowClient({ apiBase: "/api", getToken: () => "expired", onUnauthorized: () => { unauthorizedCalls += 1; }, fetchImpl: async () => new Response(JSON.stringify({ error: { code: "UNAUTHORIZED", message: "expired" } }), { status: 401, headers: { "Content-Type": "application/json" } }) });
  client.connect("task-1", 0, () => assert.fail("no event expected"), (error) => { disconnected = error ?? disconnected; });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.ok(disconnected);
  assert.equal(unauthorizedCalls, 1);
});

test("stream skips malformed data and preserves structured 403 metadata", async () => {
  const encoder = new TextEncoder();
  let calls = 0; let failure: import("./types.ts").StreamDisconnect | undefined;
  const client = createDrawingWorkflowClient({ apiBase: "/api", getToken: () => "token", fetchImpl: async () => {
    calls += 1;
    if (calls === 1) return new Response(new ReadableStream({ start(controller) { controller.enqueue(encoder.encode("event: heartbeat\ndata: not-json\n\n")); controller.close(); } }), { status: 200 });
    return new Response(JSON.stringify({ error: { code: "QUOTA_EXCEEDED", message: "none", retryable: false, phase: "drawing_analysis", details: { remaining: 0 } } }), { status: 403, headers: { "Content-Type": "application/json" } });
  }});
  client.connect("task-1", 0, () => assert.fail("malformed data must be ignored"));
  await new Promise((resolve) => setTimeout(resolve, 0));
  client.connect("task-1", 0, () => {}, (error) => { failure = error; });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(failure?.error?.code, "QUOTA_EXCEEDED");
  assert.equal(failure?.status, 403);
});

test("upload and command methods use exact v1 endpoints and export URL", async () => {
  const calls: Array<{ url: string; method: string }> = [];
  const client = createDrawingWorkflowClient({ apiBase: "/api", getToken: () => "token", fetchImpl: async (input, init) => { calls.push({ url: String(input), method: init?.method ?? "GET" }); return new Response(JSON.stringify(snapshot), { status: 200, headers: { "Content-Type": "application/json" } }); }, streamTransport: () => ({ close() {} }) });
  await client.upload(new File(["x"], "part.png"));
  await client.finalizeAnnotations("task-1", {});
  await client.submitReview("task-1", { features: [] });
  await client.cancel("task-1");
  assert.deepEqual(calls.map(({ url, method }) => [url, method]), [["/api/v1/tasks", "POST"], ["/api/v1/tasks/task-1/annotations/finalize", "POST"], ["/api/v1/tasks/task-1/review", "POST"], ["/api/v1/tasks/task-1/cancel", "POST"]]);
  assert.equal(client.exportUrl("task 1"), "/api/v1/tasks/task%201/export?format=pdf");
});

test("loads a preview asset with Bearer auth through the workflow client", async () => {
  let url = ""; let authorization: string | null = null;
  const client = createDrawingWorkflowClient({ apiBase: "https://forge.example/api", getToken: () => "preview-token", fetchImpl: async (input, init) => {
    url = String(input); authorization = new Headers(init?.headers).get("Authorization");
    return new Response(new Blob(["image"], { type: "image/png" }), { status: 200 });
  }, streamTransport: () => ({ close() {} }) });
  const blob = await client.getAsset("task", "/api/result/task/asset/pages/test.png");
  assert.equal(url, "https://forge.example/api/result/task/asset/pages/test.png");
  assert.equal(authorization, "Bearer preview-token");
  assert.equal(blob.type, "image/png");
});

test("rejects untrusted asset URLs before fetch or Authorization creation", async () => {
  let fetchCalls = 0; let tokenCalls = 0;
  const client = createDrawingWorkflowClient({
    apiBase: "https://forge.example/api",
    getToken: () => { tokenCalls += 1; return "must-not-leak"; },
    fetchImpl: async () => { fetchCalls += 1; throw new Error("fetch must not run"); },
  });
  const invalid = [
    "https://evil.example/api/result/task-1/asset/pages/a.png",
    "/api/result/other-task/asset/pages/a.png",
    "/api/result/task-1/not-asset/pages/a.png",
    "/api/result/task-1/asset/../secret.txt",
    "/api/result/task-1/asset/%2e%2e%2fsecret.txt",
    "/api/result/task-1/asset/",
  ];
  for (const url of invalid) await assert.rejects(client.getAsset("task-1", url), /Untrusted workflow asset URL/);
  assert.equal(fetchCalls, 0);
  assert.equal(tokenCalls, 0);
});

test("SSE parser survives every byte split around CRLF frames and flushes EOF", async () => {
  const encoder = new TextEncoder();
  const wire = "retry: 2750\r\nid: 3\r\nevent: heartbeat\r\ndata: {\"schema_version\":\"1.0\",\"seq\":3,\"task_id\":\"task-1\",\"type\":\"heartbeat\",\"phase\":\"drawing_analysis\",\"progress\":1,\"timestamp\":\"\",\"payload\":{}}\r\n\r\nid: 4\revent: heartbeat\rdata: {\"schema_version\":\"1.0\",\"seq\":4,\"task_id\":\"task-1\",\"type\":\"heartbeat\",\"phase\":\"drawing_analysis\",\"progress\":2,\"timestamp\":\"\",\"payload\":{}}";
  for (const split of Array.from({ length: wire.length - 1 }, (_, index) => index + 1)) {
    const bytes = encoder.encode(wire); const events: TaskEvent[] = []; let retryMs: number | undefined;
    const client = createDrawingWorkflowClient({ apiBase: "/api", getToken: () => "t", fetchImpl: async () => new Response(new ReadableStream({ start(controller) { controller.enqueue(bytes.slice(0, split)); controller.enqueue(bytes.slice(split)); controller.close(); } }), { status: 200 }) });
    client.connect("task-1", 0, (event) => events.push(event), (disconnect) => { retryMs = disconnect.retryMs; });
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.deepEqual(events.map((event) => event.seq), [3, 4], `split=${split}`);
    assert.equal(retryMs, 2750);
  }
});

test("SSE parser joins multiline data fields split one byte at a time", async () => {
  const wire = "event: heartbeat\ndata: {\"schema_version\":\"1.0\",\ndata: \"seq\":5,\"task_id\":\"task-1\",\"type\":\"heartbeat\",\"phase\":\"drawing_analysis\",\"progress\":0,\"timestamp\":\"\",\"payload\":{}}\n\n";
  const bytes = new TextEncoder().encode(wire); const events: TaskEvent[] = [];
  const client = createDrawingWorkflowClient({ apiBase: "/api", getToken: () => null, fetchImpl: async () => new Response(new ReadableStream({ start(controller) { bytes.forEach((byte) => controller.enqueue(Uint8Array.of(byte))); controller.close(); } }), { status: 200 }) });
  client.connect("task-1", 0, (event) => events.push(event)); await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(events[0]?.seq, 5);
});
