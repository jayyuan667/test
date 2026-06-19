# Review Follow-up Design

## Goal

Address two regressions introduced by the recent fallback and responsive changes:

1. Prevent degraded vision reports from poisoning the reusable feature cache.
2. Restore expected sidebar behavior when resizing back to desktop widths.

## Scope

This document covers only the follow-up fixes for the review findings. It does not redesign the broader upload pipeline, cache model, or frontend layout system.

## Problem 1: Degraded Feature Cache Poisoning

### Current Behavior

When remote vision analysis fails, the upload flow now produces a degraded feature report from annotation text or local fallback output. That degraded report is still eligible for SHA-based cache persistence. A later upload of the same file can hit this cache entry and skip remote VLM extraction entirely, even if the external service has recovered.

### Desired Behavior

Only cache reports that are considered canonical enough to safely reuse as a substitute for fresh VLM analysis.

### Design

Add an explicit cacheability gate in the upload pipeline:

- Treat any report generated from degraded vision flow as `non-cacheable`.
- Detect degradation from task/result metadata rather than by inferring from text content.
- Skip writing cache entries when `vision_degraded == True`.
- Continue reading older valid cache entries as before.

### Implementation Direction

Relevant file: [upload.py](F:/Work_Dir/2D-v/backend/api/upload.py)

- Ensure degraded paths always set `task["vision_degraded"] = True`.
- At the feature-cache write site, guard persistence with `if not task.get("vision_degraded")`.
- Preserve existing behavior for full remote-success and acceptable non-degraded local-success paths only if they are intentionally cacheable.

### Risks

- If local fallback output is high quality but marked degraded, cache reuse becomes more conservative. This is acceptable because correctness is more important than reuse.

## Problem 2: Sidebar Resize Regression

### Current Behavior

The resize handler forces `collapsed = true` below `1024px`, but does not restore desktop-expanded state when the viewport returns above that breakpoint.

### Desired Behavior

Responsive auto-collapse should be symmetric:

- Below desktop breakpoint: collapse automatically.
- Returning to desktop breakpoint or above: restore expanded state unless the user is currently in a deliberate mobile-sized layout mode.

### Design

Use breakpoint-driven state reconciliation instead of one-way forcing:

- Track whether the current viewport is mobile/tablet vs desktop.
- When crossing from desktop to narrow width, force collapse.
- When crossing from narrow width back to desktop, force expand.
- Avoid repeated writes on every resize event; only react when the breakpoint side changes.

### Implementation Direction

Relevant file: [App.tsx](F:/Work_Dir/2D-v/frontend/src/App.tsx)

- Replace the current one-way resize logic with breakpoint transition logic.
- Keep manual user toggling intact during steady-state desktop or steady-state mobile widths.

## Validation

### Backend

- Upload a drawing that triggers degraded vision fallback.
- Confirm no reusable feature cache entry is written for that run.
- Re-run the same drawing after remote VLM recovery and confirm fresh VLM analysis executes.

### Frontend

- Start above `1024px`: sidebar should be expanded.
- Resize below `1024px`: sidebar should collapse.
- Resize back above `1024px`: sidebar should expand automatically.

## Acceptance Criteria

- Degraded upload results never suppress future healthy VLM analysis through cache reuse.
- Sidebar state matches viewport breakpoint transitions without requiring manual recovery after resizing.
