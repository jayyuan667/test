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
  if (snapshot.task.state === "completed" || snapshot.process_operations.length > 0) return "process";
  if (snapshot.task.state === "awaiting_review" || snapshot.features.length > 0) return "review";
  if (snapshot.task.state === "awaiting_annotation" || snapshot.drawing.preview_urls.length > 0) return "annotation";
  return "upload";
}

export function canInspectStep(target: WorkflowStepId, reached: WorkflowStepId): boolean {
  return order[target] <= order[reached];
}
