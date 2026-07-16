# FORGE Legacy Shell and v1 Workflow Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the proven four-step engineering workstation interaction and visual hierarchy while keeping the v1 typed workflow as the only task, transport, recovery, and command implementation.

**Architecture:** `GeneratePage` remains the controller lifecycle and view-step coordinator. Focused presentational workspaces consume typed snapshot/state props and callbacks; they never fetch, poll, parse Markdown, construct EventSource, or read local storage. A pure step model separates the highest backend-reached step from the user's current inspection step so completed work can be revisited without replaying commands.

**Tech Stack:** Next.js 16, React 19, TypeScript, existing CSS custom properties, Node test runner, Playwright, Flask v1 workflow API.

## Global Constraints

- Keep `/api/v1` and `DrawingWorkflowController` as the only workflow transport and command path.
- Do not modify recognition models, prompts, process-generation algorithms, or database models.
- Do not import business functions from `LegacyGeneratePage` or reintroduce polling, direct fetch, EventSource, query tokens, or Markdown feature parsing.
- Use the existing AppShell, dark industrial tokens, typography, and restrained accent strategy.
- Preserve authenticated preview allowlisting and do not invent confidence, page, duration, or source values.
- Desktop is a dense workstation; narrow screens stack the workspaces without shrinking primary controls.
- Motion is 150–250 ms, state-driven, and disabled or reduced under `prefers-reduced-motion`.
- Every interactive control requires visible focus, disabled, loading, and error behavior.

## File Map

- `src/components/pages/GeneratePage.tsx`: controller lifecycle, local active-task persistence, current view step, and workspace composition.
- `src/components/workflow/workflow-step-model.ts`: pure snapshot-to-step mapping and navigation rules.
- `src/components/workflow/WorkflowStepper.tsx`: accessible four-step navigation.
- `src/components/workflow/DrawingWorkspace.tsx`: authenticated preview presentation, page selection, and expanded preview.
- `src/components/workflow/UploadWorkspace.tsx`: legacy-inspired upload surface and selected-file summary.
- `src/components/workflow/FeatureReviewWorkspace.tsx`: structured feature rows and review confirmation.
- `src/components/workflow/ProcessWorkspace.tsx`: real generation state, structured operations, and PDF export.
- `src/components/workflow/WorkflowFeedback.tsx`: user-facing processing, reconnect, failure, and empty-state feedback.
- `src/components/workflow/workflow.css`: scoped workstation layout, responsive rules, focus, and reduced motion.
- `src/components/workflow/*.test.tsx`: pure model and server-rendered component behavior.
- `e2e/v1-workflow.spec.ts`: real four-step interaction, backward inspection, reload recovery, and PDF verification.

---

### Task 1: Pure Four-Step Navigation Model

**Files:**
- Create: `src/components/workflow/workflow-step-model.ts`
- Create: `src/components/workflow/workflow-step-model.test.ts`

**Interfaces:**
- Consumes: `TaskSnapshot | null` from `src/features/drawing-workflow/types.ts`.
- Produces: `WorkflowStepId`, `WORKFLOW_STEPS`, `reachedStepForSnapshot(snapshot)`, and `canInspectStep(target, reached)`.

- [ ] **Step 1: Write the failing mapping and navigation tests**

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { canInspectStep, reachedStepForSnapshot } from "./workflow-step-model.ts";

const snapshot = (state, preview_urls = [], features = [], process_operations = []) => ({
  task: { state }, drawing: { preview_urls }, features, process_operations,
});

test("maps backend states to the highest reached workstation step", () => {
  assert.equal(reachedStepForSnapshot(null), "upload");
  assert.equal(reachedStepForSnapshot(snapshot("processing")), "upload");
  assert.equal(reachedStepForSnapshot(snapshot("processing", ["/preview.png"])), "annotation");
  assert.equal(reachedStepForSnapshot(snapshot("awaiting_annotation", ["/preview.png"])), "annotation");
  assert.equal(reachedStepForSnapshot(snapshot("awaiting_review", [], [{}])), "review");
  assert.equal(reachedStepForSnapshot(snapshot("completed", [], [], [{}])), "process");
});

