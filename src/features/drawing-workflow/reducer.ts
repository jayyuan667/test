import type {
  ProcessOperation,
  TaskEvent,
  TaskSnapshot,
  WorkflowConnection,
  WorkflowError,
  WorkflowState,
} from "./types.ts";

export type WorkflowAction =
  | TaskEvent
  | { type: "snapshot_received"; snapshot: TaskSnapshot }
  | { type: "connection_changed"; connection: WorkflowConnection }
  | { type: "error_received"; error: WorkflowError | null };

const phaseOrder: Record<TaskSnapshot["task"]["phase"], number> = {
  upload: 0, drawing_analysis: 1, annotation: 2, feature_review: 3,
  process_generation: 4, export: 5, done: 6,
};

export function createInitialWorkflowState(snapshot: TaskSnapshot | null = null): WorkflowState {
  const operations = snapshot?.process_operations ?? [];
  return {
    snapshot,
    operationsById: Object.fromEntries(operations.map((operation) => [operation.id, operation])),
    operationOrder: operations.map((operation) => operation.id),
    lastSeq: snapshot?.task.revision ?? 0,
    connection: "idle",
    error: snapshot?.task.error ?? null,
  };
}

function replaceSnapshot(state: WorkflowState, snapshot: TaskSnapshot): WorkflowState {
  if (state.snapshot && snapshot.task.revision <= state.snapshot.task.revision) return state;
  const operations = snapshot.process_operations;
  return {
    ...state,
    snapshot,
    operationsById: Object.fromEntries(operations.map((operation) => [operation.id, operation])),
    operationOrder: operations.map((operation) => operation.id),
    lastSeq: Math.max(state.lastSeq, snapshot.task.revision),
    error: snapshot.task.error,
  };
}

function updateSnapshotTask(
  snapshot: TaskSnapshot | null,
  changes: Partial<TaskSnapshot["task"]>,
): TaskSnapshot | null {
  return snapshot ? { ...snapshot, task: { ...snapshot.task, ...changes } } : null;
}

function upsertOperation(state: WorkflowState, operation: ProcessOperation): WorkflowState {
  const exists = Object.hasOwn(state.operationsById, operation.id);
  return {
    ...state,
    operationsById: { ...state.operationsById, [operation.id]: operation },
    operationOrder: exists ? state.operationOrder : [...state.operationOrder, operation.id],
  };
}

export function reduceWorkflowState(state: WorkflowState, action: WorkflowAction): WorkflowState {
  if (action.type === "snapshot_received") return replaceSnapshot(state, action.snapshot);
  if (action.type === "connection_changed") return { ...state, connection: action.connection };
  if (action.type === "error_received") return { ...state, error: action.error };
  if (action.seq <= state.lastSeq) return state;

  let next = { ...state, lastSeq: action.seq };
  const snapshot = action.payload.snapshot;
  if (snapshot) next = replaceSnapshot(next, snapshot);

  if (action.type === "operation_upserted" && action.payload.operation) {
    next = upsertOperation(next, action.payload.operation);
  }
  if (action.type === "feature_ready" && action.payload.feature && next.snapshot) {
    const features = next.snapshot.features;
    const index = features.findIndex((feature) => feature.id === action.payload.feature?.id);
    const merged = index < 0 ? [...features, action.payload.feature] : features.map((feature, position) => position === index ? action.payload.feature! : feature);
    next = { ...next, snapshot: { ...next.snapshot, features: merged } };
  }

  if (action.type === "phase_started" || action.type === "phase_progress" || action.type === "phase_completed") {
    const current = next.snapshot?.task;
    const phase = current && phaseOrder[action.phase] < phaseOrder[current.phase] ? current.phase : action.phase;
    const progress = current ? Math.max(current.progress, action.progress) : action.progress;
    next = { ...next, snapshot: updateSnapshotTask(next.snapshot, { phase, progress }) };
  } else if (action.type === "task_completed") {
    next = {
      ...next,
      snapshot: updateSnapshotTask(next.snapshot, { state: "completed", phase: "done", progress: action.progress, error: null }),
      error: null,
    };
  } else if (action.type === "task_failed") {
    const error = action.payload.error ?? null;
    const current = next.snapshot?.task;
    next = {
      ...next,
      snapshot: updateSnapshotTask(next.snapshot, { state: action.payload.status === "cancelled" || action.payload.state === "cancelled" ? "cancelled" : "failed", phase: current && phaseOrder[action.phase] < phaseOrder[current.phase] ? current.phase : action.phase, progress: current ? Math.max(current.progress, action.progress) : action.progress, error }),
      error,
    };
  }
  return next;
}
