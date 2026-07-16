import { createInitialWorkflowState, reduceWorkflowState } from "./reducer.ts";
import type { DrawingWorkflowClient, EventConnection, TaskEvent, WorkflowState } from "./types.ts";

export interface DrawingWorkflowController {
  upload(file: File | Blob): Promise<void>;
  start(taskId: string): Promise<void>;
  finalizeAnnotations(body?: unknown): Promise<void>;
  submitReview(body: unknown): Promise<void>;
  cancel(): Promise<void>;
  exportUrl(): string;
  loadPreview(url: string): Promise<string>;
  getState(): WorkflowState;
  subscribe(listener: (state: WorkflowState) => void): () => void;
  dispose(): void;
}

export interface ControllerOptions {
  scheduleReconnect?: (callback: () => void, delayMs: number) => () => void;
  random?: () => number;
  maxReconnectDelay?: number;
  createObjectURL?: (blob: Blob) => string;
  revokeObjectURL?: (url: string) => void;
}

const terminalStates = new Set(["completed", "failed", "cancelled"]);

export function createDrawingWorkflowController(client: DrawingWorkflowClient, options: ControllerOptions = {}): DrawingWorkflowController {
  const scheduleReconnect = options.scheduleReconnect ?? ((callback, delayMs) => { const timer = setTimeout(callback, delayMs); return () => clearTimeout(timer); });
  const random = options.random ?? Math.random;
  const maxDelay = options.maxReconnectDelay ?? 30_000;
  const listeners = new Set<(state: WorkflowState) => void>();
  let state = createInitialWorkflowState();
  let activeTask: string | null = null;
  let connection: EventConnection | null = null;
  let cancelReconnect: (() => void) | null = null;
  let generation = 0;
  let reconnectAttempt = 0;
  let reconnectBase = 1_000;
  let disposed = false;
  let terminal = false;
  const previewUrls = new Set<string>();
  const createObjectURL = options.createObjectURL ?? ((blob) => URL.createObjectURL(blob));
  const revokeObjectURL = options.revokeObjectURL ?? ((url) => URL.revokeObjectURL(url));

  const publish = (next: WorkflowState) => { state = next; listeners.forEach((listener) => listener(state)); };
  const cleanup = () => { cancelReconnect?.(); cancelReconnect = null; connection?.close(); connection = null; };
  const refreshSnapshot = async (taskId: string, expectedGeneration: number) => {
    try {
      const snapshot = await client.getSnapshot(taskId);
      if (!disposed && expectedGeneration === generation && activeTask === taskId) {
        publish(reduceWorkflowState(state, { type: "snapshot_received", snapshot }));
      }
    } catch { /* the stream remains authoritative; reconnect can retry recovery */ }
  };

  const openConnection = (expectedGeneration: number) => {
    if (!activeTask || disposed || terminal || expectedGeneration !== generation) return;
    connection?.close();
    const taskId = activeTask;
    publish(reduceWorkflowState(state, { type: "connection_changed", connection: state.lastSeq ? "reconnecting" : "connecting" }));
    connection = client.connect(taskId, state.lastSeq, (event: TaskEvent) => {
      if (disposed || terminal || expectedGeneration !== generation || event.task_id !== taskId) return;
      publish(reduceWorkflowState(state, event));
      const legacyType = event.payload.legacy_type;
      if (legacyType === "annotation_required" || legacyType === "review_required" || event.type === "task_completed") {
        void refreshSnapshot(taskId, expectedGeneration);
      }
      const taskState = state.snapshot?.task.state;
      terminal = event.type === "task_completed" || event.type === "task_failed" || (taskState ? terminalStates.has(taskState) : false);
      if (terminal) {
        connection?.close(); connection = null;
        publish(reduceWorkflowState(state, { type: "connection_changed", connection: "closed" }));
      } else {
        reconnectAttempt = 0;
        publish(reduceWorkflowState(state, { type: "connection_changed", connection: "connected" }));
      }
    }, (disconnect) => {
      if (expectedGeneration !== generation) return;
      connection?.close(); connection = null;
      if (disposed || terminal) return;
      if (disconnect.error) publish(reduceWorkflowState(state, { type: "error_received", error: disconnect.error }));
      if (!disconnect.retryable || disconnect.status === 401 || disconnect.status === 403) {
        terminal = true;
        publish(reduceWorkflowState(state, { type: "connection_changed", connection: "closed" }));
        return;
      }
      publish(reduceWorkflowState(state, { type: "connection_changed", connection: "reconnecting" }));
      if (typeof disconnect.retryMs === "number" && Number.isFinite(disconnect.retryMs) && disconnect.retryMs >= 0) reconnectBase = Math.min(maxDelay, disconnect.retryMs);
      const base = Math.min(maxDelay, reconnectBase * (2 ** reconnectAttempt));
      const delay = Math.min(maxDelay, Math.round(base * (1 + Math.max(0, random()) * 0.2)));
      reconnectAttempt += 1;
      cancelReconnect?.();
      cancelReconnect = scheduleReconnect(() => openConnection(expectedGeneration), delay);
    });
  };

  return {
    async upload(file) {
      const snapshot = await client.upload(file);
      await this.start(snapshot.task.id);
    },
    async start(taskId) {
      generation += 1;
      const expectedGeneration = generation;
      cleanup();
      activeTask = taskId;
      reconnectAttempt = 0;
      reconnectBase = 1_000;
      terminal = false;
      publish(createInitialWorkflowState());
      const snapshot = await client.getSnapshot(taskId);
      if (disposed || expectedGeneration !== generation || activeTask !== taskId) return;
      publish(reduceWorkflowState(state, { type: "snapshot_received", snapshot }));
      terminal = terminalStates.has(snapshot.task.state);
      if (!terminal) openConnection(expectedGeneration);
      else publish(reduceWorkflowState(state, { type: "connection_changed", connection: "closed" }));
    },
    async finalizeAnnotations(body) {
      if (!activeTask) throw new Error("No active workflow task");
      const taskId = activeTask; const expectedGeneration = generation;
      const snapshot = await client.finalizeAnnotations(taskId, body);
      if (disposed || expectedGeneration !== generation || activeTask !== taskId) return;
      publish(reduceWorkflowState(state, { type: "snapshot_received", snapshot }));
    },
    async submitReview(body) {
      if (!activeTask) throw new Error("No active workflow task");
      const taskId = activeTask; const expectedGeneration = generation;
      const snapshot = await client.submitReview(taskId, body);
      if (disposed || expectedGeneration !== generation || activeTask !== taskId) return;
      publish(reduceWorkflowState(state, { type: "snapshot_received", snapshot }));
    },
    async cancel() {
      if (!activeTask) throw new Error("No active workflow task");
      const taskId = activeTask; const expectedGeneration = generation;
      const snapshot = await client.cancel(taskId);
      if (disposed || expectedGeneration !== generation || activeTask !== taskId) return;
      publish(reduceWorkflowState(state, { type: "snapshot_received", snapshot }));
      terminal = true;
      cleanup();
    },
    exportUrl() {
      if (!activeTask) throw new Error("No active workflow task");
      return client.exportUrl(activeTask);
    },
    async loadPreview(url) {
      if (!activeTask) throw new Error("No active workflow task");
      const expectedGeneration = generation;
      const taskId = activeTask;
      const blob = await client.getAsset(taskId, url);
      if (disposed || expectedGeneration !== generation) return "";
      const objectUrl = createObjectURL(blob); previewUrls.add(objectUrl); return objectUrl;
    },
    getState: () => state,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    dispose() {
      if (disposed) return;
      disposed = true; generation += 1; cleanup();
      previewUrls.forEach(revokeObjectURL); previewUrls.clear();
      publish(reduceWorkflowState(state, { type: "connection_changed", connection: "closed" }));
      listeners.clear();
    },
  };
}
