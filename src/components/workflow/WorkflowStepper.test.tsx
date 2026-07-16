import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { WorkflowFeedback } from "./WorkflowFeedback.tsx";
import { WorkflowStepper } from "./WorkflowStepper.tsx";

test("marks the current, completed, and unavailable workflow steps", () => {
  const html = renderToStaticMarkup(
    React.createElement(WorkflowStepper, {
      current: "annotation",
      reached: "review",
      busy: false,
      onSelect: () => {},
    }),
  );

  assert.match(html, /aria-label="图纸分析步骤"/);
  assert.match(html, /aria-current="step"/);
  assert.match(html, />01</);
  assert.match(html, />上传图纸</);
  assert.match(html, />特征标注</);
  assert.match(html, />审阅确认</);
  assert.match(html, /disabled=""[^>]*>[^<]*<span[^>]*>04<\/span>[^<]*<span[^>]*>工艺生成<\/span>/);
  assert.doesNotMatch(html, /seq|connected|closed/i);
});

test("disables every workflow step while an action is busy", () => {
  const html = renderToStaticMarkup(
    React.createElement(WorkflowStepper, {
      current: "review",
      reached: "process",
      busy: true,
      onSelect: () => {},
    }),
  );

  assert.equal((html.match(/disabled=""/g) ?? []).length, 4);
});

test("shows only actionable connection feedback in user-facing language", () => {
  const connecting = renderToStaticMarkup(
    React.createElement(WorkflowFeedback, {
      state: "processing",
      connection: "connecting",
      error: null,
    }),
  );
  const connected = renderToStaticMarkup(
    React.createElement(WorkflowFeedback, {
      state: "processing",
      connection: "connected",
      error: null,
    }),
  );
  const reconnecting = renderToStaticMarkup(
    React.createElement(WorkflowFeedback, {
      state: "processing",
      connection: "reconnecting",
      error: null,
    }),
  );

  assert.match(connecting, /正在连接分析任务…/);
  assert.equal(connected, "");
  assert.match(reconnecting, /正在恢复实时进度…/);
  assert.doesNotMatch(`${connecting}${connected}${reconnecting}`, /seq|connected|closed/i);
});

test("renders a structured error and the supplied recovery action", () => {
  const html = renderToStaticMarkup(
    React.createElement(WorkflowFeedback, {
      state: "failed",
      connection: "closed",
      error: {
        code: "analysis_failed",
        message: "图纸解析失败，请重试。",
        retryable: true,
        phase: "drawing_analysis",
        details: { seq: 42 },
      },
      action: { label: "重试分析", onSelect: () => {} },
    }),
  );

  assert.match(html, /role="alert"/);
  assert.match(html, /图纸解析失败，请重试。/);
  assert.match(html, /<button[^>]*>重试分析<\/button>/);
  assert.doesNotMatch(html, /analysis_failed|drawing_analysis|seq|42/);
});
