# React Frontend Build Checklist

## Branch Workspace

- Workspace root: `F:\Work_Dir\2D-r`
- Frontend source: `F:\Work_Dir\2D-r\frontend-react`
- Backend URL: `http://127.0.0.1:5190`
- Frontend development URL: `http://127.0.0.1:3200`
- Frontend preview URL: `http://127.0.0.1:3201`

## Build Output

- Build command: `npm run build`
- Current JS bundle: `frontend-react/dist/assets/index-Cf7ychIO.js`
- Current CSS bundle: `frontend-react/dist/assets/index-C63WlPJx.css`

## Required Checks

1. Run `npm install` in `frontend-react`.
2. Run `npm run build`.
3. Confirm `frontend-react/dist/index.html` references the current bundles.
4. Start the backend on port `5190` and the development frontend on port `3200`.
5. Verify the upload, YOLO review, feature review, process generation, database, and history flows.

## Isolation Check

- Do not point this workspace at the original `2D-v` source tree.
- Do not reuse ports `5090`, `3100`, or `3101`.
- Keep frontend dependencies under `frontend-react/node_modules`.
- The backend serves production assets only from `frontend-react/dist`.
