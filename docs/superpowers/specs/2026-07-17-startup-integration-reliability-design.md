# Startup and integration reliability design

## Goal

Make local startup predictable for the Forge drawing workflow so frontend/backend integration can be tested without repeatedly hitting ambiguous `python` command failures, wrong backend ports, or silent port conflicts.

## Current problems

- `start-backend.sh` calls `python app.py` from `backend/`, which fails on macOS environments where only `python3` or `.venv/bin/python` exists.
- Backend code defaults to port `5190`, while the active workflow documentation and frontend integration expect `5390`.
- Port conflicts on `3002` and `5390` produce raw framework errors instead of actionable diagnostics.
- Startup commands are split between shell snippets and ad-hoc terminal commands, making it easy to start a stale backend or frontend process.

## Recommended approach

Create a small, explicit startup contract:

1. Backend startup uses the project virtual environment when available: `./.venv/bin/python -m backend.app`.
2. Backend startup defaults to `BACKEND_PORT=5390`, while preserving caller overrides.
3. Scripts check whether the requested port is already listening before starting, and print the owning PID plus the exact `kill` command for the user. The script should not auto-kill processes.
4. `package.json` exposes clear commands for common workflows:
   - `dev:frontend` for Next development on port `3002`.
   - `start:frontend` for production Next serving on port `3002`.
   - `start:backend` for backend startup.
   - `start:all` only if it can remain dependency-light and readable.
5. A lightweight regression test or static check verifies the backend script does not regress to `python app.py` and keeps `5390` as the documented default.

## Scope

In scope:

- Startup scripts and npm scripts.
- Documentation snippets directly tied to startup.
- Tests/static checks for startup command correctness.

Out of scope:

- Killing ports automatically.
- Adding a full process manager or daemon.
- Changing backend API behavior.
- Changing frontend workflow UI.
- Committing local runtime state such as databases, logs, uploads, output files, or secret/config JSON.

## Data and control flow

Backend startup:

1. User runs `npm run start:backend` or `./start-backend.sh`.
2. Script resolves project root.
3. Script chooses Python interpreter:
   - first `./.venv/bin/python`;
   - otherwise `python3`;
   - if neither exists, fail with a clear installation message.
4. Script sets `BACKEND_PORT=${BACKEND_PORT:-5390}`.
5. Script checks whether the port is listening.
6. If occupied, it exits with the PID and suggested command.
7. If free, it starts `python -m backend.app` from the project root.

Frontend startup:

1. User runs `npm run dev:frontend` or `npm run start:frontend`.
2. Command uses port `3002`.
3. If a port-check wrapper is added, it follows the same “diagnose, do not kill” rule.

## Error handling

The startup UX should prefer concrete messages:

- Missing interpreter: explain `.venv` is missing and `python3` fallback failed.
- Occupied backend port: print `Port 5390 is already in use by PID <pid>` and `kill <pid>` as the manual cleanup option.
- Occupied frontend port: print equivalent message for `3002`.
- Backend startup should run with `FLASK_DEBUG=0` by default unless the caller explicitly sets it.

## Testing plan

- Add a test that inspects `start-backend.sh` and asserts:
  - it does not contain `python app.py`;
  - it uses `-m backend.app`;
  - it defaults `BACKEND_PORT` to `5390`;
  - it contains a port conflict check.
- Run backend workflow tests already covering task/event behavior.
- Run frontend workflow tests to confirm package script changes do not affect runtime code.

## Risks and mitigations

- Risk: `package.json` already has unrelated local changes. Mitigation: inspect and patch only script entries needed for startup.
- Risk: shell scripts behave differently across macOS/Linux. Mitigation: use POSIX-compatible shell where possible and `lsof`, which is already what the user used on macOS.
- Risk: auto-killing the wrong process. Mitigation: scripts only diagnose and provide manual commands.

## Acceptance criteria

- A fresh developer can start the backend with one command and it binds to `5390`.
- The backend script works without a global `python` command.
- If `5390` or `3002` is occupied, the user receives a clear PID-level message.
- Startup changes are covered by at least one automated check.
- No runtime artifacts, local config JSON, database files, or secrets are committed.
