import type { TaskPhase, WorkflowConnection } from "@/features/drawing-workflow/types";

interface WorkflowWaitingPanelProps {
  phase: TaskPhase;
  progress: number;
  connection: WorkflowConnection;
}

const waitingCopy: Record<TaskPhase, { title: string; detail: string; next: string }> = {
  upload: {
    title: "正在准备上传任务",
    detail: "系统正在建立任务通道并校验图纸文件。",
    next: "连接完成后将自动进入图纸解析。",
  },
  drawing_analysis: {
    title: "标注已确认，正在进行视觉分析",
    detail: "正在提取结构特征、尺寸证据和图纸文本。",
    next: "完成后将自动进入审阅确认。",
  },
  annotation: {
    title: "正在整理特征标注",
    detail: "正在合成图纸预览和自动标注结果。",
    next: "准备完成后即可确认标注。",
  },
  feature_review: {
    title: "正在准备审阅结果",
    detail: "正在融合视觉分析、OCR 文本和结构化特征。",
    next: "完成后将自动进入审阅确认。",
  },
  process_generation: {
    title: "工艺路线正在生成",
    detail: "正在把结构特征转换为工序、设备和加工依据。",
    next: "系统会自动刷新工序表。",
  },
  export: {
    title: "正在准备导出文件",
    detail: "正在整理工艺路线和导出数据。",
    next: "完成后即可下载文件。",
  },
  done: {
    title: "工艺生成已完成",
    detail: "结构化工艺路线已经生成。",
    next: "可以导出或清除当前任务重新开始。",
  },
};

export function WorkflowWaitingPanel({ phase, progress, connection }: WorkflowWaitingPanelProps) {
  const normalizedProgress = Math.min(100, Math.max(0, progress));
  const copy = waitingCopy[phase];
  const recovering = connection === "reconnecting" || connection === "connecting";

  return (
    <section className="forge-waiting" data-testid="workflow-waiting-panel" aria-live="polite" aria-busy="true">
      <div className="forge-waiting__visual" aria-hidden="true">
        <span className="forge-waiting__orb" />
        <span className="forge-waiting__scanner" />
      </div>
      <div className="forge-waiting__content">
        <p className="forge-eyebrow">SYSTEM / WORKING</p>
        <h2 id="forge-waiting-title">{recovering ? "正在恢复实时进度" : copy.title}</h2>
        <p>{recovering ? "正在重新连接任务事件流，不会重复提交当前任务。" : copy.detail}</p>
        <ul>
          {recovering ? <li>当前阶段：{copy.title}</li> : null}
          <li>{copy.detail}</li>
          <li>{copy.next}</li>
          <li>{recovering ? "不会重复提交当前任务。" : "页面会在结果就绪后自动切换。"}</li>
        </ul>
        <div className="forge-waiting__meter">
          <span>完成度 {normalizedProgress}%</span>
          <progress value={normalizedProgress} max={100}>{normalizedProgress}%</progress>
        </div>
      </div>
    </section>
  );
}
