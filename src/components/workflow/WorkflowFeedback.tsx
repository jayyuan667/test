import type { TaskState, WorkflowConnection, WorkflowError } from "@/features/drawing-workflow/types";

const connectionCopy = {
  idle: null,
  connecting: "正在连接分析任务…",
  connected: null,
  reconnecting: "正在恢复实时进度…",
  closed: null,
} as const satisfies Record<WorkflowConnection, string | null>;

export interface WorkflowFeedbackAction {
  label: string;
  onSelect: () => void;
}

export interface WorkflowFeedbackProps {
  state: TaskState | null;
  connection: WorkflowConnection;
  error: WorkflowError | null;
  action?: WorkflowFeedbackAction;
}

export function WorkflowFeedback({ connection, error, action }: WorkflowFeedbackProps) {
  const status = connectionCopy[connection];

  if (!error && !status) return null;

  if (error) {
    return (
      <div className="forge-feedback forge-feedback--error" role="alert">
        <p className="forge-feedback__message">{error.message}</p>
        {action ? (
          <button className="forge-feedback__action" type="button" onClick={action.onSelect}>
            {action.label}
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="forge-feedback" role="status" aria-live="polite">
      <span className="forge-feedback__pulse" aria-hidden="true" />
      <p className="forge-feedback__message">{status}</p>
    </div>
  );
}
