import type {
  DrawingWorkflowClient,
  EventConnection,
  TaskEvent,
  TaskEventType,
  TaskSnapshot,
  WorkflowError,
} from "./types.ts";

interface EventSourceLike extends EventConnection {
  onmessage: ((event: MessageEvent<string>) => void) | null;
  onerror: ((event: Event) => void) | null;
  addEventListener?(type: string, listener: (event: MessageEvent<string>) => void): void;
}

export interface DrawingWorkflowClientOptions {
  apiBase: string;
  getToken: () => string | null;
  fetchImpl?: typeof fetch;
  eventSourceFactory?: (url: string) => EventSourceLike;
  onUnauthorized?: () => void;
}

export class DrawingWorkflowApiError extends Error {
  readonly status: number;
  readonly metadata: WorkflowError;

  constructor(
    status: number,
    metadata: WorkflowError,
  ) {
    super(metadata.message);
    this.name = "DrawingWorkflowApiError";
    this.status = status;
    this.metadata = metadata;
  }
}

const eventTypes: TaskEventType[] = [
  "phase_started", "phase_progress", "feature_ready", "operation_upserted",
  "phase_completed", "task_completed", "task_failed", "heartbeat",
];

function baseUrl(apiBase: string): string {
  return apiBase.replace(/\/$/, "");
}

function taskUrl(apiBase: string, taskId: string, suffix = ""): string {
  return `${baseUrl(apiBase)}/v1/tasks/${encodeURIComponent(taskId)}${suffix}`;
}

export function createDrawingWorkflowClient(options: DrawingWorkflowClientOptions): DrawingWorkflowClient {
  const fetchImpl = options.fetchImpl ?? fetch;
  const eventSourceFactory = options.eventSourceFactory ?? ((url) => new EventSource(url));

  async function request(url: string, init: RequestInit = {}): Promise<TaskSnapshot> {
    const headers = new Headers(init.headers);
    const token = options.getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const response = await fetchImpl(url, { ...init, headers });
    const body: unknown = await response.json();
    if (!response.ok) {
      if (response.status === 401) options.onUnauthorized?.();
      const candidate = (body as { error?: Partial<WorkflowError> }).error ?? {};
      throw new DrawingWorkflowApiError(response.status, {
        code: candidate.code ?? "REQUEST_FAILED",
        message: candidate.message ?? `Request failed (${response.status})`,
        retryable: candidate.retryable ?? false,
        phase: candidate.phase ?? null,
        details: candidate.details ?? {},
      });
    }
    return body as TaskSnapshot;
  }

  function command(taskId: string, suffix: string, body?: unknown): Promise<TaskSnapshot> {
    const init: RequestInit = { method: "POST" };
    if (body !== undefined) {
      init.headers = { "Content-Type": "application/json" };
      init.body = JSON.stringify(body);
    }
    return request(taskUrl(options.apiBase, taskId, suffix), init);
  }

  return {
    upload(file) {
      const form = new FormData();
      form.append("file", file, file instanceof File ? file.name : "drawing");
      return request(`${baseUrl(options.apiBase)}/v1/tasks`, { method: "POST", body: form });
    },
    getSnapshot(taskId) {
      return request(taskUrl(options.apiBase, taskId));
    },
    connect(taskId, after, onEvent, onDisconnect) {
      const url = new URL(taskUrl(options.apiBase, taskId, "/events"), globalThis.location?.origin ?? "http://localhost");
      url.searchParams.set("after", String(after));
      const token = options.getToken();
      if (token) url.searchParams.set("token", token);
      const source = eventSourceFactory(url.origin === "http://localhost" && options.apiBase.startsWith("/") ? `${url.pathname}${url.search}` : url.toString());
      const receive = (message: MessageEvent<string>) => onEvent(JSON.parse(message.data) as TaskEvent);
      if (source.addEventListener) eventTypes.forEach((type) => source.addEventListener?.(type, receive));
      else source.onmessage = receive;
      source.onerror = () => onDisconnect?.();
      return source;
    },
    finalizeAnnotations(taskId, body) { return command(taskId, "/annotations/finalize", body); },
    submitReview(taskId, body) { return command(taskId, "/review", body); },
    cancel(taskId) { return command(taskId, "/cancel"); },
    exportUrl(taskId) { return taskUrl(options.apiBase, taskId, "/export"); },
  };
}
