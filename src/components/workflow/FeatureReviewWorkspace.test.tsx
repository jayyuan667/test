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
