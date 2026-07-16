import assert from "node:assert/strict";
import test from "node:test";
import type { Feature, ProcessOperation, TaskSnapshot, TaskState } from "../../features/drawing-workflow/types.ts";
import { canInspectStep, reachedStepForSnapshot } from "./workflow-step-model.ts";

const feature: Feature = {
  id: "feature-1",
  kind: "diameter",
  label: "Diameter",
  value: "10",
  unit: "mm",
  tolerance: { upper: null, lower: null, text: null },
  source: { method: "ocr", page: 1, bbox: null, evidence_text: null },
  confidence: 0.9,
  review_status: "unreviewed",
  missing_reason: null,
};

const operation: ProcessOperation = {
  id: "operation-1",
  code: "OP-10",
  trade: null,
  content: "Machine part",
  equipment: [],
  duration_minutes: null,
  parameters: [],
  note: null,
  status: "complete",
};

function snapshot(
  state: TaskState,
  preview_urls: string[] = [],
  features: Feature[] = [],
  process_operations: ProcessOperation[] = [],
): TaskSnapshot {
  return {
    schema_version: "1.0",
    task: {
      id: "task-1",
      state,
      phase: "upload",
      progress: 0,
      revision: 1,
      created_at: null,
      updated_at: null,
      error: null,
    },
    drawing: {
      name: "drawing.png",
      source_kind: "png",
      page_count: preview_urls.length,
      preview_urls,
    },
    features,
    review: { status: "not_ready", raw_text: null },
    process_operations,
    reuse_candidates: [],
    capabilities: {},
  };
}

test("maps backend states to the highest reached workstation step", () => {
  assert.equal(reachedStepForSnapshot(null), "upload");
  assert.equal(reachedStepForSnapshot(snapshot("processing")), "upload");
  assert.equal(reachedStepForSnapshot(snapshot("processing", ["/preview.png"])), "annotation");
  assert.equal(reachedStepForSnapshot(snapshot("awaiting_annotation", ["/preview.png"])), "annotation");
  assert.equal(reachedStepForSnapshot(snapshot("awaiting_review", [], [feature])), "review");
  assert.equal(reachedStepForSnapshot(snapshot("completed", [], [], [operation])), "process");
});

test("allows inspecting completed steps but never future steps", () => {
  assert.equal(canInspectStep("upload", "review"), true);
  assert.equal(canInspectStep("annotation", "review"), true);
  assert.equal(canInspectStep("process", "review"), false);
});
