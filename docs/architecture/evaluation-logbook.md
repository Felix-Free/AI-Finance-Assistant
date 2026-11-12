# Evaluation Logbook (owner: roles C and E)

> Purpose: the running record of **non-functional requirements (NFRs)** for the finance
> assistant — what is measured, against which threshold, from which input, by which
> procedure, with which evidence, and what was actually observed. This logbook is where an
> NFR moves from "pending" to a measured result; a threshold without an observed result is
> marked **pending**, never assumed to pass.
>
> Status: **Phase 2 · C-side documentation (transcript 60339160).** C defines the metric,
> threshold and evidence contract; E runs the measurement; D implements the pipeline. No
> measurement result is recorded here until it has actually been run.

---

## 1. How to read this logbook

- **Result states.** `pending` — not yet measured. `measured` — the procedure in §2 was
  actually run and the observed value is recorded below. `blocked` — the procedure cannot
  run yet because the pipeline/evidence it needs does not exist. A `pending` or `blocked`
  NFR is **not** a pass.
- **No invented results.** The observed result is copied from a run whose output is
  attached (evidence file or command output). If it was not run, it says so.
- **Ids.** The repository convention is `REQ-NFR-###`
  (`docs/code-governance/structural-constraints.md §3`); this logbook keeps the short form
  `NFR-###` used in the requirements conversation and maps it 1:1.

---

## 2. Logbook entries

### NFR-001 — Input parsing reliability

| Field | Value |
|---|---|
| NFR | Input parsing reliability: a well-formed spending sentence yields the correct structured record. |
| Metric | Share of fixture inputs whose parsed `(amount, category)` equals the expected record. |
| Threshold | Defined by the requirements source; recorded here once confirmed. Until then the threshold is **not** asserted. |
| Input / data source | Fixed offline fixture set under `data/` (deterministic inputs with expected outputs); no network. |
| Measurement command / procedure | Run the offline extraction over the fixtures and tally matches against expected records. Exact command is fixed when the harness lands; until then: procedure only. |
| Expected evidence files | `docs/measurements/` report for NFR-001; the fixture file under `data/`. |
| Owner | E (measurement), D (pipeline). |
| Status | pending |
| Observed result | Not measured. |

### NFR-002 — Deterministic safety boundary

| Field | Value |
|---|---|
| NFR | Deterministic safety boundary: no model output that violates `C-INV-001..003` ever affects stored data. |
| Metric | Number of invariant-violating inputs that slip past `policy_core` into storage (must be zero). |
| Threshold | Zero violations. Every violating fixture is rejected with the documented `policy:*` code. |
| Input / data source | Adversarial fixtures under `data/` covering the boundary values in `invariants.md §2` (amount, category, budget). |
| Measurement command / procedure | Feed each violating fixture through the pipeline; assert rejection and absence of a storage record. This is the negative-test property from `invariants.md §3` applied across the fixture set. |
| Expected evidence files | `docs/measurements/` report for NFR-002; `logs/review.jsonl` rejection lines for the rejected cases. |
| Owner | E (measurement), D (guards). |
| Status | pending |
| Observed result | Not measured. |

### NFR-006 — Evidence join by `call_id`

| Field | Value |
|---|---|
| NFR | Evidence records belonging to one decision carry the same `call_id` (`runtime-policy-catalog.md §5.4`). |
| Metric | Share of decisions whose three relevant `call_id` locations/evidence records carry the same `call_id`. |
| Threshold | Three relevant `call_id` locations/evidence records for the same decision must carry the same `call_id`. Strict; not weakened to a two-record join, no "where applicable", not redefined from whatever records happen to exist. |
| Threshold mapping | **Pending clarification.** The exact names of the three required `call_id` locations are not available in this repository yet; the measurement mapping is pending and is not replaced with a weaker rule. |
| Conditional evidence shape | Separate rule, not the threshold. Accepted decision → `llm_calls` + normal storage evidence. Rejected decision → `llm_calls` + review evidence. A rejected decision must not create a normal storage record. |
| Input / data source | The logs produced by a measurement run: `logs/llm_calls.jsonl` plus `logs/review.jsonl`, and the stored records for accepted decisions. |
| Measurement command / procedure | For each decision, check that the three relevant `call_id` locations/evidence records carry the same `call_id` (threshold), and assert the conditional shape — accepted → llm_calls + storage, rejected → llm_calls + review. Any decision with a storage record *and* a review line, or with mismatched ids, is a failure. |
| Expected evidence files | `docs/measurements/` report for NFR-006; the joined `logs/llm_calls.jsonl` and `logs/review.jsonl` excerpts used for the check. |
| Owner | E (measurement), D (pipeline: `call_id` generation and carriage), C (contract). |
| Status | blocked |
| Observed result | Not measured — blocked on the `call_id` pipeline (C2/C3). |

> **Why NFR-006 is blocked, not pending.** The join depends on the C2/C3/C4 pipeline
> actually emitting `call_id` into both log files and removing `__call_id__` before
> `policy_core`. Until that pipeline exists and produces real log lines, the procedure has
> nothing to measure; recording "pending" with a numeric result would be misleading.

---

## 3. Summary table

| NFR | Metric | Threshold | Owner | Status | Observed result |
|---|---|---|---|---|---|
| NFR-001 | fixture parse-match rate | as per requirements (not asserted yet) | E / D | pending | not measured |
| NFR-002 | invariant violations reaching storage | zero | E / D | pending | not measured |
| NFR-006 | decisions whose three relevant call_id locations share one call_id | three relevant call_id locations/evidence records share the same call_id | E / D / C | blocked | not measured |

---

## 4. Change protocol

- Adding an NFR means adding a full entry in §2 and a row in §3.
- Recording a result means filling `Status` → `measured` and `Observed result` with the
  actual value **and** the evidence file that holds the run. A result without an evidence
  file is not recorded.
- Thresholds are owned by role B's requirements; C records them here from the requirements
  source and does not invent them. If the requirements source does not state a threshold,
  the cell says so rather than guessing.
