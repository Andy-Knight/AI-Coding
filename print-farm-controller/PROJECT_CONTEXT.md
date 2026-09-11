# Printer Fleet Controller — Project Context

> Cross-chat handoff file. Read this first when continuing the project in a new chat. Keep it concise and update it whenever architecture/decisions change, a task is completed, or the current/next task changes.

## Source of truth

- Repository: `Andy-Knight/AI-Coding`
- Project path: `print-farm-controller/`
- Branch: `main`
- Current application version: **0.10.9**
- Runtime: **Node.js 20+**, ES modules, no npm runtime dependencies.
- Current uploaded GitHub tree is the authoritative baseline for future work.

## Architecture

```text
Browser UI (`public/`)
        |
        v
Local Fleet Controller (`src/`)
        |
        +-- printer registry / persistent state
        +-- fleet state + SSE updates
        +-- camera manager
        +-- batch control
        +-- chamber preheat
        +-- file distribution / material metadata
        +-- persistent print queue + history + bed-clearance interlock
        |
        v
PrinterAdapter boundary (`src/adapters/`)
        +-- FlashForge Adventurer 5M / 5M Pro
        +-- Snapmaker U1 -> Moonraker / Klipper
```

Manufacturer-specific discovery, capabilities, limits, status normalization, files, print control, temperatures and camera selection belong behind the adapter boundary. Core fleet services should remain manufacturer-agnostic.

## Important decisions

- Local-first/LAN-only controller; printer credentials remain backend-side.
- Support multiple manufacturers through adapters rather than manufacturer logic in shared fleet code.
- Preserve the legacy application-data directory for upgrade compatibility.
- Queue/history is controller-side and persistent across restarts.
- A completed/active-failed/cancelled print creates a **bed-clearance interlock**; the next queued job for that printer must not start until **Bed cleared** is confirmed.
- Queue jobs currently target a specific printer; automatic compatible-printer scheduling is a future layer.
- FlashForge AD5M/Pro: local HTTP/TCP APIs, bed limit up to 110 °C on supported firmware, nozzle up to 265 °C.
- Snapmaker U1: native Moonraker/Klipper integration, four tools, stock camera workflow, native print preferences/tool mapping and stock calibration commands.
- Stored-file material checks are advisory for interactive printing; unsafe/ambiguous unattended queue starts are held for review where applicable.
- Every released/generated application version should increment the controller version shown by the application and update documentation/context as needed.

## Completed work / current baseline

- FlashForge Adventurer 5M / 5M Pro support.
- Snapmaker U1 support via Moonraker/Klipper, including camera streaming.
- Automatic/local printer discovery and persistent printer registry.
- Persistent controller-side printer renaming (v0.10.9).
- Dashboard ordering, live polling/SSE fleet state and diagnostics.
- Multi-printer selection/batch actions and verified G-code distribution.
- Persistent print queue, history, reprint, review state and bed-clearance safety interlock.
- Material metadata/preflight for FlashForge and multi-tool print setup/preflight for U1.
- U1 tool mapping, print preferences, material/nozzle readiness and XYZ toolhead offset calibration.
- Bed-powered timed chamber preheat and applicable fan/purifier controls.
- Controller version displayed in the UI and versioned with releases.
- Automated Node test suite covering the main backend/services and UI setup flows; v0.10.9 was previously verified with **89 passing tests**.

## Current task

Establish reliable cross-chat continuity. The v0.10.9 application has been manually uploaded to GitHub under `print-farm-controller/`, and `PROJECT_CONTEXT.md` is now the handoff document.

There is **no unfinished feature implementation currently recorded**. The next functional task should be set here when work begins.

## Next steps

1. At the start of a new chat, read this file plus `package.json` and the relevant source files before making changes.
2. Record the active feature/bug under **Current task** before or during substantial work.
3. Make changes against the GitHub baseline, run the relevant automated tests, and avoid regressions to existing printer support.
4. Increment the application version for a new delivered version and update README/context where appropriate.
5. When a task is complete, summarize the result under **Completed work**, replace **Current task**, and update **Next steps** rather than turning this file into a detailed changelog.

## Handoff rule

If chat context and this file disagree about the codebase, inspect the current GitHub files and tests. **GitHub is authoritative for code; this document is authoritative for project intent/status until deliberately updated.**
