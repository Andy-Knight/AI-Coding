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
- Current v0.10.9 queue jobs target a specific printer and assume the file is already present there.
- Next queue milestone is **file-centric scheduling** with a **Next available compatible printer** mode. The controller should retain/stage the G-code, select an eligible printer, distribute and verify the file if needed, perform printer-specific preflight, then start it.
- Compatibility must be evaluated centrally from normalized printer capabilities/status, while printer-specific preflight remains behind the adapter boundary.
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

Design and implement **Next available compatible printer** scheduling by extending the persistent queue from printer-centric jobs to optionally file-centric jobs.

A file-centric queued job should be able to wait without a fixed printer. The controller should determine which printers can safely run it, expose eligible/blocked reasons in the UI, choose an appropriate idle printer, ensure the G-code is present on that printer, verify upload, run printer-specific preflight, and start the print.

Compatibility considerations:

- Printer/manufacturer capabilities.
- Number of required tools.
- Required nozzle diameter.
- Loaded material and colour where known.
- U1 logical-to-physical tool mapping/readiness.
- Printer online/idle state.
- Outstanding bed-clearance interlock.
- Whether the file already exists on the printer (optimization, not a hard requirement once staging/distribution exists).

Target UI state should clearly distinguish jobs such as **Queued — waiting for compatible printer**, and show eligible printers plus blocked printers with reasons (for example, bed not cleared, wrong nozzle, material mismatch, offline/busy).

## Next steps

1. Add **persistent staged queue files** so the controller owns a durable copy of queued G-code instead of requiring the file to pre-exist on a printer.
2. Define a normalized **compatibility engine** returning eligible/blocked printers with explicit reason codes/messages.
3. Add **automatic printer selection** for file-centric jobs while preserving existing fixed-printer queue behavior for backward compatibility.
4. Reuse/extend verified file distribution so the staged file is uploaded only when required and verified before start.
5. Run the selected printer's existing **printer-specific preflight** immediately before start; changed filament/nozzle/tool state must not be silently ignored.
6. Extend queue persistence/restart reconciliation, cancellation, reprint/history, SSE payloads and UI for unassigned/file-centric jobs.
7. Add regression tests for compatibility decisions, scheduling fairness/races, restart persistence, bed-clearance blocking, upload failure and preflight failure.
8. Increment the application version when the milestone is delivered and update README/context accordingly.

## Handoff rule

If chat context and this file disagree about the codebase, inspect the current GitHub files and tests. **GitHub is authoritative for code; this document is authoritative for project intent/status until deliberately updated.**
