import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import type { WorkflowFeature } from "@/services";

import { createSubmissionGate, FeatureReviewWorkspace, mergeFeatureDraft } from "./FeatureReviewWorkspace.tsx";

const feature: WorkflowFeature = {
  id: "feature-1",
  kind: "diameter",
  label: "外圆直径",
  value: "42",
  unit: "mm",
  tolerance: { upper: 0.02, lower: -0.01, text: "+0.02/-0.01" },
  source: { method: "legacy_text", page: 2, bbox: [1, 2, 3, 4], evidence_text: "Ø42 +0.02/-0.01" },
  confidence: 0.87,
  review_status: "unreviewed",
  missing_reason: null,
};

const secondFeature: WorkflowFeature = {
  ...feature,
  id: "feature-2",
  label: "螺纹规格",
  value: "M115×3-6g",
  unit: null,
  source: { ...feature.source, evidence_text: "M115×3-6g" },
};

test("renders structured evidence and explicit missing values without invented confidence", () => {
  const html = renderToStaticMarkup(
    <FeatureReviewWorkspace
      mode="review"
      features={[{ ...feature, confidence: null, source: { ...feature.source, page: null } }]}
      preview={<div>图纸预览</div>}
      busy={false}
      onConfirm={() => {}}
    />,
  );

  assert.match(html, /外圆直径/);
  assert.match(html, /42/);
  assert.match(html, /mm/);
  assert.match(html, /\+0\.02\/\-0\.01/);
  assert.match(html, /legacy_text/);
  assert.match(html, /页码未提供/);
  assert.match(html, /Ø42 \+0\.02\/\-0\.01/);
  assert.match(html, /置信度/);
  assert.match(html, /未提供/);
  assert.match(html, /未审阅/);
  assert.doesNotMatch(html, /85%|90%|95%/);
});

test("shows one active feature with pager controls instead of stacking every feature form", () => {
  const html = renderToStaticMarkup(
    <FeatureReviewWorkspace
      mode="review"
      features={[feature, secondFeature]}
      preview={<div>图纸预览</div>}
      busy={false}
      onConfirm={() => {}}
    />,
  );

  assert.match(html, /data-testid="feature-pager"/);
  assert.match(html, /第 1 \/ 2 项/);
  assert.match(html, /上一项/);
  assert.match(html, /下一项/);
  assert.match(html, /查看第 2 项特征：螺纹规格/);
  assert.match(html, /外圆直径/);
  assert.doesNotMatch(html, /M115×3-6g/);
  assert.equal((html.match(/data-testid="feature-row"/g) ?? []).length, 1);
});

test("empty annotation can still be confirmed so zero YOLO detections do not block the workflow", () => {
  const html = renderToStaticMarkup(
    <FeatureReviewWorkspace
      mode="annotation"
      features={[]}
      preview={null}
      busy={false}
      onConfirm={() => {}}
    />,
  );

  assert.match(html, /data-testid="feature-empty"/);
  assert.match(html, /未检测到自动特征，可确认标注后继续视觉分析/);
  assert.match(html, /确认标注/);
  assert.doesNotMatch(html, /disabled/);
});

test("empty review shows a clear disabled state", () => {
  const html = renderToStaticMarkup(
    <FeatureReviewWorkspace
      mode="review"
      features={[]}
      preview={null}
      busy={false}
      onConfirm={() => {}}
    />,
  );

  assert.match(html, /data-testid="feature-empty"/);
  assert.match(html, /确认审阅并生成工艺/);
  assert.match(html, /disabled/);
});

test("shows missing reason and mode-accurate actions without a skip command", () => {
  const missing: WorkflowFeature = {
    ...feature,
    value: null,
    unit: null,
    tolerance: { upper: null, lower: null, text: null },
    missing_reason: "图面字符模糊",
    review_status: "rejected",
  };
  const annotation = renderToStaticMarkup(
    <FeatureReviewWorkspace mode="annotation" features={[missing]} preview={null} busy={false} onConfirm={() => {}} />,
  );
  const review = renderToStaticMarkup(
    <FeatureReviewWorkspace mode="review" features={[feature]} preview={null} busy onConfirm={() => {}} />,
  );

  assert.match(annotation, /图面字符模糊/);
  assert.match(annotation, /确认标注/);
  assert.doesNotMatch(annotation, /跳过/);
  assert.match(review, /确认审阅并生成工艺/);
  assert.match(review, /disabled/);
});

test("historical inspection is read-only and cannot replay an owning command", () => {
  const html = renderToStaticMarkup(
    <FeatureReviewWorkspace
      mode="annotation"
      features={[feature]}
      preview={null}
      busy={false}
      canConfirm={false}
      onConfirm={() => {}}
    />,
  );

  assert.match(html, /此步骤已完成，当前为回看模式/);
  assert.doesNotMatch(html, />确认标注<\/button>/);
});

test("merges editable draft fields while preserving immutable evidence", () => {
  const merged = mergeFeatureDraft(feature, {
    label: "精车外圆",
    value: "43",
    unit: "毫米",
    toleranceText: "±0.01",
    reviewStatus: "modified",
  });

  assert.deepEqual(merged, {
    ...feature,
    label: "精车外圆",
    value: "43",
    unit: "毫米",
    tolerance: { ...feature.tolerance, text: "±0.01" },
    review_status: "modified",
  });
  assert.equal(merged.source, feature.source);
});

test("submission gate synchronously rejects duplicate submit events from the same render", () => {
  const gate = createSubmissionGate();
  let calls = 0;

  assert.equal(gate.submit(() => { calls += 1; }), true);
  assert.equal(gate.submit(() => { calls += 1; }), false);
  assert.equal(calls, 1);
});

test("submission gate unlocks after rejection and after a completed parent busy cycle", async () => {
  const gate = createSubmissionGate();
  let calls = 0;

  gate.submit(async () => {
    calls += 1;
    throw new Error("提交失败");
  });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(gate.submit(() => { calls += 1; }), true);
  assert.equal(calls, 2);

  gate.observeBusy(true);
  assert.equal(gate.submit(() => { calls += 1; }), false);
  gate.observeBusy(false);
  assert.equal(gate.submit(() => { calls += 1; }), true);
  assert.equal(calls, 3);
});
