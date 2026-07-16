# Feature review pager and transition design

## Goal

Improve the current feature review step by replacing the long stacked feature form with a focused one-feature-at-a-time review panel, and make workflow/feature transitions feel smoother without changing the v1 backend workflow.

## Scope

- Keep upload, annotation, review, process generation, SSE recovery, and export behavior unchanged.
- Modify only the current workflow UI surface.
- Defer the Three.js visual companion to a separate feature.

## UX Direction

The feature review panel should behave like a controlled engineering inspection station:

- Show one active feature at a time.
- Provide previous/next controls and a compact feature index.
- Show `第 N / M 项` so the user understands review progress.
- Preserve edits for every feature while paging.
- Submit all features, not only the active page.
- Preserve historical read-only mode.

The visual style should stay restrained and task-focused:

- No decorative cards or marketing animation.
- Use existing FORGE dark/industrial tokens.
- Keep controls keyboard accessible.
- Use 150-250ms transform/opacity transitions.
- Respect `prefers-reduced-motion`.

## Component Behavior

`FeatureReviewWorkspace` owns:

- `activeFeatureIndex`
- existing draft edit state
- next/previous/select handlers

If `features.length === 0`, the panel shows an empty state and disables the confirm button.

If features change and the active index is out of range, clamp it to the last available feature.

The current feature article remounts by feature id so CSS can animate the content change.

## Workflow Step Transition

`GeneratePage` should make the active workspace container transition between steps. The transition should be purely presentational and must not alter controller ownership or task state.

Use CSS animation on `.forge-workflow__active` keyed by `viewStep`. Reduced-motion users get no movement.

## Testing

- Static render confirms one active feature is shown instead of all feature forms.
- Static render confirms pager controls and progress copy.
- Static render confirms empty state for zero features.
- Existing submission gate and draft merge tests remain.
- Workflow/component tests and scoped lint/type/build gates must pass.