test("allows inspecting completed steps but never future steps", () => {
  assert.equal(canInspectStep("upload", "review"), true);
  assert.equal(canInspectStep("annotation", "review"), true);
  assert.equal(canInspectStep("process", "review"), false);
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `node --test --experimental-strip-types src/components/workflow/workflow-step-model.test.ts`

Expected: FAIL because `workflow-step-model.ts` does not exist.

- [ ] **Step 3: Implement the pure model**

```ts
import type { TaskSnapshot } from "@/features/drawing-workflow/types";

export type WorkflowStepId = "upload" | "annotation" | "review" | "process";
export const WORKFLOW_STEPS = [
  { id: "upload", number: "01", label: "上传图纸" },
  { id: "annotation", number: "02", label: "特征标注" },
  { id: "review", number: "03", label: "审阅确认" },
  { id: "process", number: "04", label: "工艺生成" },
] as const;

const order = Object.fromEntries(WORKFLOW_STEPS.map((step, index) => [step.id, index])) as Record<WorkflowStepId, number>;

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
```

- [ ] **Step 4: Run the focused test and workflow regression gate**

Run: `node --test --experimental-strip-types src/components/workflow/workflow-step-model.test.ts && npm run test:workflow`

Expected: all tests PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/components/workflow/workflow-step-model.ts src/components/workflow/workflow-step-model.test.ts
git commit -m "feat: add workflow step navigation model"
```

---

### Task 2: Accessible Legacy-Inspired Stepper and Feedback

**Files:**
- Create: `src/components/workflow/WorkflowStepper.tsx`
- Create: `src/components/workflow/WorkflowFeedback.tsx`
- Create: `src/components/workflow/workflow.css`
- Create: `src/components/workflow/WorkflowStepper.test.tsx`

**Interfaces:**
- Consumes: `WorkflowStepId`, `WORKFLOW_STEPS`, `WorkflowConnection`, progress, busy, and structured `WorkflowError`.
- Produces: `<WorkflowStepper current reached onSelect busy />` and `<WorkflowFeedback state connection error />`.

- [ ] **Step 1: Write server-rendered semantic tests**

```tsx
import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { WorkflowStepper } from "./WorkflowStepper.tsx";

test("marks current, completed, and unavailable steps without exposing technical connection text", () => {
  const html = renderToStaticMarkup(
    <WorkflowStepper current="annotation" reached="review" busy={false} onSelect={() => {}} />,
  );
  assert.match(html, /aria-current="step"/);
  assert.match(html, /上传图纸/);
  assert.match(html, /特征标注/);
  assert.match(html, /审阅确认/);
  assert.match(html, /disabled=""[^>]*>工艺生成/);
  assert.doesNotMatch(html, /seq|connected|closed/);
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `node --test --experimental-strip-types src/components/workflow/WorkflowStepper.test.tsx`

Expected: FAIL because the components do not exist.

- [ ] **Step 3: Implement typed stepper and user-facing feedback**

Implement buttons using `aria-current="step"`, visible labels and numbers, `disabled={!canInspectStep(...) || busy}`, and an `onSelect(step.id)` callback. Implement feedback copy with this exact mapping:

```ts
const connectionCopy = {
  idle: null,
  connecting: "正在连接分析任务…",
  connected: null,
  reconnecting: "正在恢复实时进度…",
  closed: null,
} as const;
```

Render structured error message and a retry/restart action supplied by the parent. Never render sequence IDs or raw connection enum values.

- [ ] **Step 4: Implement scoped workstation CSS**

Use `.forge-workflow`, `.forge-stepper`, `.forge-workspace`, and `.forge-feedback` under one stylesheet. Desktop content max width is `1440px`; workspace gaps use existing spacing variables; cards cap at `16px` radius; focus uses a 2px accent outline. At `max-width: 900px`, two-column workspaces become one column. Add:

```css
@media (prefers-reduced-motion: reduce) {
  .forge-workflow *, .forge-workflow *::before, .forge-workflow *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 5: Verify components and styles**

Run: `node --test --experimental-strip-types src/components/workflow/WorkflowStepper.test.tsx && npx eslint src/components/workflow && npx tsc --noEmit`

Expected: PASS with no new lint or type errors.

- [ ] **Step 6: Commit Task 2**

```bash
git add src/components/workflow/WorkflowStepper.tsx src/components/workflow/WorkflowFeedback.tsx src/components/workflow/WorkflowStepper.test.tsx src/components/workflow/workflow.css
git commit -m "feat: restore workflow step navigation"
```

---

### Task 3: Upload and Authenticated Drawing Workspaces

**Files:**
- Create: `src/components/workflow/UploadWorkspace.tsx`
- Create: `src/components/workflow/DrawingWorkspace.tsx`
- Create: `src/components/workflow/DrawingWorkspace.test.tsx`
- Modify: `src/components/workflow/workflow.css`

**Interfaces:**
- Consumes: selected `File | null`, preview object URLs, drawing metadata, busy state, and callbacks owned by `GeneratePage`.
- Produces: `<UploadWorkspace file busy onFileChange onStart />` and `<DrawingWorkspace drawing previewUrls activePage onPageChange />`.

- [ ] **Step 1: Write semantic rendering tests**

```tsx
test("drawing workspace keeps the engineering drawing primary and exposes page controls", () => {
  const html = renderToStaticMarkup(
    <DrawingWorkspace
      drawing={{ name: "test.png", source_kind: "png", page_count: 2, preview_urls: [] }}
      previewUrls={["blob:one", "blob:two"]}
      activePage={0}
      onPageChange={() => {}}
    />,
  );
  assert.match(html, /alt="test\.png · 第 1 页"/);
  assert.match(html, /第 1 页 \/ 共 2 页/);
  assert.match(html, /放大查看/);
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `node --test --experimental-strip-types src/components/workflow/DrawingWorkspace.test.tsx`

Expected: FAIL because the workspace does not exist.

- [ ] **Step 3: Implement the upload workspace**

Use a visible native file input, accepted types from the existing workflow, selected filename and size, and one primary button. The button label is `开始解析` or `正在上传…`; it is disabled without a file or while busy. Do not create a second upload state machine.

- [ ] **Step 4: Implement drawing preview and expansion**

Use only object URLs supplied by `GeneratePage`; never fetch inside the component. Provide previous/next page controls and a native `<dialog>` or fixed portal for expanded preview. The dialog closes by button and Escape. Reuse the same image URL and preserve descriptive alt text.

- [ ] **Step 5: Verify focused behavior and accessibility**

Run: `node --test --experimental-strip-types src/components/workflow/DrawingWorkspace.test.tsx && npx eslint src/components/workflow && npx tsc --noEmit`

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git add src/components/workflow/UploadWorkspace.tsx src/components/workflow/DrawingWorkspace.tsx src/components/workflow/DrawingWorkspace.test.tsx src/components/workflow/workflow.css
git commit -m "feat: restore drawing upload workspace"
```

---

### Task 4: Structured Feature Review Workspace

**Files:**
- Create: `src/components/workflow/FeatureReviewWorkspace.tsx`
- Create: `src/components/workflow/FeatureReviewWorkspace.test.tsx`
- Modify: `src/components/workflow/workflow.css`

**Interfaces:**
- Consumes: `WorkflowFeature[]`, drawing preview content, busy state, annotation/review mode, and typed callbacks.
- Produces: immutable row display plus local editable draft; `onConfirm(features: WorkflowFeature[])` sends the normalized draft.

- [ ] **Step 1: Write tests for real and missing values**

```tsx
test("renders structured evidence and explicit missing values without invented confidence", () => {
  const html = renderToStaticMarkup(
    <FeatureReviewWorkspace
      mode="review"
      features={[{ ...feature, confidence: null, source: { ...feature.source, page: null } }]}
      busy={false}
      onConfirm={() => {}}
    />,
  );
  assert.match(html, /未提供/);
  assert.match(html, /页码未提供/);
  assert.match(html, /legacy_text/);
  assert.doesNotMatch(html, /85%|90%|95%/);
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `node --test --experimental-strip-types src/components/workflow/FeatureReviewWorkspace.test.tsx`

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement structured rows and local draft editing**

Render label, value/unit, tolerance text, source method/page/evidence, confidence or missing reason, and review status. Draft edits update only local component state. Preserve IDs and source fields when editing. The annotation mode has `确认标注`; review mode has `确认审阅并生成工艺`.

- [ ] **Step 4: Prevent duplicate commands**

The primary action is disabled while `busy`. After invoking the callback, the parent immediately transitions the view out of the command-ready state using the existing controller command transition. No skip action is added unless the backend exposes an explicit v1 capability for it.

- [ ] **Step 5: Verify review behavior**

Run: `node --test --experimental-strip-types src/components/workflow/FeatureReviewWorkspace.test.tsx && npx eslint src/components/workflow && npx tsc --noEmit`

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add src/components/workflow/FeatureReviewWorkspace.tsx src/components/workflow/FeatureReviewWorkspace.test.tsx src/components/workflow/workflow.css
git commit -m "feat: add structured feature review workspace"
```

---

### Task 5: Structured Process Workstation and Page Composition

**Files:**
- Create: `src/components/workflow/ProcessWorkspace.tsx`
- Create: `src/components/workflow/ProcessWorkspace.test.tsx`
- Modify: `src/components/pages/GeneratePage.tsx`
- Modify: `src/components/workflow/workflow.css`

**Interfaces:**
- Consumes: `ProcessOperation[]`, snapshot state/phase/progress, export callback, and `WorkflowFeedback` props.
- Produces: complete four-step page composition with backward inspection and no legacy transport.

- [ ] **Step 1: Write process-table semantic tests**

```tsx
test("renders structured operations and explicit absent equipment or duration", () => {
  const html = renderToStaticMarkup(
    <ProcessWorkspace
      operations={[{ ...operation, equipment: [], duration_minutes: null }]}
      taskState="completed"
      phase="done"
      progress={100}
      onExport={() => {}}
    />,
  );
  assert.match(html, /0010/);
  assert.match(html, /设备未提供/);
  assert.match(html, /工时未提供/);
  assert.match(html, /导出 PDF/);
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `node --test --experimental-strip-types src/components/workflow/ProcessWorkspace.test.tsx`

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement the process workstation**

Use a semantic table on desktop and labeled rows on narrow screens. Render operation code, name, content, equipment, duration, and source without converting to Markdown. While processing, preserve the table and show actual phase/progress in `WorkflowFeedback`; do not show raw stream chunks.

- [ ] **Step 4: Replace the current validation-page composition**

In `GeneratePage`, retain controller creation, subscriptions, active-task recovery, preview loading, command guards, cancel reset, and export transport. Add:

```ts
const reachedStep = reachedStepForSnapshot(snapshot);
const [viewStep, setViewStep] = useState<WorkflowStepId>("upload");
const [followLatest, setFollowLatest] = useState(true);

useEffect(() => {
  if (!snapshot) setViewStep("upload");
  else if (followLatest) setViewStep(reachedStep);
  else setViewStep((current) => canInspectStep(current, reachedStep) ? current : reachedStep);
}, [snapshot, reachedStep, followLatest]);
```

Selecting an earlier completed step sets `followLatest` to false. Starting a command from its owning step sets it back to true so the page follows the next backend transition. Compose the stepper and exactly one active workspace. Remove the current technical `connection · seq` display and card stack.

- [ ] **Step 5: Add static architecture guards**

Extend workflow tests to read `GeneratePage.tsx` and assert it contains none of:

```ts
for (const forbidden of ["fetch(", "new EventSource", "setInterval(", "marked(", "?token="]) {
  assert.equal(source.includes(forbidden), false);
}
```

- [ ] **Step 6: Run frontend gates**

Run: `npm run test:workflow && node --test --experimental-strip-types src/components/workflow/*.test.ts src/components/workflow/*.test.tsx && npx eslint src/components/pages/GeneratePage.tsx src/components/workflow && npx tsc --noEmit && npm run build`

Expected: all commands PASS.

- [ ] **Step 7: Commit Task 5**

```bash
git add src/components/pages/GeneratePage.tsx src/components/workflow src/features/drawing-workflow
git commit -m "feat: fuse legacy workstation with v1 workflow"
```

---

### Task 6: Real Four-Step Acceptance and Visual QA

**Files:**
- Modify: `e2e/v1-workflow.spec.ts`
- Modify: `docs/verification/2026-07-15-v1-workflow.md`
- Create: `docs/verification/2026-07-16-workstation-fusion.md`

**Interfaces:**
- Consumes: running frontend on port 3002, backend on port 5390, real credentials from environment, and `/Users/caojiayuan/Documents/测试包/drawing/test.png`.
- Produces: reproducible real acceptance evidence for interaction, recovery, structured results, and PDF.

- [ ] **Step 1: Extend E2E selectors and assertions before implementation is considered complete**

Add assertions for:

```ts
await expect(page.getByRole("navigation", { name: "工艺生成步骤" })).toBeVisible();
await expect(page.getByRole("button", { name: /特征标注/ })).toHaveAttribute("aria-current", "step");
await expect(page.getByRole("img", { name: /test\.png/ })).toBeVisible();
await expect(page.getByText("未提供", { exact: true }).first()).toBeVisible();
await page.getByRole("button", { name: /上传图纸/ }).click();
await expect(page.getByText("test.png", { exact: false })).toBeVisible();
await expect(page.getByText(/closed\s*·\s*seq/i)).toHaveCount(0);
```

Keep existing assertions for same-task reload recovery, positive feature/operation counts, completed/done/100, and real PDF MIME/name/size/`%PDF` magic.

- [ ] **Step 2: Run E2E and capture the first failing checkpoint**

Run: `PW_TEST_HTML_REPORT_OPEN=never npx playwright test --config=e2e/playwright.prod.config.ts e2e/v1-workflow.spec.ts --reporter=line`

Expected before all UI work is complete: FAIL at the first missing fused-workstation selector.

- [ ] **Step 3: Complete responsive and visual QA in a real browser**

Inspect at `1440x1000`, `1024x768`, and `390x844`. Verify no clipped controls, no text overflow, visible focus, readable table fallback, stable preview, and no decorative card repetition. Save screenshots under `/tmp/forge-workstation-fusion/`, not Git.

- [ ] **Step 4: Run the real E2E to GREEN**

Run the same Playwright command.

Expected: `1 passed`; the evidence identifies the real task ID and PDF.

- [ ] **Step 5: Run final gates**

Run:

```bash
npm run test:workflow
node --test --experimental-strip-types src/components/workflow/*.test.ts src/components/workflow/*.test.tsx
npx eslint src/components/pages/GeneratePage.tsx src/components/workflow e2e/v1-workflow.spec.ts
npx tsc --noEmit
npm run build
.venv/bin/python -m pytest backend/test_task_events_v1.py backend/test_task_contract_v1.py backend/test_tasks_api_v1.py backend/test_sse_events.py -q
git diff --check
```

Expected: all owned gates PASS. Record the existing Onshape/background-thread or missing user runtime-smoke limitations only if they reproduce; do not report them as new fusion failures.

- [ ] **Step 6: Write the verification record and commit**

Document viewport screenshots, task ID, feature/operation counts, backward step inspection, reload task identity, and PDF metadata in `docs/verification/2026-07-16-workstation-fusion.md`.

```bash
git add e2e/v1-workflow.spec.ts docs/verification/2026-07-16-workstation-fusion.md docs/verification/2026-07-15-v1-workflow.md
git commit -m "test: verify fused workflow workstation"
```

---

## Final Review Gate

- Generate one review package from the implementation base through HEAD.
- Request an independent read-only review against the fusion design spec and this plan.
- Fix every Critical and Important finding, rerun affected gates, and request re-review.
- Do not remove `NEXT_PUBLIC_USE_WORKFLOW_V1=false` or the immutable legacy fallback in this implementation; its existing production observation and rollback gate remains in force.
