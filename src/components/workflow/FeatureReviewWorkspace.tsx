"use client";

import { useState, type FormEvent, type ReactNode } from "react";

import type { WorkflowFeature } from "@/services";

export interface FeatureDraft {
  label: string;
  value: string;
  unit: string;
  toleranceText: string;
  reviewStatus: WorkflowFeature["review_status"];
}

interface FeatureReviewWorkspaceProps {
  mode: "annotation" | "review";
  features: WorkflowFeature[];
  preview: ReactNode;
  busy: boolean;
  onConfirm: (features: WorkflowFeature[]) => void;
}

const reviewStatusLabels: Record<WorkflowFeature["review_status"], string> = {
  unreviewed: "未审阅",
  confirmed: "已确认",
  modified: "已修改",
  rejected: "已驳回",
};

function draftFromFeature(feature: WorkflowFeature): FeatureDraft {
  return {
    label: feature.label,
    value: feature.value ?? "",
    unit: feature.unit ?? "",
    toleranceText: feature.tolerance.text ?? "",
    reviewStatus: feature.review_status,
  };
}

function optionalValue(value: string): string | null {
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
}

export function mergeFeatureDraft(feature: WorkflowFeature, draft: FeatureDraft): WorkflowFeature {
  return {
    ...feature,
    label: draft.label.trim(),
    value: optionalValue(draft.value),
    unit: optionalValue(draft.unit),
    tolerance: { ...feature.tolerance, text: optionalValue(draft.toleranceText) },
    review_status: draft.reviewStatus,
  };
}

function toleranceLabel(feature: WorkflowFeature) {
  if (feature.tolerance.text) return feature.tolerance.text;
  if (feature.tolerance.upper !== null || feature.tolerance.lower !== null) {
    return `上偏差 ${feature.tolerance.upper ?? "未提供"} / 下偏差 ${feature.tolerance.lower ?? "未提供"}`;
  }
  return "未提供";
}

export function FeatureReviewWorkspace({ mode, features, preview, busy, onConfirm }: FeatureReviewWorkspaceProps) {
  const [draftEdits, setDraftEdits] = useState<Record<string, Partial<FeatureDraft>>>({});

  function draftFor(feature: WorkflowFeature): FeatureDraft {
    return { ...draftFromFeature(feature), ...draftEdits[feature.id] };
  }

  function updateDraft(feature: WorkflowFeature, patch: Partial<FeatureDraft>) {
    setDraftEdits((current) => ({ ...current, [feature.id]: { ...current[feature.id], ...patch } }));
  }

  function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    onConfirm(features.map((feature) => mergeFeatureDraft(feature, draftFor(feature))));
  }

  return (
    <section className="forge-feature-review" aria-labelledby="forge-feature-review-title">
      <div className="forge-feature-review__preview">{preview ?? <p>图纸预览未提供</p>}</div>
      <form className="forge-feature-review__panel" onSubmit={confirm}>
        <header className="forge-feature-review__header">
          <div>
            <p className="forge-eyebrow">FEATURE / EVIDENCE</p>
            <h2 id="forge-feature-review-title">{mode === "annotation" ? "结构化特征标注" : "结构化特征审阅"}</h2>
          </div>
          <span>{features.length} 项特征</span>
        </header>

        <div className="forge-feature-review__rows">
          {features.map((feature) => {
            const draft = draftFor(feature);
            return (
              <article className="forge-feature" key={feature.id}>
                <div className="forge-feature__fields">
                  <label>特征名称<input value={draft.label} onChange={(event) => updateDraft(feature, { label: event.target.value })} /></label>
                  <label>值<input value={draft.value} placeholder="未提供" onChange={(event) => updateDraft(feature, { value: event.target.value })} /></label>
                  <label>单位<input value={draft.unit} placeholder="未提供" onChange={(event) => updateDraft(feature, { unit: event.target.value })} /></label>
                  <label>公差<input value={draft.toleranceText} placeholder="未提供" onChange={(event) => updateDraft(feature, { toleranceText: event.target.value })} /></label>
                  <label>审阅状态
                    <select value={draft.reviewStatus} onChange={(event) => updateDraft(feature, { reviewStatus: event.target.value as FeatureDraft["reviewStatus"] })}>
                      {Object.entries(reviewStatusLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                    </select>
                  </label>
                </div>

                <dl className="forge-feature__evidence">
                  <div><dt>原始值</dt><dd>{feature.value ?? "未提供"}{feature.unit ? ` ${feature.unit}` : ""}</dd></div>
                  <div><dt>原始公差</dt><dd>{toleranceLabel(feature)}</dd></div>
                  <div><dt>来源方式</dt><dd>{feature.source.method ?? "未提供"}</dd></div>
                  <div><dt>来源页码</dt><dd>{feature.source.page === null ? "页码未提供" : `第 ${feature.source.page} 页`}</dd></div>
                  <div className="forge-feature__evidence-text"><dt>证据文本</dt><dd>{feature.source.evidence_text ?? "未提供"}</dd></div>
                  <div><dt>置信度</dt><dd>{feature.confidence === null ? "未提供" : `${feature.confidence}（原始值）`}</dd></div>
                  <div><dt>缺失原因</dt><dd>{feature.missing_reason ?? "无"}</dd></div>
                  <div><dt>审阅状态</dt><dd>{reviewStatusLabels[feature.review_status]}</dd></div>
                </dl>
              </article>
            );
          })}
        </div>

        <button className="forge-feature-review__primary" type="submit" disabled={busy} aria-busy={busy}>
          {mode === "annotation" ? "确认标注" : "确认审阅并生成工艺"}
        </button>
      </form>
    </section>
  );
}
