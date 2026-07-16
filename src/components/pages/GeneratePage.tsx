"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { DrawingWorkspace } from "@/components/workflow/DrawingWorkspace";
import { FeatureReviewWorkspace } from "@/components/workflow/FeatureReviewWorkspace";
import { ProcessWorkspace } from "@/components/workflow/ProcessWorkspace";
import { UploadWorkspace } from "@/components/workflow/UploadWorkspace";
import { WorkflowFeedback } from "@/components/workflow/WorkflowFeedback";
import { WorkflowStepper } from "@/components/workflow/WorkflowStepper";
import {
  canInspectStep,
  reachedStepForSnapshot,
  type WorkflowStepId,
} from "@/components/workflow/workflow-step-model";
import "@/components/workflow/workflow.css";
import { createDrawingWorkflowController, type DrawingWorkflowController } from "@/features/drawing-workflow/controller";
import type { WorkflowError, WorkflowState } from "@/features/drawing-workflow/types";
import { workflowService } from "@/services";

import { LegacyGeneratePage } from "./LegacyGeneratePage";

const useWorkflowV1 = process.env.NEXT_PUBLIC_USE_WORKFLOW_V1 !== "false";
const activeTaskKey = "forge-v1-active-task";
const initialState: WorkflowState = {
  snapshot: null,
  operationsById: {},
  operationOrder: [],
  lastSeq: 0,
  connection: "idle",
  error: null,
};

function localWorkflowError(message: string): WorkflowError {
  return { code: "ui_action_failed", message, retryable: true, phase: null, details: {} };
}

