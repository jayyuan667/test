import { WORKFLOW_STEPS, canInspectStep } from "./workflow-step-model";
import type { WorkflowStepId } from "./workflow-step-model";

export interface WorkflowStepperProps {
  current: WorkflowStepId;
  reached: WorkflowStepId;
  onSelect: (step: WorkflowStepId) => void;
  busy: boolean;
}

export function WorkflowStepper({ current, reached, onSelect, busy }: WorkflowStepperProps) {
  return (
    <nav className="forge-stepper" aria-label="工艺生成步骤">
      <ol className="forge-stepper__list">
        {WORKFLOW_STEPS.map((step) => {
          const isCurrent = step.id === current;
          const isAvailable = canInspectStep(step.id, reached);

          return (
            <li className="forge-stepper__item" key={step.id}>
              <button
                className="forge-stepper__button"
                type="button"
                aria-current={isCurrent ? "step" : undefined}
                disabled={!isAvailable || busy}
                onClick={() => onSelect(step.id)}
              >
                <span className="forge-stepper__number" aria-hidden="true">{step.number}</span>
                <span className="forge-stepper__label">{step.label}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
