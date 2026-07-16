# Three.js drawing visual companion design

## Goal

Build a separate visual-companion workspace that can switch between the existing abstract sphere scene and a new Three.js inferred part scene. The part scene is derived from 2D drawing features and should communicate approximate structure at the same fidelity level as the current sphere-style visual layer, not claim CAD or STEP precision.

## Product Positioning

This is an engineering review aid. It helps users understand what the AI thinks the drawing represents and compare extracted features against a spatial proxy. It is not a manufacturing model, measurement authority, or CAD reverse-engineering tool.

The interface must use precise language:

- Use `推测结构`, `视觉伴侣`, `近似模型`, `由二维图纸特征推断`.
- Do not use `精确三维模型`, `CAD 重建`, `可制造模型`, or `STEP 级`.

## Page Model

Create a new Three.js visual-companion surface rather than putting this inside the current feature form. The current four-step workflow remains the source of truth for upload, annotation, review, process generation, recovery, and export.

The page should have:

- A top tab bar with at least two tabs:
  - `视觉球体`: the current abstract sphere/companion scene.
  - `推测零件`: the inferred mechanical part scene.
- A full visual stage below the tab bar.
- A compact side or bottom inspection strip for the active tab:
  - For the sphere tab: scene status and workflow context.
  - For the part tab: inferred part type, feature count, certainty notes, and currently highlighted feature.

## Inferred Part Scene

The initial supported inference target is an axis-like machined part, because the provided drawing is a valve stem / shaft-like part.

The first version should derive a deterministic proxy from available task snapshot data:

- Use `drawing.name`, `features`, and `review.raw_text`.
- Extract likely diameter and length cues from feature labels/evidence text with conservative regex parsing.
- Use the largest length-like value for approximate x-axis length.
- Use diameter-like values for stepped cylinder radii.
- If parsing is weak, fall back to a stable multi-segment shaft silhouette.

Visual representation:

- Build the model as grouped cylinders along one axis.
- Add rings or shallow torus bands for thread-like and groove-like features.
- Use repeated radial teeth or small boxes for spline/gear-like cues when text mentions `12等分`, `花键`, or `齿`.
- Use subtle material differences for uncertainty:
  - solid metal for confident base shaft;
  - translucent/dashed accent bands for inferred or low-confidence details.
- Keep the model inspectable with orbit controls.

Accuracy boundary:

- Relative proportions should look plausible.
- Exact dimensions are not guaranteed.
- The UI must not let users treat this as the source of truth over the 2D drawing or extracted feature fields.

## Tab Bar and GSAP Transition

Switching tabs should feel spatial and fluid.

Interaction:

1. User clicks `视觉球体` or `推测零件`.
2. A black/white vortex overlay expands over the stage.
3. The outgoing scene fades/scales down under the vortex.
4. The incoming scene fades/scales in after the midpoint.
5. The vortex collapses, leaving the new tab active.

Implementation constraints:

- Use GSAP for the vortex timeline.
- Animate only transform and opacity for DOM layers.
- Use a CSS radial/conic visual for the vortex mask; do not block rendering with shader complexity in v1.
- Transition duration target: 650-900ms.
- Respect `prefers-reduced-motion`: replace the vortex with a simple 150ms crossfade.
- The tab buttons must remain keyboard accessible.

## Data Flow

The visual companion consumes the same v1 workflow snapshot already loaded by `GeneratePage`.

Minimum integration path:

- Add a new `visual` workflow step or a separate workspace entry reachable from the current workflow UI.
- Pass `snapshot.drawing`, `snapshot.features`, and `snapshot.review.raw_text` to the visual companion.
- Do not create new backend APIs in the first version.
- Do not persist inferred model geometry in v1.

## Components

Suggested component boundaries:

- `VisualCompanionWorkspace`
  - owns tab state and GSAP transition state.
- `CompanionTabBar`
  - accessible tab list and keyboard semantics.
- `CompanionSphereScene`
  - wraps or reuses the existing sphere scene style.
- `InferredPartScene`
  - Three.js canvas for the part proxy.
- `inferPartModel`
  - pure helper that converts snapshot text/features into simple segment/ring/tooth descriptors.

## UX Quality Bar

- The part model must not render blank.
- Canvas must resize correctly at desktop and narrow widths.
- No horizontal page overflow.
- Text must not overlap controls.
- Motion must not trap focus or delay commands.
- Loading and fallback states must state exactly what is unavailable.

## Testing

Add tests at three levels:

- Pure inference tests for `inferPartModel`.
- Component render tests for tab bar semantics and reduced-motion fallback hooks where practical.
- Browser verification:
  - open the visual companion;
  - capture sphere tab;
  - switch to part tab;
  - confirm canvas is nonblank;
  - confirm tab state and labels;
  - capture desktop and mobile screenshots.

## Open Constraints

- This design assumes the current Three.js dependencies remain in `package.json`.
- The first implementation should not attempt CAD-grade boolean operations, STEP export, mesh repair, or exact dimension validation.
- The first implementation should focus on one strong shaft-like proxy for the provided drawing before broadening to arbitrary part classes.
