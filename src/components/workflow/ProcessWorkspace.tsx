import type {
  ProcessOperation,
  TaskPhase,
  TaskState,
  WorkflowConnection,
  WorkflowError,
} from "@/features/drawing-workflow/types";

import { WorkflowFeedback } from "./WorkflowFeedback";
import { WorkflowWaitingPanel } from "./WorkflowWaitingPanel";

interface ProcessWorkspaceProps {
  operations: ProcessOperation[];
  taskState: TaskState;
  phase: TaskPhase;
  progress: number;
  connection: WorkflowConnection;
  error: WorkflowError | null;
  onExport: () => void;
}

const phaseLabels: Record<TaskPhase, string> = {
  upload: "正在上传图纸",
  drawing_analysis: "正在解析图纸",
  annotation: "正在整理特征标注",
  feature_review: "正在准备审阅结果",
  process_generation: "正在生成工艺",
  export: "正在准备导出文件",
  done: "工艺生成已完成",
};

function operationSource(operation: ProcessOperation): string {
  // The v1 operation contract has no dedicated source field. A note remains a
  // note; when it is absent we say so instead of deriving evidence from content.
  return operation.note?.trim() || "来源未提供";
}

export function ProcessWorkspace({
  operations,
  taskState,
  phase,
  progress,
  connection,
  error,
  onExport,
}: ProcessWorkspaceProps) {
  const completed = taskState === "completed";
  const normalizedProgress = Math.min(100, Math.max(0, progress));

  return (
    <section className="forge-process" aria-labelledby="forge-process-title" data-testid="workflow-status">
      <header className="forge-process__header">
        <div>
          <p className="forge-eyebrow">PROCESS / ROUTE</p>
          <h2 id="forge-process-title">结构化工艺路线</h2>
          <p data-testid="workflow-phase" data-phase={phase}>{phaseLabels[phase]}</p>
        </div>
        <div className="forge-process__progress">
          <span data-testid="workflow-progress-value">完成度 {normalizedProgress}%</span>
          <progress value={normalizedProgress} max={100}>{normalizedProgress}%</progress>
        </div>
      </header>

      <WorkflowFeedback state={taskState} connection={connection} error={error} />
      {taskState === "processing" ? (
        <WorkflowWaitingPanel phase={phase} progress={normalizedProgress} connection={connection} />
      ) : null}

      <div className="forge-process__table-wrap">
        <table className="forge-process__table" data-testid="operation-table">
          <thead>
            <tr>
              <th scope="col">工序</th>
              <th scope="col">工种</th>
              <th scope="col">加工内容</th>
              <th scope="col">设备</th>
              <th scope="col">工时</th>
              <th scope="col">依据 / 备注</th>
            </tr>
          </thead>
          <tbody>
            {operations.map((operation) => (
              <tr data-testid="operation-row" key={operation.id}>
                <td data-label="工序"><strong>{operation.code || "编号未提供"}</strong></td>
                <td data-label="工种">{operation.trade ?? "工种未提供"}</td>
                <td data-label="加工内容">{operation.content || "内容未提供"}</td>
                <td data-label="设备">{operation.equipment.length ? operation.equipment.join("、") : "设备未提供"}</td>
                <td data-label="工时">{operation.duration_minutes === null ? "工时未提供" : `${operation.duration_minutes} 分钟`}</td>
                <td data-label="依据 / 备注">{operationSource(operation)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {operations.length === 0 ? (
          <p className="forge-process__empty">结构化工序将在生成后显示</p>
        ) : null}
      </div>

      {completed ? (
        <footer className="forge-process__actions">
          <span>共 {operations.length} 道工序</span>
          <button data-testid="download-export" type="button" onClick={onExport}>导出 PDF</button>
        </footer>
      ) : null}
    </section>
  );
}
