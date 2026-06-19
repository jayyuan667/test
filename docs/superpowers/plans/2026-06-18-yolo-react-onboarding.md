# yolo-react Onboarding Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `yolo-react` branch independently installable and runnable by a new remote developer.

**Architecture:** Keep one source of truth for ports and directory names across documentation and scripts. Separate first-time installation from daily startup, and clearly distinguish core requirements from optional CAD/PDF integrations.

**Tech Stack:** Markdown, Windows Batch, PowerShell, Python/Flask, React/Vite, npm.

---

### Task 1: Rewrite user-facing documentation

**Files:**
- Modify: `README.md`
- Modify: `INSTALL.md`
- Modify: `START.md`
- Modify: `BRANCH_DEVELOPMENT.md`

- [x] Replace corrupted and legacy instructions with UTF-8 documentation.
- [x] Document cloning the `yolo-react` branch.
- [x] Document `.env` creation and required API keys.
- [x] Document ports `5190`, `3200`, and `3201`.
- [x] Document empty local database behavior and optional integrations.

### Task 2: Update first-time setup

**Files:**
- Modify: `setup.bat`

- [x] Check Python 3.11/3.12, Node.js, and npm.
- [x] Create `.venv`.
- [x] Install `backend/requirements.txt`.
- [x] Run `npm install` in `frontend-react`.
- [x] Copy `.env.example` to `.env` without overwriting existing configuration.
- [x] Print exact daily startup commands and URLs.

### Task 3: Validate and publish

**Files:**
- Verify: `start.ps1`
- Verify: `frontend-react/package.json`
- Verify: `frontend-react/vite.config.ts`

- [x] Scan documentation and scripts for stale directory names and ports.
- [x] Run `npm run build`.
- [x] Compile changed Python files.
- [x] Parse `start.ps1`.
- [x] Run GitNexus change detection.
- [x] Commit and push `yolo-react`.