function V1GeneratePage() {
  const controllerRef = useRef<DrawingWorkflowController | null>(null);
  const previewLoadRef = useRef(0);
  const previewTaskRef = useRef<string | null>(null);
  const previewPromisesRef = useRef(new Map<string, Promise<string>>());
  const actionInFlightRef = useRef(false);
  const [state, setState] = useState<WorkflowState>(initialState);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [loadedPreviews, setLoadedPreviews] = useState<{ signature: string; urls: string[] }>({ signature: "", urls: [] });
  const [activePage, setActivePage] = useState(0);
  const [selectedStep, setSelectedStep] = useState<WorkflowStepId>("upload");
  const [followLatest, setFollowLatest] = useState(true);

  useEffect(() => {
    const controller = createDrawingWorkflowController(workflowService);
    controllerRef.current = controller;
    const unsubscribe = controller.subscribe(setState);
    const savedTask = localStorage.getItem(activeTaskKey);
    if (savedTask) {
      void controller.start(savedTask).catch((error: Error) => setMessage(error.message));
    }
    return () => {
      previewLoadRef.current += 1;
      unsubscribe();
      controller.dispose();
      controllerRef.current = null;
    };
  }, []);

  const snapshot = state.snapshot;
  const previewSources = snapshot?.drawing.preview_urls ?? [];
  const previewSignature = `${snapshot?.task.id ?? "none"}:${snapshot?.task.revision ?? 0}:${previewSources.join("\u001f")}`;

  useEffect(() => {
    const loadId = ++previewLoadRef.current;
    const controller = controllerRef.current;
    if (!controller || previewSources.length === 0) return;
    const taskId = snapshot?.task.id ?? null;
    if (previewTaskRef.current !== taskId) {
      previewTaskRef.current = taskId;
      previewPromisesRef.current.clear();
    }

    void Promise.all(
      previewSources.map((source) => {
        const pending = previewPromisesRef.current.get(source);
        if (pending) return pending;
        const request = controller
          .loadPreview(source)
          .catch(() => "")
          .finally(() => {
            if (previewPromisesRef.current.get(source) === request) {
              previewPromisesRef.current.delete(source);
            }
          });
        previewPromisesRef.current.set(source, request);
        return request;
      }),
    ).then((loaded) => {
      if (loadId !== previewLoadRef.current) return;
      setLoadedPreviews({ signature: previewSignature, urls: loaded });
      setActivePage(0);
      if (loaded.some((url) => !url)) setMessage("部分图纸预览加载失败，可继续审阅已加载页面。");
    });

    return () => { previewLoadRef.current += 1; };
    // previewSignature is a stable value identity for task, revision, and page order.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewSignature]);

  const reachedStep = reachedStepForSnapshot(snapshot);
  const viewStep: WorkflowStepId = !snapshot
    ? "upload"
    : followLatest || !canInspectStep(selectedStep, reachedStep)
      ? reachedStep
      : selectedStep;
  const previewUrls = loadedPreviews.signature === previewSignature ? loadedPreviews.urls : [];

  useEffect(() => {
    if (snapshot?.task.state !== "cancelled") return;
    localStorage.removeItem(activeTaskKey);
    controllerRef.current?.reset();
  }, [snapshot?.task.state]);

  async function run(action: (controller: DrawingWorkflowController) => Promise<void>) {
    const controller = controllerRef.current;
    if (!controller || actionInFlightRef.current) return;
    actionInFlightRef.current = true;
    setBusy(true);
    setMessage(null);
    try {
      await action(controller);
      const taskId = controller.getState().snapshot?.task.id;
      if (taskId) localStorage.setItem(activeTaskKey, taskId);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "操作失败");
    } finally {
      actionInFlightRef.current = false;
      setBusy(false);
    }
  }

  function selectStep(step: WorkflowStepId) {
    setSelectedStep(step);
    setFollowLatest(step === reachedStep);
  }

  function clearCurrentTask() {
    if (busy) return;
    previewLoadRef.current += 1;
    previewTaskRef.current = null;
    previewPromisesRef.current.clear();
    localStorage.removeItem(activeTaskKey);
    controllerRef.current?.reset();
    setFile(null);
    setLoadedPreviews({ signature: "", urls: [] });
    setActivePage(0);
    setSelectedStep("upload");
    setFollowLatest(true);
    setMessage(null);
  }

  function drawingWorkspace() {
    if (!snapshot) return null;
    return (
      <DrawingWorkspace
        drawing={snapshot.drawing}
        previewUrls={previewUrls}
        activePage={activePage}
        onPageChange={setActivePage}
      />
    );
  }

  const operations = useMemo(
    () => state.operationOrder.map((id) => state.operationsById[id]).filter(Boolean),
    [state.operationOrder, state.operationsById],
  );
  const feedbackError = message ? localWorkflowError(message) : state.error;

  let workspace;
  if (viewStep === "upload") {
    workspace = (
      <UploadWorkspace
        file={file}
        busy={busy}
        onFileChange={setFile}
        onStart={() => {
          if (!file) return;
          setFollowLatest(true);
          void run((controller) => controller.upload(file));
        }}
      />
    );
  } else if (snapshot && viewStep === "annotation") {
    workspace = (
      <FeatureReviewWorkspace
        mode="annotation"
        features={snapshot.features}
        preview={drawingWorkspace()}
        busy={busy}
        canConfirm={snapshot.task.state === "awaiting_annotation"}
        onConfirm={(features) => {
          setFollowLatest(true);
          return run((controller) => controller.finalizeAnnotations({ features }));
        }}
      />
    );
  } else if (snapshot && viewStep === "review") {
    workspace = (
      <FeatureReviewWorkspace
        mode="review"
        features={snapshot.features}
        preview={drawingWorkspace()}
        busy={busy}
        canConfirm={snapshot.task.state === "awaiting_review"}
        onConfirm={(features) => {
          setFollowLatest(true);
          return run((controller) => controller.submitReview({
            review_text: snapshot.review.raw_text ?? "",
            features,
          }));
        }}
      />
    );
  } else if (snapshot && viewStep === "process") {
    workspace = (
      <ProcessWorkspace
        operations={operations}
        taskState={snapshot.task.state}
        phase={snapshot.task.phase}
        progress={snapshot.task.progress}
        connection={state.connection}
        error={feedbackError}
        onExport={() => {
          const controller = controllerRef.current;
          if (controller) window.location.assign(controller.exportUrl());
        }}
      />
    );
  }

  return (
    <main className="forge-workflow" data-testid="v1-workflow">
      <header className="forge-workflow__masthead">
        <div>
          <p className="forge-eyebrow">AI PROCESS PLANNING</p>
          <h1>工艺生成</h1>
        </div>
        {snapshot ? (
          <div className="forge-workflow__task-actions">
            <p className="forge-workflow__drawing-name">{snapshot.drawing.name}</p>
            <button
              className="forge-workflow__clear-task"
              data-testid="clear-workflow-task"
              disabled={busy}
              onClick={clearCurrentTask}
              type="button"
            >
              清除当前任务
            </button>
          </div>
        ) : null}
      </header>

      <WorkflowStepper current={viewStep} reached={reachedStep} onSelect={selectStep} busy={busy} />

      {viewStep !== "process" ? (
        <WorkflowFeedback state={snapshot?.task.state ?? null} connection={state.connection} error={feedbackError} />
      ) : null}

      <div className="forge-workflow__active" data-step={viewStep} key={viewStep}>{workspace}</div>
    </main>
  );
}

export function GeneratePage() {
  return useWorkflowV1 ? <V1GeneratePage /> : <LegacyGeneratePage />;
}
