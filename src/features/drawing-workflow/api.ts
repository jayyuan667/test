import type { DrawingWorkflowClient, EventConnection, StreamDisconnect, TaskEvent, TaskSnapshot, WorkflowError } from "./types.ts";
import { normalizeTaskEvent, normalizeTaskSnapshot } from "./normalize.ts";

export interface StreamRequest {
  url: string;
  token: string | null;
  after: number;
  fetchImpl: typeof fetch;
  onUnauthorized?: () => void;
  onEvent: (event: TaskEvent) => void;
  onDisconnect: (disconnect: StreamDisconnect) => void;
}

export type StreamTransport = (request: StreamRequest) => EventConnection;

export interface DrawingWorkflowClientOptions {
  apiBase: string;
  getToken: () => string | null;
  fetchImpl?: typeof fetch;
  streamTransport?: StreamTransport;
  onUnauthorized?: () => void;
}

export class DrawingWorkflowApiError extends Error {
  readonly status: number;
  readonly metadata: WorkflowError;
  constructor(status: number, metadata: WorkflowError) {
    super(metadata.message);
    this.name = "DrawingWorkflowApiError";
    this.status = status;
    this.metadata = metadata;
  }
}

function workflowError(body: unknown, status: number): WorkflowError {
  const candidate = (body as { error?: Partial<WorkflowError> } | null)?.error ?? {};
  return {
    code: candidate.code ?? "REQUEST_FAILED",
    message: candidate.message ?? `Request failed (${status})`,
    retryable: candidate.retryable ?? false,
    phase: candidate.phase ?? null,
    details: candidate.details ?? {},
  };
}

async function responseError(response: Response): Promise<DrawingWorkflowApiError> {
  let body: unknown = null;
  try { body = await response.json(); } catch { /* invalid error bodies use the safe fallback */ }
  return new DrawingWorkflowApiError(response.status, workflowError(body, response.status));
}

function parseEvent(data: string, id?: string, eventName?: string): TaskEvent | null {
  try {
    const value = JSON.parse(data) as Record<string, unknown>;
    if (id !== undefined && /^\d+$/.test(id)) value.seq = Number(id);
    if (eventName) value.type = eventName;
    return normalizeTaskEvent(value);
  } catch { return null; }
}

export const fetchStreamTransport: StreamTransport = (request) => {
  const controller = new AbortController();
  let closed = false;
  void (async () => {
    try {
      const headers = new Headers({ Accept: "text/event-stream" });
      if (request.token) headers.set("Authorization", `Bearer ${request.token}`);
      const url = new URL(request.url, globalThis.location?.origin ?? "http://localhost");
      url.searchParams.set("after", String(request.after));
      const response = await request.fetchImpl(request.url.startsWith("/") ? `${url.pathname}${url.search}` : url.toString(), { headers, signal: controller.signal });
      if (!response.ok) {
        if (response.status === 401) request.onUnauthorized?.();
        throw await responseError(response);
      }
      if (!response.body) throw new Error("SSE response has no body");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let frameLines: string[] = [];
      let serverRetryMs: number | undefined;
      const dispatchFrame = () => {
        if (frameLines.length === 0) return;
        let id: string | undefined;
        let eventName: string | undefined;
        const dataLines: string[] = [];
        for (const line of frameLines) {
          if (!line || line.startsWith(":")) continue;
          const separator = line.indexOf(":");
          const field = separator < 0 ? line : line.slice(0, separator);
          const raw = separator < 0 ? "" : line.slice(separator + 1).replace(/^ /, "");
          if (field === "data") dataLines.push(raw);
          else if (field === "id" && !raw.includes("\0")) id = raw;
          else if (field === "event") eventName = raw;
          else if (field === "retry" && /^\d+$/.test(raw)) serverRetryMs = Number(raw);
        }
        frameLines = [];
        const data = dataLines.join("\n");
        if (data) { const event = parseEvent(data, id, eventName); if (event) request.onEvent(event); }
      };
      const consume = (eof: boolean) => {
        let start = 0;
        for (let index = 0; index < buffer.length; index += 1) {
          const char = buffer[index];
          if (char !== "\n" && char !== "\r") continue;
          if (char === "\r" && index === buffer.length - 1 && !eof) break;
          const line = buffer.slice(start, index);
          if (char === "\r" && buffer[index + 1] === "\n") index += 1;
          start = index + 1;
          if (line === "") dispatchFrame(); else frameLines.push(line);
        }
        buffer = buffer.slice(start);
        if (eof) {
          if (buffer) frameLines.push(buffer);
          buffer = "";
          dispatchFrame();
        }
      };
      while (!closed) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        consume(done);
        if (done) break;
      }
      if (!closed) request.onDisconnect({ retryable: true, retryMs: serverRetryMs });
    } catch (error) {
      if (!closed && !(error instanceof DOMException && error.name === "AbortError")) {
        if (error instanceof DrawingWorkflowApiError) request.onDisconnect({ status: error.status, retryable: error.metadata.retryable, error: error.metadata });
        else request.onDisconnect({ retryable: true });
      }
    }
  })();
  return { close() { if (closed) return; closed = true; controller.abort(); } };
};

function baseUrl(apiBase: string): string { return apiBase.replace(/\/$/, ""); }
function taskUrl(apiBase: string, taskId: string, suffix = ""): string { return `${baseUrl(apiBase)}/v1/tasks/${encodeURIComponent(taskId)}${suffix}`; }

export function createDrawingWorkflowClient(options: DrawingWorkflowClientOptions): DrawingWorkflowClient {
  const fetchImpl = options.fetchImpl ?? fetch;
  const streamTransport = options.streamTransport ?? fetchStreamTransport;
  async function request(url: string, init: RequestInit = {}): Promise<TaskSnapshot> {
    const headers = new Headers(init.headers);
    const token = options.getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const response = await fetchImpl(url, { ...init, headers });
    if (!response.ok) {
      if (response.status === 401) options.onUnauthorized?.();
      throw await responseError(response);
    }
    const snapshot = normalizeTaskSnapshot(await response.json());
    if (!snapshot) throw new DrawingWorkflowApiError(502, workflowError({ error: { code: "INVALID_RESPONSE", message: "Invalid workflow response" } }, 502));
    return snapshot;
  }
  const command = (taskId: string, suffix: string, body?: unknown) => request(taskUrl(options.apiBase, taskId, suffix), body === undefined ? { method: "POST" } : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return {
    upload(file) { const form = new FormData(); form.append("file", file, file instanceof File ? file.name : "drawing"); return request(`${baseUrl(options.apiBase)}/v1/tasks`, { method: "POST", body: form }); },
    getSnapshot(taskId) { return request(taskUrl(options.apiBase, taskId)); },
    connect(taskId, after, onEvent, onDisconnect = () => {}) { return streamTransport({ url: taskUrl(options.apiBase, taskId, "/events"), token: options.getToken(), after, fetchImpl, onUnauthorized: options.onUnauthorized, onEvent, onDisconnect }); },
    finalizeAnnotations(taskId, body) { return command(taskId, "/annotations/finalize", body); },
    submitReview(taskId, body) { return command(taskId, "/review", body); },
    cancel(taskId) { return command(taskId, "/cancel"); },
    exportUrl(taskId) { return taskUrl(options.apiBase, taskId, "/export"); },
  };
}
