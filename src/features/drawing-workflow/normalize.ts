import type { Feature, ProcessOperation, TaskEvent, TaskEventType, TaskPhase, TaskSnapshot, TaskState, WorkflowError } from "./types.ts";

const states = new Set<TaskState>(["pending", "processing", "awaiting_annotation", "awaiting_review", "completed", "failed", "cancelled"]);
const phases = new Set<TaskPhase>(["upload", "drawing_analysis", "annotation", "feature_review", "process_generation", "export", "done"]);
const eventTypes = new Set<TaskEventType>(["phase_started", "phase_progress", "feature_ready", "operation_upserted", "phase_completed", "task_completed", "task_failed", "heartbeat"]);
const featureKinds = new Set<Feature["kind"]>(["diameter", "length", "thread", "tolerance", "surface", "material", "requirement", "geometry", "identifier", "unknown"]);
const featureStatuses = new Set<Feature["review_status"]>(["unreviewed", "confirmed", "modified", "rejected"]);
const operationStatuses = new Set<ProcessOperation["status"]>(["draft", "streaming", "complete", "modified"]);
const sourceKinds = new Set<TaskSnapshot["drawing"]["source_kind"]>(["png", "jpg", "pdf", "dxf", "prt", "unknown"]);
const reviewStatuses = new Set<TaskSnapshot["review"]["status"]>(["not_ready", "pending", "confirmed", "modified"]);
const record = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const string = (value: unknown, fallback = "") => typeof value === "string" ? value : fallback;
const number = (value: unknown, fallback = 0) => typeof value === "number" && Number.isFinite(value) ? value : fallback;
const nullableString = (value: unknown) => typeof value === "string" ? value : null;

function normalizeError(value: unknown): WorkflowError | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const item = record(value);
  return { code: string(item.code, "TASK_FAILED"), message: string(item.message, "Task failed"), retryable: item.retryable === true, phase: phases.has(item.phase as TaskPhase) ? item.phase as TaskPhase : null, details: record(item.details) };
}

function normalizeFeature(value: unknown, index: number): Feature {
  const item = record(value); const tolerance = record(item.tolerance); const source = record(item.source);
  const methods = new Set(["vlm", "ocr", "yolo", "geometry", "combined", "legacy_text"]);
  return {
    id: string(item.id, `feature-${index}`), kind: featureKinds.has(item.kind as Feature["kind"]) ? item.kind as Feature["kind"] : "unknown", label: string(item.label), value: nullableString(item.value), unit: nullableString(item.unit),
    tolerance: { upper: typeof tolerance.upper === "number" ? tolerance.upper : null, lower: typeof tolerance.lower === "number" ? tolerance.lower : null, text: nullableString(tolerance.text) },
    source: { method: methods.has(String(source.method)) ? source.method as Feature["source"]["method"] : null, page: typeof source.page === "number" && Number.isFinite(source.page) && source.page >= 0 ? source.page : null, bbox: Array.isArray(source.bbox) && source.bbox.length === 4 && source.bbox.every((entry) => typeof entry === "number" && Number.isFinite(entry)) ? source.bbox as [number, number, number, number] : null, evidence_text: nullableString(source.evidence_text) },
    confidence: typeof item.confidence === "number" && Number.isFinite(item.confidence) && item.confidence >= 0 && item.confidence <= 1 ? item.confidence : null, review_status: featureStatuses.has(item.review_status as Feature["review_status"]) ? item.review_status as Feature["review_status"] : "unreviewed", missing_reason: nullableString(item.missing_reason),
  };
}

function normalizeOperation(value: unknown, index: number): ProcessOperation {
  const item = record(value);
  return { id: string(item.id, `operation-${index}`), code: string(item.code), trade: nullableString(item.trade), content: string(item.content), equipment: Array.isArray(item.equipment) ? item.equipment.filter((entry): entry is string => typeof entry === "string") : [], duration_minutes: typeof item.duration_minutes === "number" && Number.isFinite(item.duration_minutes) && item.duration_minutes >= 0 ? item.duration_minutes : null, parameters: Array.isArray(item.parameters) ? item.parameters : [], note: nullableString(item.note), status: operationStatuses.has(item.status as ProcessOperation["status"]) ? item.status as ProcessOperation["status"] : "draft" };
}

export function normalizeTaskSnapshot(value: unknown): TaskSnapshot | null {
  const root = record(value); const task = record(root.task); const drawing = record(root.drawing); const review = record(root.review);
  if (root.schema_version !== "1.0" || typeof task.id !== "string") return null;
  const state = states.has(task.state as TaskState) ? task.state as TaskState : "pending";
  return {
    schema_version: "1.0",
    task: { id: task.id, state, phase: phases.has(task.phase as TaskPhase) ? task.phase as TaskPhase : "upload", progress: typeof task.progress === "number" && Number.isFinite(task.progress) && task.progress >= 0 && task.progress <= 100 ? task.progress : 0, revision: typeof task.revision === "number" && Number.isInteger(task.revision) && task.revision >= 0 ? task.revision : 0, created_at: nullableString(task.created_at), updated_at: nullableString(task.updated_at), error: state === "completed" ? null : normalizeError(task.error) },
    drawing: { name: string(drawing.name), source_kind: sourceKinds.has(drawing.source_kind as TaskSnapshot["drawing"]["source_kind"]) ? drawing.source_kind as TaskSnapshot["drawing"]["source_kind"] : "unknown", page_count: typeof drawing.page_count === "number" && Number.isInteger(drawing.page_count) && drawing.page_count > 0 ? drawing.page_count : 1, preview_urls: Array.isArray(drawing.preview_urls) ? drawing.preview_urls.filter((entry): entry is string => typeof entry === "string") : [] },
    features: Array.isArray(root.features) ? root.features.map(normalizeFeature) : [], review: { status: reviewStatuses.has(review.status as TaskSnapshot["review"]["status"]) ? review.status as TaskSnapshot["review"]["status"] : "not_ready", raw_text: nullableString(review.raw_text) },
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
  if (payload.snapshot) {
    const snapshot = normalizeTaskSnapshot(payload.snapshot);
    if (snapshot) payload.snapshot = snapshot;
    else delete payload.snapshot;
  }
  return { schema_version: "1.0", seq: item.seq as number, task_id: item.task_id, type: item.type as TaskEventType, phase: phases.has(item.phase as TaskPhase) ? item.phase as TaskPhase : "drawing_analysis", progress: typeof item.progress === "number" && Number.isFinite(item.progress) && item.progress >= 0 && item.progress <= 100 ? item.progress : 0, timestamp: string(item.timestamp), payload };
}
