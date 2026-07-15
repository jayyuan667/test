import { createInitialWorkflowState, reduceWorkflowState } from "./reducer.ts";
import type { DrawingWorkflowClient, EventConnection, TaskEvent, WorkflowState } from "./types.ts";

export interface DrawingWorkflowController {
  start(taskId: string): Promise<void>;
  getState(): WorkflowState;
  subscribe(listener: (state: WorkflowState) => void): () => void;
  dispose(): void;
}

export interface ControllerOptions {
  scheduleReconnect?: (callback: () => void) => () => void;
}

export function createDrawingWorkflowController(
  client: DrawingWorkflowClient,
  options: ControllerOptions = {},
): DrawingWorkflowController {
  const scheduleReconnect = options.scheduleReconnect ?? ((callback) => {
    const timer = setTimeout(callback, 1_500);
    return () => clearTimeout(timer);
  });
  const listeners = new Set<(state: WorkflowState) => void>();
  let state = createInitialWorkflowState();
  let taskId: string | null = null;
  let connection: EventConnection | null = null;
  let cancelReconnect: (() => void) | null = null;
  let disposed = false;

  const publish = (next: WorkflowState) => {
    state = next;
    listeners.forEach((listener) => listener(state));
  };

  const openConnection = () => {
    if (!taskId || disposed) return;
    connection?.close();
    publish(reduceWorkflowState(state, { type: "connection_changed", connection: state.lastSeq ? "reconnecting" : "connecting" }));
    connection = client.connect(taskId, state.lastSeq, (event: TaskEvent) => {
      publish(reduceWorkflowState(state, event));
      publish(reduceWorkflowState(state, { type: "connection_changed", connection: "connected" }));
    }, () => {
      connection?.close();
      connection = null;
      if (disposed) return;
      publish(reduceWorkflowState(state, { type: "connection_changed", connection: "reconnecting" }));
      cancelReconnect?.();
      cancelReconnect = scheduleReconnect(openConnection);
    });
  };

  return {
    async start(nextTaskId) {
      taskId = nextTaskId;
      const snapshot = await client.getSnapshot(nextTaskId);
      if (disposed || taskId !== nextTaskId) return;
      publish(reduceWorkflowState(state, { type: "snapshot_received", snapshot }));
      openConnection();
    },
    getState: () => state,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    dispose() {
      disposed = true;
      cancelReconnect?.();
      connection?.close();
      connection = null;
      listeners.clear();
      publish(reduceWorkflowState(state, { type: "connection_changed", connection: "closed" }));
    },
  };
}
