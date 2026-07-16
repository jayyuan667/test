"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";

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
  canConfirm?: boolean;
  onConfirm: (features: WorkflowFeature[]) => void | Promise<void>;
}

export interface SubmissionGate {
  submit: (command: () => void | Promise<void>) => boolean;
  observeBusy: (busy: boolean) => void;
}

export function createSubmissionGate(): SubmissionGate {
  let locked = false;
  let observedBusy = false;

  return {
    submit(command) {
      if (locked) return false;
      locked = true;
      try {
        void Promise.resolve(command()).catch(() => {
          locked = false;
        });
      } catch {
        locked = false;
      }
      return true;
    },
    observeBusy(busy) {
      if (busy) {
        observedBusy = true;
        locked = true;
      } else if (observedBusy) {
        observedBusy = false;
        locked = false;
      }
    },
  };
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

export function FeatureReviewWorkspace({ mode, features, preview, busy, canConfirm = true, onConfirm }: FeatureReviewWorkspaceProps) {
  const [draftEdits, setDraftEdits] = useState<Record<string, Partial<FeatureDraft>>>({});
  const [activeFeatureIndex, setActiveFeatureIndex] = useState(0);
  const [submissionGate] = useState(createSubmissionGate);
  const featureCount = features.length;
  const activeIndex = featureCount === 0 ? 0 : Math.min(activeFeatureIndex, featureCount - 1);
  const activeFeature = features[activeIndex];

  useEffect(() => {
    submissionGate.observeBusy(busy);
  }, [busy, submissionGate]);

  function draftFor(feature: WorkflowFeature): FeatureDraft {
    return { ...draftFromFeature(feature), ...draftEdits[feature.id] };
  }

  function updateDraft(feature: WorkflowFeature, patch: Partial<FeatureDraft>) {
    setDraftEdits((current) => ({ ...current, [feature.id]: { ...current[feature.id], ...patch } }));
  }

  function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || featureCount === 0) return;
    submissionGate.submit(() => onConfirm(features.map((feature) => mergeFeatureDraft(feature, draftFor(feature)))));
  }

  function selectFeature(index: number) {
    if (busy || featureCount === 0) return;
    setActiveFeatureIndex(Math.min(Math.max(index, 0), featureCount - 1));
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
          <span>{featureCount} 项特征</span>
        </header>

        {activeFeature ? (
          <div className="forge-feature-review__pager" data-testid="feature-pager">
            <div className="forge-feature-review__pager-bar">
              <button type="button" disabled={busy || activeIndex === 0} onClick={() => selectFeature(activeIndex - 1)}>
                上一项
              </button>
              <output data-testid="feature-current-index" aria-live="polite">
                第 {activeIndex + 1} / {featureCount} 项
              </output>
              <button type="button" disabled={busy || activeIndex >= featureCount - 1} onClick={() => selectFeature(activeIndex + 1)}>
                下一项
              </button>
            </div>

            <div className="forge-feature-review__index" role="tablist" aria-label="特征分页">
              {features.map((feature, index) => (
                <button
                  aria-label={`查看第 ${index + 1} 项特征：${feature.label}`}
                  aria-selected={index === activeIndex}
                  disabled={busy}
                  key={feature.id}
                  onClick={() => selectFeature(index)}
                  role="tab"
                  type="button"
                >
                  {index + 1}
                </button>
              ))}
            </div>

            {(() => {
              const feature = activeFeature;
              const draft = draftFor(feature);
              return (
                <article className="forge-feature" data-testid="feature-row" key={feature.id}>
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
                    <div><dt>置信度</dt><dd data-testid="feature-confidence">{feature.confidence === null ? "未提供" : `${feature.confidence}（原始值）`}</dd></div>
                    <div><dt>缺失原因</dt><dd>{feature.missing_reason ?? "无"}</dd></div>
                    <div><dt>审阅状态</dt><dd>{reviewStatusLabels[feature.review_status]}</dd></div>
                  </dl>
                </article>
              );
            })()}
          </div>
        ) : (
          <div className="forge-feature-review__empty" data-testid="feature-empty">
            暂无可审阅特征，等待图纸解析结果。
          </div>
        )}

        {canConfirm ? (
          <button
            className="forge-feature-review__primary"
            data-testid={mode === "annotation" ? "finalize-annotations" : "confirm-review"}
            type="submit"
            disabled={busy || featureCount === 0}
            aria-busy={busy}
          >
            {mode === "annotation" ? "确认标注" : "确认审阅并生成工艺"}
          </button>
        ) : <p className="forge-feature-review__readonly">此步骤已完成，当前为回看模式。</p>}
      </form>
    </section>
  );
}
