import type { Feature, ProcessOperation, TaskEvent, TaskEventType, TaskPhase, TaskSnapshot, TaskState, WorkflowError } from "./types.ts";

const states = new Set<TaskState>(["pending", "processing", "awaiting_annotation", "awaiting_review", "completed", "failed", "cancelled"]);
const phases = new Set<TaskPhase>(["upload", "drawing_analysis", "annotation", "feature_review", "process_generation", "export", "done"]);
const eventTypes = new Set<TaskEventType>(["phase_started", "phase_progress", "feature_ready", "operation_upserted", "phase_completed", "task_completed", "task_failed", "heartbeat"]);
const record = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const string = (value: unknown, fallback = "") => typeof value === "string" ? value : fallback;
const number = (value: unknown, fallback = 0) => typeof value === "number" && Number.isFinite(value) ? value : fallback;
const nullableString = (value: unknown) => typeof value === "string" ? value : null;

function normalizeError(value: unknown): WorkflowError | null {
  if (value == null) return null;
  const item = record(value);
  return { code: string(item.code, "TASK_FAILED"), message: string(item.message, "Task failed"), retryable: item.retryable === true, phase: phases.has(item.phase as TaskPhase) ? item.phase as TaskPhase : null, details: record(item.details) };
}

function normalizeFeature(value: unknown, index: number): Feature {
  const item = record(value); const tolerance = record(item.tolerance); const source = record(item.source);
  const methods = new Set(["vlm", "ocr", "yolo", "geometry", "combined", "legacy_text"]);
  return {
    id: string(item.id, `feature-${index}`), kind: string(item.kind, "unknown") as Feature["kind"], label: string(item.label), value: nullableString(item.value), unit: nullableString(item.unit),
    tolerance: { upper: typeof tolerance.upper === "number" ? tolerance.upper : null, lower: typeof tolerance.lower === "number" ? tolerance.lower : null, text: nullableString(tolerance.text) },
    source: { method: methods.has(String(source.method)) ? source.method as Feature["source"]["method"] : null, page: typeof source.page === "number" ? source.page : null, bbox: Array.isArray(source.bbox) && source.bbox.length === 4 ? source.bbox as [number, number, number, number] : null, evidence_text: nullableString(source.evidence_text) },
    confidence: typeof item.confidence === "number" ? item.confidence : null, review_status: string(item.review_status, "unreviewed") as Feature["review_status"], missing_reason: nullableString(item.missing_reason),
  };
}

function normalizeOperation(value: unknown, index: number): ProcessOperation {
  const item = record(value);
  return { id: string(item.id, `operation-${index}`), code: string(item.code), trade: nullableString(item.trade), content: string(item.content), equipment: Array.isArray(item.equipment) ? item.equipment.filter((entry): entry is string => typeof entry === "string") : [], duration_minutes: typeof item.duration_minutes === "number" ? item.duration_minutes : null, parameters: Array.isArray(item.parameters) ? item.parameters : [], note: nullableString(item.note), status: string(item.status, "draft") as ProcessOperation["status"] };
}

export function normalizeTaskSnapshot(value: unknown): TaskSnapshot | null {
  const root = record(value); const task = record(root.task); const drawing = record(root.drawing); const review = record(root.review);
  if (root.schema_version !== "1.0" || typeof task.id !== "string") return null;
  return {
    schema_version: "1.0",
    task: { id: task.id, state: states.has(task.state as TaskState) ? task.state as TaskState : "pending", phase: phases.has(task.phase as TaskPhase) ? task.phase as TaskPhase : "upload", progress: number(task.progress), revision: number(task.revision), created_at: nullableString(task.created_at), updated_at: nullableString(task.updated_at), error: normalizeError(task.error) },
    drawing: { name: string(drawing.name), source_kind: string(drawing.source_kind, "unknown") as TaskSnapshot["drawing"]["source_kind"], page_count: number(drawing.page_count, 1), preview_urls: Array.isArray(drawing.preview_urls) ? drawing.preview_urls.filter((entry): entry is string => typeof entry === "string") : [] },
    features: Array.isArray(root.features) ? root.features.map(normalizeFeature) : [], review: { status: string(review.status, "not_ready") as TaskSnapshot["review"]["status"], raw_text: nullableString(review.raw_text) },
    process_operations: Array.isArray(root.process_operations) ? root.process_operations.map(normalizeOperation) : [], reuse_candidates: Array.isArray(root.reuse_candidates) ? root.reuse_candidates : [], capabilities: record(root.capabilities),
  };
}

export function normalizeTaskEvent(value: unknown): TaskEvent | null {
  const item = record(value);
  if (item.schema_version !== "1.0" || !Number.isInteger(item.seq) || number(item.seq, -1) < 0 || typeof item.task_id !== "string" || !eventTypes.has(item.type as TaskEventType)) return null;
  const payload = record(item.payload);
  if (payload.feature) payload.feature = normalizeFeature(payload.feature, 0);
  if (payload.operation) payload.operation = normalizeOperation(payload.operation, 0);
  if (payload.error) payload.error = normalizeError(payload.error);
  if (payload.snapshot) payload.snapshot = normalizeTaskSnapshot(payload.snapshot);
  return { schema_version: "1.0", seq: item.seq as number, task_id: item.task_id, type: item.type as TaskEventType, phase: phases.has(item.phase as TaskPhase) ? item.phase as TaskPhase : "drawing_analysis", progress: number(item.progress), timestamp: string(item.timestamp), payload };
}
