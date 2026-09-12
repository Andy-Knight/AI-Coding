# Printer Fleet Controller — Project Context

> Cross-chat handoff file. Read this first when continuing the project in a new chat. Keep it concise and update it whenever architecture/decisions change, a task is completed, or the current/next task changes.

## Source of truth

- Repository: `Andy-Knight/AI-Coding`
- Project path: `print-farm-controller/`
- Branch: `main`
- Current application version: **0.12.2**
- Runtime: **Node.js 20+**, ES modules, no npm runtime dependencies.
- GitHub is the authoritative code baseline.

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
        +-- staged queue-file store
        +-- compatibility engine
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
- Multiple manufacturers are supported through adapters rather than manufacturer logic in shared fleet code.
- Default application data uses the manufacturer-neutral `Printer Fleet Controller` directory. v0.11.2 automatically migrates the complete historical `FlashForge Fleet` directory on first startup; custom `DATA_DIR` locations are never moved.
- Queue/history and controller-staged queue files persist across restarts.
- A completed/active-failed/cancelled print creates a **bed-clearance interlock**; no later queued job may start on that printer until **Bed cleared** is confirmed.
- Queue jobs support two assignment modes: **fixed printer** and **Next available compatible printer**.
- Automatic scheduling is file-centric: the controller owns a durable staged copy, evaluates compatibility/readiness, reserves one printer, uploads/verifies if required, performs a fresh live preflight, then starts.
- Compatibility and readiness are distinct. A printer may be compatible but temporarily blocked by offline/busy/bed-clearance/reservation state.
- Automatic compatibility returns explicit per-printer reasons and distinguishes **Eligible**, **Waiting**, **Needs review**, and **Not compatible**.
- Required nozzle size must not be guessed. If a printer cannot report an explicitly required nozzle, unattended scheduling requires review rather than assuming a match.
- U1 logical-to-physical tool mapping is derived from live material/colour/nozzle state and uses constrained matching to avoid greedy mapping errors.
- Production batches share one staged G-code across multiple run records. Pausing prevents not-yet-started copies from progressing, while active prints continue; cancelling remaining copies also catches copies still in upload/preflight without cancelling prints that have already started.
- Existing fixed-printer queue behaviour remains backward compatible.
- Every delivered version increments the application version and updates README/context.

## Completed work / current baseline

- FlashForge Adventurer 5M / 5M Pro support.
- Snapmaker U1 support via Moonraker/Klipper, including stock camera integration.
- Automatic/local discovery, persistent printer registry and controller-side printer renaming.
- Dashboard ordering, SSE fleet state, diagnostics and batch actions.
- Verified file distribution and printer-local file operations.
- Persistent queue/history/reprint/review states and bed-clearance safety interlock.
- Material metadata/preflight for FlashForge and multi-tool print setup/preflight for U1.
- U1 tool mapping, print preferences, material/nozzle readiness and XYZ offset calibration.
- Bed-powered timed chamber preheat and applicable fan/purifier controls.
- **v0.11.0 file-centric automatic queue:**
  - persistent controller-side staged queue files with SHA-256;
  - bounded G-code requirement extraction for tools/material/colour/nozzle metadata;
  - centralized compatibility/readiness engine with reason codes;
  - automatic printer selection and reservation;
  - U1 logical→physical tool-map generation;
  - staged-file upload and verification only when needed;
  - fresh printer-specific preflight immediately before start;
  - restart-safe automatic upload/preflight recovery;
  - cancellation-race protection;
  - queue UI showing Eligible / Waiting / Needs review / Not compatible;
  - fixed-printer jobs retained for backward compatibility.
- v0.11.0 regression suite: **100 passing tests, 0 failures**, including GitHub Actions verification of the release patch.
- **v0.11.1 FlashForge nozzle designation:** persistent per-printer controller nozzle diameter, normalized into FlashForge tool status and enforced by file-centric automatic queue compatibility; explicit nozzle matches can run unattended and mismatches are blocked.
- v0.11.1 regression suite: **105 passing tests, 0 failures**, including GitHub Actions verification.
- **v0.11.2 neutral data directory:** default controller storage no longer contains `FlashForge`; existing printer registry, queue/history, staged queue files, and metadata migrate automatically to the new manufacturer-neutral directory.
- v0.11.2 regression suite: **106 passing tests, 0 failures**, including an end-to-end legacy-directory migration test in GitHub Actions.
- **v0.11.3 staged-file cleanup:** clearing print history immediately removes controller-staged queue files that have no remaining queue/history reference; shared/referenced files are retained.
- **v0.12.0 production quantity / batch printing:** one staged G-code can create 2–999 run records sharing the same file; automatic scheduling can distribute copies across multiple compatible printers concurrently, with batch progress, pause/resume, cancel remaining, and safe quantity adjustment.
- v0.12.0 regression suite: **113 passing tests, 0 failures**, including concurrent assignment plus pause/cancel race coverage during staged upload.
- **v0.12.1 cancelled-history reprint regression:** automated coverage now guarantees a cancelled automatic queued job remains reprintable from Recent history using the same staged controller file and print options; UI coverage verifies cancelled history retains the Reprint action.
- v0.12.1 regression suite: **115 passing tests, 0 failures**.
- **v0.12.2 production batch reprint:** finished production batches in Recent history expose **Reprint batch**, creating a fresh automatic batch with the same quantity, staged controller file and print options while preserving the original history.
- v0.12.2 regression suite: **117 passing tests, 0 failures**.

## Current task

**v0.12.2 batch reprint implementation is complete in code and automated tests.** Next priority is real-hardware validation of production quantities across mixed FlashForge/Snapmaker printers, especially concurrent assignment, bed-clearance recycling, printer-local file reuse, and pause/resume behaviour.

## Next steps

1. Queue a known-good single-tool file with quantity 4 or more and confirm multiple compatible printers receive copies concurrently.
2. Confirm each completed printer waits for **Bed cleared** before it receives the next copy from the same production batch.
3. Pause a production batch while copies are active and confirm active prints continue but no new copies start; then resume it.
4. Increase and decrease the requested quantity while copies are waiting and confirm already-started/finished copies are never removed.
5. Cancel remaining copies and confirm currently active prints continue while all waiting/preparing copies are cancelled.
6. Confirm a printer that already has the exact filename reuses its printer-local copy rather than uploading it again.
7. After hardware validation, consider queue priority / scheduling policy as the next scheduler milestone.

## Handoff rule

If chat context and this file disagree about the codebase, inspect current GitHub files and tests. **GitHub is authoritative for code; this document is authoritative for project intent/status until deliberately updated.**
