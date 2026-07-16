import type { TaskSnapshot } from "@/features/drawing-workflow/types";

export type WorkflowStepId = "upload" | "annotation" | "review" | "process";

export const WORKFLOW_STEPS = [
  { id: "upload", number: "01", label: "上传图纸" },
  { id: "annotation", number: "02", label: "特征标注" },
  { id: "review", number: "03", label: "审阅确认" },
  { id: "process", number: "04", label: "工艺生成" },
] as const;

const order = Object.fromEntries(
  WORKFLOW_STEPS.map((step, index) => [step.id, index]),
) as Record<WorkflowStepId, number>;

export function reachedStepForSnapshot(snapshot: TaskSnapshot | null): WorkflowStepId {
  if (!snapshot) return "upload";
  if (
    snapshot.task.state === "completed"
    || snapshot.task.phase === "process_generation"
    || snapshot.task.phase === "export"
    || snapshot.task.phase === "done"
    || snapshot.process_operations.length > 0
  ) return "process";
  // Explicit command-owning states win over collection presence. Annotation
  // snapshots normally already contain features, but must stay on step 02.
  if (snapshot.task.state === "awaiting_annotation" || snapshot.task.phase === "annotation") return "annotation";
  if (snapshot.task.state === "awaiting_review" || snapshot.task.phase === "feature_review" || snapshot.features.length > 0) return "review";
  if (snapshot.drawing.preview_urls.length > 0) return "annotation";
  return "upload";
}

export function canInspectStep(target: WorkflowStepId, reached: WorkflowStepId): boolean {
  return order[target] <= order[reached];
}
