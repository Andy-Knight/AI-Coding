# Printer Fleet Controller — Project Context

> Cross-chat handoff file. Read this first when continuing the project in a new chat. Keep it concise and update it whenever architecture/decisions change, a task is completed, or the current/next task changes.

## Source of truth

- Repository: `Andy-Knight/AI-Coding`
- Project path: `print-farm-controller/`
- Branch: `main`
- Current application version: **0.11.0**
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
- Preserve the legacy application-data directory for upgrade compatibility.
- Queue/history and controller-staged queue files persist across restarts.
- A completed/active-failed/cancelled print creates a **bed-clearance interlock**; no later queued job may start on that printer until **Bed cleared** is confirmed.
- Queue jobs support two assignment modes: **fixed printer** and **Next available compatible printer**.
- Automatic scheduling is file-centric: the controller owns a durable staged copy, evaluates compatibility/readiness, reserves one printer, uploads/verifies if required, performs a fresh live preflight, then starts.
- Compatibility and readiness are distinct. A printer may be compatible but temporarily blocked by offline/busy/bed-clearance/reservation state.
- Automatic compatibility returns explicit per-printer reasons and distinguishes **Eligible**, **Waiting**, **Needs review**, and **Not compatible**.
- Required nozzle size must not be guessed. If a printer cannot report an explicitly required nozzle, unattended scheduling requires review rather than assuming a match.
- U1 logical-to-physical tool mapping is derived from live material/colour/nozzle state and uses constrained matching to avoid greedy mapping errors.
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

## Current task

**v0.11.0 implementation is complete in code and automated tests.** Next priority is real-hardware validation of the new **Next available compatible printer** workflow on the user's configured FlashForge and Snapmaker fleet.

Validation should confirm staging from the browser, live compatibility reasons, bed-clearance blocking, U1 tool mapping, upload/verification, final preflight, print start, cancellation during preparation, restart behaviour, and fixed-printer queue regression behaviour.

## Next steps

1. Deploy/run v0.11.0 and queue a simple known-good single-tool G-code using **+ Queue file**.
2. Verify the UI lists eligible and blocked printers with accurate reasons before assignment.
3. Test bed-clearance blocking by leaving one otherwise-compatible printer uncleared and confirming another eligible printer is chosen.
4. Validate U1 material/colour/nozzle mapping with a known multi-tool file before relying on unattended multi-tool scheduling.
5. Confirm FlashForge files with explicit nozzle requirements enter **Needs review** when nozzle size cannot be verified rather than being started automatically.
6. Test controller restart with an unassigned automatic job and confirm it remains safely queued with the staged file intact.
7. After hardware validation, address any observed edge cases before extending scheduling policy/fairness or adding more printer manufacturers.

## Handoff rule

If chat context and this file disagree about the codebase, inspect current GitHub files and tests. **GitHub is authoritative for code; this document is authoritative for project intent/status until deliberately updated.**
