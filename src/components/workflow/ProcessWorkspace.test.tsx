import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import type { ProcessOperation } from "@/features/drawing-workflow/types";

import { ProcessWorkspace } from "./ProcessWorkspace.tsx";

const operation: ProcessOperation = {
  id: "operation-10",
  code: "0010",
  trade: "车工",
  content: "粗车外圆并留精加工余量",
  equipment: [],
  duration_minutes: null,
  parameters: [],
  note: null,
  evidence_features: [],
  status: "complete",
};

test("renders structured operations and explicit absent equipment, duration, and evidence", () => {
  const html = renderToStaticMarkup(
    <ProcessWorkspace
      operations={[operation]}
      taskState="completed"
      phase="done"
      connection="closed"
      error={null}
      onExport={() => {}}
    />,
  );

  assert.match(html, /0010/);
  assert.match(html, /粗车外圆并留精加工余量/);
  assert.match(html, /设备未提供/);
  assert.match(html, /工时未提供/);
  assert.match(html, /依据未匹配，请人工核对/);
  assert.match(html, /当前阶段/);
  assert.match(html, /工艺生成已完成/);
  assert.doesNotMatch(html, /完成度 100%/);
  assert.doesNotMatch(html, /<progress/);
  assert.match(html, /导出 PDF/);
  assert.doesNotMatch(html, /markdown|seq|closed/i);
});

test("renders operation evidence as compact trust tags", () => {
  const html = renderToStaticMarkup(
    <ProcessWorkspace
      operations={[{
        ...operation,
        note: "留精加工余量",
        evidence_features: [
          {
            id: "feature-dia-1",
            kind: "diameter",
            label: "外圆",
            value: "Φ146±0.05",
            unit: null,
            tolerance: { upper: null, lower: null, text: null },
            source: { method: "vlm", page: 1, bbox: null, evidence_text: "Φ146±0.05" },
            confidence: 0.92,
            review_status: "confirmed",
            missing_reason: null,
          },
        ],
      }]}
      taskState="completed"
      phase="done"
      connection="closed"
      error={null}
      onExport={() => {}}
    />,
  );

  assert.match(html, /依据 \/ 备注/);
  assert.match(html, /外圆/);
  assert.match(html, /Φ146±0.05/);
  assert.match(html, /第 1 页/);
  assert.match(html, /92%/);
  assert.match(html, /留精加工余量/);
  assert.doesNotMatch(html, /来源未提供/);
});

test("keeps the workstation visible while processing without fake percentage progress", () => {
  const html = renderToStaticMarkup(
    <ProcessWorkspace
      operations={[]}
      taskState="processing"
      phase="process_generation"
      connection="connected"
      error={null}
      onExport={() => {}}
    />,
  );

  assert.match(html, /正在生成工艺/);
  assert.match(html, /阶段进行中/);
  assert.doesNotMatch(html, /完成度 63%/);
  assert.doesNotMatch(html, /<progress/);
  assert.match(html, /data-testid="workflow-waiting-panel"/);
  assert.match(html, /工艺路线正在生成/);
  assert.match(html, /系统会自动刷新工序表/);
  assert.match(html, /结构化工序将在生成后显示/);
  assert.doesNotMatch(html, /导出 PDF/);
});

test("marks streamed operation rows as generating while process output arrives", () => {
  const html = renderToStaticMarkup(
    <ProcessWorkspace
      operations={[{ ...operation, status: "streaming" }]}
      taskState="processing"
      phase="process_generation"
      connection="connected"
      error={null}
      onExport={() => {}}
    />,
  );

  assert.match(html, /forge-process__row--streaming/);
  assert.match(html, /生成中/);
  assert.match(html, /粗车外圆并留精加工余量/);
});
