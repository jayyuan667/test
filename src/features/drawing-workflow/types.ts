export type TaskState =
  | "pending"
  | "processing"
  | "awaiting_annotation"
  | "awaiting_review"
  | "completed"
  | "failed"
  | "cancelled";

export type TaskPhase =
  | "upload"
  | "drawing_analysis"
  | "annotation"
  | "feature_review"
  | "process_generation"
  | "export"
  | "done";

export interface WorkflowError {
  code: string;
  message: string;
  retryable: boolean;
  phase: TaskPhase | null;
  details: Record<string, unknown>;
}

export interface Feature {
  id: string;
  kind:
    | "diameter"
    | "length"
    | "thread"
    | "tolerance"
    | "surface"
    | "material"
    | "requirement"
    | "geometry"
    | "identifier"
    | "unknown";
  label: string;
  value: string | null;
  unit: string | null;
  tolerance: { upper: number | null; lower: number | null; text: string | null };
  source: {
    method: "vlm" | "ocr" | "yolo" | "geometry" | "combined" | "legacy_text" | null;
    page: number | null;
    bbox: [number, number, number, number] | null;
    evidence_text: string | null;
  };
  confidence: number | null;
  review_status: "unreviewed" | "confirmed" | "modified" | "rejected";
  missing_reason: string | null;
}

export interface ProcessOperation {
  id: string;
  code: string;
  trade: string | null;
  content: string;
  equipment: string[];
  duration_minutes: number | null;
  parameters: unknown[];
  note: string | null;
  evidence_features: Feature[];
  status: "draft" | "streaming" | "complete" | "modified";
}

export interface TaskSnapshot {
  schema_version: "1.0";
  task: {
    id: string;
    state: TaskState;
    phase: TaskPhase;
    progress: number;
    revision: number;
    created_at: string | null;
    updated_at: string | null;
    error: WorkflowError | null;
  };
  drawing: {
    name: string;
    source_kind: "png" | "jpg" | "pdf" | "dxf" | "prt" | "unknown";
    page_count: number;
    preview_urls: string[];
  };
  features: Feature[];
  review: {
    status: "not_ready" | "pending" | "confirmed" | "modified";
    raw_text: string | null;
  };
  process_operations: ProcessOperation[];
  reuse_candidates: unknown[];
  capabilities: Record<string, unknown>;
}

export type TaskEventType =
  | "phase_started"
  | "phase_progress"
  | "feature_ready"
  | "operation_upserted"
  | "phase_completed"
  | "task_completed"
  | "task_failed"
  | "heartbeat";

export interface TaskEvent {
  schema_version: "1.0";
  seq: number;
  task_id: string;
  type: TaskEventType;
  phase: TaskPhase;
  progress: number;
  timestamp: string;
  payload: {
    operation?: ProcessOperation;
    feature?: Feature;
    error?: WorkflowError;
    snapshot?: TaskSnapshot;
    [key: string]: unknown;
  };
}

export type WorkflowConnection = "idle" | "connecting" | "connected" | "reconnecting" | "closed";

export interface WorkflowState {
  snapshot: TaskSnapshot | null;
  operationsById: Record<string, ProcessOperation>;
  operationOrder: string[];
  lastSeq: number;
  connection: WorkflowConnection;
  error: WorkflowError | null;
}

export interface EventConnection {
  close(): void;
}

export interface StreamDisconnect {
  retryable: boolean;
  status?: number;
  error?: WorkflowError;
  retryMs?: number;
}

export interface DrawingWorkflowClient {
  upload(file: File | Blob): Promise<TaskSnapshot>;
  getSnapshot(taskId: string): Promise<TaskSnapshot>;
  getAsset(taskId: string, url: string): Promise<Blob>;
  connect(taskId: string, after: number, onEvent: (event: TaskEvent) => void, onDisconnect?: (disconnect: StreamDisconnect) => void): EventConnection;
  finalizeAnnotations(taskId: string, body?: unknown): Promise<TaskSnapshot>;
  submitReview(taskId: string, body: unknown): Promise<TaskSnapshot>;
  cancel(taskId: string): Promise<TaskSnapshot>;
  exportUrl(taskId: string): string;
}
