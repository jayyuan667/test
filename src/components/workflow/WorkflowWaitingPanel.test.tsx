import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import { WorkflowWaitingPanel } from "./WorkflowWaitingPanel.tsx";

test("explains visual analysis waiting state with visible motion affordances", () => {
  const html = renderToStaticMarkup(
    <WorkflowWaitingPanel
      phase="drawing_analysis"
      progress={40}
      connection="connected"
    />,
  );

  assert.match(html, /data-testid="workflow-waiting-panel"/);
  assert.match(html, /标注已确认，正在进行视觉分析/);
  assert.match(html, /正在提取结构特征/);
  assert.match(html, /完成后将自动进入审阅确认/);
  assert.match(html, /forge-waiting__scanner/);
  assert.match(html, /forge-waiting__orb/);
  assert.match(html, /完成度 40%/);
});

test("shows realtime recovery copy when the event stream is reconnecting", () => {
  const html = renderToStaticMarkup(
    <WorkflowWaitingPanel
      phase="feature_review"
      progress={50}
      connection="reconnecting"
    />,
  );

  assert.match(html, /正在恢复实时进度/);
  assert.match(html, /不会重复提交当前任务/);
  assert.match(html, /正在准备审阅结果/);
});
