# FORGE workstation fusion verification

## Result

- Date: 2026-07-16 12:45-12:47 CST
- Fixture: `/Users/caojiayuan/Documents/测试包/drawing/test.png`
- Frontend: `http://localhost:3002`
- Backend: `http://localhost:5390`, started with `FLASK_DEBUG=0 BACKEND_PORT=5390`
- Task ID: `f53b4477-75ac-4f53-86aa-f4af5cbefded`
- Final task state: `completed / done / 100%`, revision `3445`
- Extracted features: 25
- Structured operations: 13
- Process table markdown fence check: passed, no ``` in operation table or sanitized operations
- Export: `Process_f53b4477.pdf`, 232260 bytes, `%PDF` header

## Browser acceptance

Command:

```bash
PW_TEST_HTML_REPORT_OPEN=never npx playwright test --config=e2e/playwright.prod.config.ts e2e/v1-workflow.spec.ts --reporter=line
```

Result:

```text
1 passed (2.0m)
```

Covered checkpoints:

- Login with real backend.
- Upload `test.png`.
- Four-step workstation navigation: upload, annotation, review, process.
- Real drawing preview visible.
- Annotation confirmation and review confirmation issue v1 controller commands.
- Feature review renders real extracted features and explicit missing confidence.
- Process table renders structured operations and rejects markdown fence pollution.
- Historical upload-step inspection shows the selected file and does not expose `closed · seq`.
- Returning to process step preserves operation count.
- Page reload restores the same active task ID from `forge-v1-active-task`.
- PDF export response is `application/pdf`, suggested filename ends in `.pdf`, saved file begins with `%PDF`.

## Visual QA

Screenshots were captured outside Git:

- `/tmp/forge-workstation-fusion/1440x1000.png`
- `/tmp/forge-workstation-fusion/1024x768.png`
- `/tmp/forge-workstation-fusion/390x844.png`

The process workstation remains readable at desktop, tablet, and narrow mobile widths. The narrow view uses the table fallback rows instead of clipping process cells.

## Evidence

Evidence files are under `/tmp/forge-v1-evidence/` and are not committed:

- `task-id.txt`
- `final-snapshot.json`
- `events-sanitized.json`
- `01-real-phase.png`
- `02-structured-operation.png`
- `03-resumed-complete.png`
- `Process_f53b4477.pdf`
- `browser-diagnostics.txt`

## Gates

- `npm run test:workflow`: 45 passed.
- `npx --no-install tsx --test $(rg --files src/components/workflow | rg '\.test\.tsx?$')`: 18 passed.
- `npx eslint src/components/pages/GeneratePage.tsx src/components/workflow e2e/v1-workflow.spec.ts`: exit 0.
- `npx tsc --noEmit`: exit 0.
- `npm run build`: exit 0.
- `.venv/bin/python -m pytest backend/test_task_events_v1.py backend/test_task_contract_v1.py backend/test_tasks_api_v1.py backend/test_sse_events.py -q`: 71 passed.
- `git diff --check`: exit 0.

## Runtime note

The backend default debug reloader can terminate during long browser runs. Final acceptance used `FLASK_DEBUG=0 BACKEND_PORT=5390 ./.venv/bin/python -m backend.app`, which kept port 5390 stable for the full E2E.
