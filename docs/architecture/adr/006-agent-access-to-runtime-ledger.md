# ADR-006 — Deny Agent Access to the Runtime Ledger

- **Status:** Accepted by role C.
- **Owner:** Role C.
- **Date:** 2026-11-22.
- **Related:** `docs/architecture/permission-model.md`;
  `.opencode/permissions.jsonc`; `docs/architecture/adr/003-atomic-append-and-locking.md`.

## Context

The agent needs read and edit access to selected `data/**` paths for measurement
inputs and outputs. The runtime ledger also lives under `data/`, and contains
validated financial records. Its lock sidecar and atomic-append temporary files
share the `data/records.jsonl` filename prefix. A broad `data/**` allow would
therefore expose runtime business data unless there is a narrower exception.

## Decision

Keep the `data/**` read and edit allows needed for measurement work, and add a
`data/records.jsonl*` deny for both actions. The specific deny covers the ledger,
`records.jsonl.lock`, and same-prefix temporary files. This follows the permission
model's deny-overrides-allow rule. The existing default-deny policy remains in force.

## Alternatives considered

- **Remove all `data/**` access:** rejected because it blocks the approved measurement
  workflow.
- **Rely on `.gitignore` or user convention:** rejected because neither prevents the
  agent from reading or editing the runtime ledger.
- **Keep only the broad allow:** rejected because it grants the agent access to
  financial business data and its write artifacts.

## Consequences

- Measurement data outside the `records.jsonl` prefix remains accessible under the
  existing rules.
- The runtime ledger and its same-prefix lock and temporary files remain denied for
  agent reads and edits.
- This ADR records the intended permission configuration. It does not claim that the
  OpenCode runtime matcher has been independently exercised.
