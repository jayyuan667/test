import { createInitialWorkflowState, reduceWorkflowState } from "./reducer.ts";
import type { DrawingWorkflowClient, EventConnection, TaskEvent, WorkflowState } from "./types.ts";

export interface DrawingWorkflowController {
  start(taskId: string): Promise<void>;
  getState(): WorkflowState;
  subscribe(listener: (state: WorkflowState) => void): () => void;
  dispose(): void;
}

export interface ControllerOptions {
  scheduleReconnect?: (callback: () => void, delayMs: number) => () => void;
  random?: () => number;
  maxReconnectDelay?: number;
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

  const publish = (next: WorkflowState) => { state = next; listeners.forEach((listener) => listener(state)); };
  const cleanup = () => { cancelReconnect?.(); cancelReconnect = null; connection?.close(); connection = null; };

  const openConnection = (expectedGeneration: number) => {
    if (!activeTask || disposed || terminal || expectedGeneration !== generation) return;
    connection?.close();
    const taskId = activeTask;
    publish(reduceWorkflowState(state, { type: "connection_changed", connection: state.lastSeq ? "reconnecting" : "connecting" }));
    connection = client.connect(taskId, state.lastSeq, (event: TaskEvent) => {
      if (disposed || terminal || expectedGeneration !== generation || event.task_id !== taskId) return;
      publish(reduceWorkflowState(state, event));
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
    getState: () => state,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    dispose() {
      if (disposed) return;
      disposed = true; generation += 1; cleanup();
      publish(reduceWorkflowState(state, { type: "connection_changed", connection: "closed" }));
      listeners.clear();
    },
  };
}
