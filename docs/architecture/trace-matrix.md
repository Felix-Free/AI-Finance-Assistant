# Traceability Matrix (owner: role B)

> Purpose: a **standalone** requirement-to-evidence trace, mapping every real requirement id in
> `docs/req/requirements.yaml` to its architecture component, source function, and test case, with
> an explicit evidence-status field that distinguishes what is on `main` from what only exists on an
> unmerged branch.
>
> Baseline recorded for this matrix (Phase 2 refresh).
>
> **Branch state verified as of 2026-11-16.** The SHA below is the identifier at review time and does
> **not** mean "permanently current"; branches keep moving.
>
> - `main` HEAD `94b0ec4` (includes Phase 1 Role B docs + PR #11 CI skeleton + PR #12). `main`
>   contains `src/call_llm.py`, `src/policy_core.py`, `src/pipeline.py`, the offline tests
>   `test/offline/test_policy_core_smoke.py`, `test/offline/test_pipeline_seam.py`,
>   `test/offline/test_invariants.py` (INV-001 only, 2 tests), `.github/workflows/ci.yml`, and
>   `pytest.ini`.
> - `origin/feat/D-phase2-measurement` HEAD `df729a9` — **UNMERGED** (24 ahead / 0 behind `main`).
>   Adds `src/storage.py`, `src/report_tokens.py`, `scripts/measure_latency.py`, `scripts/measure_tokens.py`,
>   token/usage capture in `src/call_llm.py`, `call_id` threading in `src/pipeline.py`, and tests
>   (`test_token_usage.py`, `test_storage.py`, `test_measurement_scripts.py`,
>   `test_evidence_join.py` — the last is **skipped** on this branch).
> - `origin/feat/e-phase2-verification` HEAD `cab1901` — **UNMERGED** (47 ahead / 0 behind `main`,
>   verified 2026-11-16). Carries the E verification work (un-skips `test_evidence_join.py`, local
>   evidence in `docs/measurements/phase2-qa-evidence.md`, guard-removal negatives; 12 INV-related
>   tests covering INV-001/002/003). Neither branch's results are evidence on `main` or in CI.
> - `origin/feat/c-phase2-policy-60339160` HEAD `01e3bc7` — **UNMERGED** (19 ahead / 17 behind `main`,
>   verified 2026-11-16).
>
> This file does **not** modify or restate requirement text; `requirements.yaml` remains the single
> source of truth for requirement content. It does **not** invent ids: every id below appears in
> `requirements.yaml`. Status values describe **where the evidence lives**, not that a requirement is
> "approved" or "passing".

---

## 1. How to read this matrix

### 1.1 Evidence Status (where the evidence lives)

| Value | Meaning |
|---|---|
| `IN_MAIN` | The named test/CI exists on `main` (`94b0ec4`) and runs from the merged code. (Phase 1 recorded this against `0dda36b`; the label means "on `main`", not a fixed SHA.) |
| `PENDING_MERGE` | The evidence exists only on an unmerged remote branch (e.g. `origin/feat/D-phase2-measurement`, `origin/feat/e-phase2-verification`) and must be treated as **not yet present** on `main`. |
| `MISSING` | No code and/or no test evidence found for the requirement. |

### 1.2 Verification Status (how far the requirement is satisfied)

| Value | Meaning |
|---|---|
| `IMPLEMENTED_AND_TESTED` | Code exists and at least one **automated offline test** exercises it on `main`. |
| `IMPLEMENTED_NOT_TESTED` | Code exists on `main` but no automated test exercises it. |
| `PARTIALLY_IMPLEMENTED` | Some part is in code; a prerequisite (e.g. storage, retry policy, live measurement) is absent. |
| `NOT_IMPLEMENTED` | No code exists. |
| `NOT_VERIFIED` | Not implemented **or** no measurable/approved verification evidence. |

> "Has a mapping" is **not** the same as "verified passing". A row counts as *test-mapped* only when
> a real test function name is cited; it counts as *verified* only when that test is `IN_MAIN` and
> asserted to pass by the offline suite. `PENDING_MERGE` rows have a mapping but are **not** verified
> on `main`.

### 1.3 Eight-column table convention and the four Phase-2 status labels

Every requirement table in §2 uses the same **eight columns**:
`Requirement ID | Description | Architecture Component | Source File/Function | Test File/Test Case |
Verification Evidence | Status | Gap/Remarks`.

Merge rules (so no information is lost from the earlier wider tables):

- **Runtime Monitor** is folded into the **Architecture Component** column. If no real continuous
  monitor/observer exists, it is shown as `—`. Running log files (`logs/llm_calls.jsonl`,
  `logs/review.jsonl`, `data/records.jsonl`) are **outputs**, not monitors, so they are never listed
  as a Runtime Monitor.
- The four Phase-2 **status labels** are folded into the **Status** column, which also carries the
  Evidence Status (`IN_MAIN`/`PENDING_MERGE`/`MISSING`) and Verification Status
  (`IMPLEMENTED_AND_TESTED` etc.).
- Branch SHA, unmerged status, evidence gaps and pending-verification notes go into
  **Gap/Remarks**.

The four Phase-2 labels may co-occur for one row; a row is **not** forced into one label. They are
assigned **only when the evidence supports them**:

| Label | Meaning |
|---|---|
| `main-implemented` | The named code/test exists on `main` (`94b0ec4`) and runs from merged code. |
| `D-branch-implemented-unmerged` | The related implementation exists only on `origin/feat/D-phase2-measurement` and is **not** on `main`. |
| `test-pending` | The relevant automated test is absent, **or** present but **skipped**, **or** the assertion is still E's to complete. A skipped test is never counted as passing. |
| `runtime-evidence-pending` | No committed, reproducible run evidence exists. Runtime artifacts are not repository evidence; D-reported figures are not independent verification. |

---

## 2. Full traceability matrix

### 2.1 Functional requirements (FR-001 … FR-008)

| Requirement ID | Description | Architecture Component | Source File/Function | Test File/Test Case | Verification Evidence | Status | Gap/Remarks |
|---|---|---|---|---|---|---|---|
| FR-001 | NL sentence → model parse via single entry point | Model client (single seam); Runtime Monitor: — | `src/call_llm.py::extract` | `test_pipeline_seam.py::test_seam_returns_parsed_object_and_logs_once`; `test_pipeline_seam.py::test_seam_non_json_is_logged_then_reraised` | IN_MAIN; IMPLEMENTED_AND_TESTED (AC-001, AC-009) | main-implemented | Live-gateway path (`test/live`) not run without an approved key. |
| FR-002 | Structured extraction + field checks (non-dict rejected) | Policy core; Runtime Monitor: — | `src/policy_core.py::validate_record` | `test_policy_core_smoke.py::test_validate_record_rejects_non_dict`; `test_policy_core_smoke.py::test_validate_record_returns_normalised_record` | IN_MAIN; IMPLEMENTED_AND_TESTED (AC-013) | main-implemented | — |
| FR-003 | Amount validity (finite, >0, ≤2 dp) | Policy core; Runtime Monitor: — | `src/policy_core.py::enforce_amount` | `test_policy_core_smoke.py::test_inv001_rejects_invalid_amount` (params: `-1,0,0.005,100.001,"350",None,True,nan,inf`); `test_inv001_accepts_boundary_and_returns_unchanged`; `test_inv001_never_returns_decimal` | IN_MAIN; IMPLEMENTED_AND_TESTED (AC-002/003/004) | main-implemented | E's `test_invariants.py::test_inv001_*` are `PENDING_MERGE`; subset of the smoke coverage, add no new boundary. |
| FR-004 | Category validity (closed whitelist, case-sensitive) | Policy core; Runtime Monitor: — | `src/policy_core.py::enforce_category` | `test_policy_core_smoke.py::test_inv002_rejects_out_of_vocabulary` (params: `Food,餐饮,meal,"",None,1`); `test_inv002_accepts_every_whitelisted_category` (all 8 values) | IN_MAIN; IMPLEMENTED_AND_TESTED (AC-005/006) | main-implemented | Whitelist finality is `INV-PENDING-01` (owner C). |
| FR-005 | Budget rule (cumulative, equality allowed) | Policy core; Runtime Monitor: — | `src/policy_core.py::enforce_budget` | `test_policy_core_smoke.py::test_inv003_equality_is_allowed`; `test_inv003_over_budget_rejected_with_review` | IN_MAIN; IMPLEMENTED_AND_TESTED (AC-007/008) | main-implemented | `budget_limit` origin (storage) absent → PD-003. Off-by-one boundary (`budget+0.01`) not separately parameterised. |
| FR-006 | Abnormal parse / illegal result handling | Model client; Runtime Monitor: — | `src/call_llm.py::_post`; `src/call_llm.py::extract` | `test_pipeline_seam.py::test_post_raises_on_malformed_envelope`; `test_pipeline_seam.py::test_seam_transport_error_logs_once` | IN_MAIN; IMPLEMENTED_AND_TESTED (AC-010) | main-implemented | — |
| FR-007 | Block invalid data before state change | Policy core / pipeline; Runtime Monitor: — | `src/policy_core.py::validate_record`; `src/pipeline.py::process` | `test_policy_core_smoke.py::test_validate_record_stops_at_first_failure` | IN_MAIN; IMPLEMENTED_AND_TESTED (AC-011) | main-implemented | No persistence layer exists, so "no state change" is structural, not observable in a store. |
| FR-008 | Logging & rejection-reason recording | Pipeline; Runtime Monitor: — | `src/call_llm.py::_append_log`; `src/pipeline.py::_append_rejection`; `src/pipeline.py::process` | `test_pipeline_seam.py::test_policy_rejection_writes_one_review_line` (params: `inv001-amount, inv002-category, inv003-budget`); `test_seam_returns_parsed_object_and_logs_once` | IN_MAIN; IMPLEMENTED_AND_TESTED (AC-012) | main-implemented | Fail-closed `OSError` branch is `# pragma: no cover` (environment failure), not exercised by a test. |

### 2.2 Non-functional requirements (NFR-001 … NFR-007)

| Requirement ID | Description | Architecture Component | Source File/Function | Test File/Test Case | Verification Evidence | Status | Gap/Remarks |
|---|---|---|---|---|---|---|---|
| NFR-001 | Model API response time | Model client; Runtime Monitor: — | `src/call_llm.py::extract` (live round-trip); D `scripts/measure_latency.py` | none on `main`; D `test/offline/test_measurement_scripts.py` (unmerged) | MISSING; NOT_VERIFIED — no committed latency evidence | D-branch-implemented-unmerged; test-pending; runtime-evidence-pending | No approved latency budget; `logs/` is a runtime artifact, not repo evidence. D-reported p50/p95 are self-reported, **not** independent verification. pytest duration is **not** a proxy. PD-007 (owner B). |
| NFR-002 | Token consumption | Model client; Runtime Monitor: — | `src/call_llm.py` (gateway usage capture); D `src/report_tokens.py` | none on `main`; D `test/offline/test_token_usage.py` (unmerged) | MISSING; NOT_VERIFIED — no committed token-run evidence | D-branch-implemented-unmerged; test-pending; runtime-evidence-pending | per-request/per-session/api_call_count/usage_source(three-state)/missing-usage implemented on D's **unmerged** branch; `user_request_count` NOT implemented. Statistics only, no approved threshold. PD-007 (owner B). |
| NFR-003 | API call failure handling | Model client / policy; Runtime Monitor: — | `src/call_llm.py::_post`; `src/call_llm.py::extract` | `test_pipeline_seam.py::test_seam_transport_error_logs_once`; `test_config_error_logs_once`; `test_post_raises_on_malformed_envelope` | IN_MAIN; PARTIALLY_IMPLEMENTED — behaviour tested | main-implemented | Behaviour (RP-002) is tested; a pass/fail **threshold** (retry policy) and retry are pending C (PD-008). |
| NFR-004 | Data security (secrets), threshold = 0 | Call client / repo; Runtime Monitor: — | `.env` gitignored; `.env.example` placeholders (`src/call_llm.py` reads env only) | none (no automated secret scan on `main`) | MISSING; PARTIALLY_IMPLEMENTED — manual grep only | main-implemented; test-pending | Threshold 0 is `approved`, but there is **no automated secret-scan test**. |
| NFR-005 | Input/output reliability | Policy core / pipeline; Runtime Monitor: — | `src/policy_core.py::validate_record` (validation precedes return) | `test_policy_core_smoke.py::test_validate_record_stops_at_first_failure`; `test_validate_record_rejects_non_dict`; `test_pipeline_seam.py::test_policy_rejection_writes_one_review_line` | IN_MAIN; PARTIALLY_IMPLEMENTED — behaviour tested | main-implemented | No defined reliability tolerance / rate measurement. PD-007 (owner B). |
| NFR-006 | Log traceability | Model client / pipeline; Runtime Monitor: — | **`main`: `src/call_llm.py::_append_log`; `src/pipeline.py::_append_rejection`.** `_append_rejection` is the renamed rejection writer on `main` (was `_append_review`); it carries `call_id` and joins to `src/storage.py` | `main`: `test_pipeline_seam.py::test_seam_returns_parsed_object_and_logs_once`; `test_seam_non_json_is_logged_then_reraised`; `test_policy_rejection_writes_one_review_line`. D `test/offline/test_evidence_join.py` (**5 skipped**, unmerged) | IN_MAIN (one-line behaviour); PARTIALLY_IMPLEMENTED — call_id join **not on main** | main-implemented; D-branch-implemented-unmerged; test-pending | "Exactly one line" behaviour tested on `main`. The call_id accepted/rejected join (`_append_rejection`, `storage.py`) is now on `main` (merged via PR #18); `main`'s `test_offline/test_evidence_join.py` is still **5 skipped**, so the join is **not** a passing test on `main`. A skipped test is not a passing test. No numeric coverage threshold. PD-008 (owner C). |
| NFR-007 | Testability | test suite / CI; Runtime Monitor: — | `main`: `test/offline/test_policy_core_smoke.py`; `test/offline/test_invariants.py` (2 INV-001 tests) | `main`: smoke INV-001/002/003 guard-removal tests in `test_policy_core_smoke.py`; `main` `test_invariants.py` = 2 INV-001 tests. E branch (unmerged `cab1901`) `test_invariants.py` = 12 INV tests | IN_MAIN; IMPLEMENTED_AND_TESTED — original AC met on `main` | main-implemented; test-pending | Original AC (`verification`: "map each INV to ≥1 test that fails without the guard; run pytest test/offline") is **met on `main`**: INV-001/002/003 each have a `pytest.raises(PolicyError)` smoke test that fails if the guard is removed. `main`'s `test_invariants.py` has **only 2 INV-001 tests**. E's **unmerged** `feat/e-phase2-verification` (`cab1901`) adds **12 INV tests covering INV-001/002/003** (guard-removal) — those are E's **local** results, **not** `main`/CI results. `test file exists` ≠ `test passed` ≠ `CI verified`. |

### 2.3 Business invariants (INV-001 … INV-003; INV-PENDING-01 is a placeholder, not a formal requirement)

| Requirement ID | Description | Architecture Component | Source File/Function | Test File/Test Case | Verification Evidence | Status | Gap/Remarks |
|---|---|---|---|---|---|---|---|
| INV-001 | Amount finite, >0, ≤2 dp | Policy core guard; Runtime Monitor: — | `src/policy_core.py::enforce_amount` | `test_policy_core_smoke.py::test_inv001_rejects_invalid_amount` (9 params); `test_inv001_accepts_boundary_and_returns_unchanged`; `test_inv001_never_returns_decimal` | IN_MAIN; IMPLEMENTED_AND_TESTED (AC-002/003/004) | main-implemented | Negative test fails if the guard is removed. E's INV-001 tests are `PENDING_MERGE`. |
| INV-002 | Category in closed whitelist (case-sensitive) | Policy core guard; Runtime Monitor: — | `src/policy_core.py::enforce_category`; `src/policy_core.py::CATEGORY_WHITELIST` | `test_policy_core_smoke.py::test_inv002_rejects_out_of_vocabulary`; `test_inv002_accepts_every_whitelisted_category` | IN_MAIN; IMPLEMENTED_AND_TESTED (AC-005/006) | main-implemented | E branch adds **no** INV-002 test. Whitelist membership finality: `INV-PENDING-01`. |
| INV-003 | Cumulative spend ≤ budget (equality allowed) | Policy core guard; Runtime Monitor: — | `src/policy_core.py::enforce_budget` | `test_policy_core_smoke.py::test_inv003_equality_is_allowed`; `test_inv003_over_budget_rejected_with_review` | IN_MAIN; IMPLEMENTED_AND_TESTED (AC-007/008) | main-implemented | E branch adds **no** INV-003 test. No separate `budget±0.01` parametrised cases (equality + over-budget covered). |
| INV-PENDING-01 | **[Placeholder — not a formal requirement; excluded from the total of 36]** Exact category whitelist membership final | Policy core constant; Runtime Monitor: — | `src/policy_core.py::CATEGORY_WHITELIST` | `test_inv002_accepts_every_whitelisted_category` (reads current 8 values) | IN_MAIN; NOT_VERIFIED — finality unconfirmed | pending_confirmation | Membership is exercised, but whether the 8 values are **final** is unconfirmed (owner C, PD-002). Counted separately from the 36 formal requirements. |

### 2.4 AI requirements (AI-REQ-001 … AI-REQ-008)

| Requirement ID | Description | Architecture Component | Source File/Function | Test File/Test Case | Verification Evidence | Status | Gap/Remarks |
|---|---|---|---|---|---|---|---|
| AI-REQ-001 | AI does NLU/parsing only | Model client; Runtime Monitor: — | `src/call_llm.py::extract` | `test_pipeline_seam.py::test_seam_returns_parsed_object_and_logs_once` | IN_MAIN; IMPLEMENTED_AND_TESTED | main-implemented | Design-level; exercised indirectly. |
| AI-REQ-002 | Model proposes, code disposes | Pipeline; Runtime Monitor: — | `src/pipeline.py::process` | `test_pipeline_seam.py::test_policy_rejection_writes_one_review_line` | IN_MAIN; IMPLEMENTED_AND_TESTED | main-implemented | Behavioural (rejection path) proves code decides. |
| AI-REQ-003 | AI output passes schema validation before use | Policy core; Runtime Monitor: — | `src/policy_core.py::validate_record` | `test_policy_core_smoke.py::test_validate_record_rejects_non_dict` | IN_MAIN; IMPLEMENTED_AND_TESTED | main-implemented | — |
| AI-REQ-004 | After schema, deterministic rule validation | Policy core; Runtime Monitor: — | `src/policy_core.py::validate_record` (order INV-001→002→003) | `test_policy_core_smoke.py::test_validate_record_stops_at_first_failure` | IN_MAIN; IMPLEMENTED_AND_TESTED | main-implemented | — |
| AI-REQ-005 | Prompt injection can't alter safety rules | Policy core (rules in code); Runtime Monitor: — | `src/policy_core.py` (guards are code, not prompt) | `test_policy_core_smoke.py::test_policy_core_has_no_io_imports`; structural review | IN_MAIN; IMPLEMENTED_NOT_TESTED | main-implemented | No dedicated injection test; guarantee is structural (rules live in code). |
| AI-REQ-006 | Failed AI parse must not fabricate a record | Pipeline; Runtime Monitor: — | `src/call_llm.py::extract` re-raises; `src/pipeline.py::process` | `test_pipeline_seam.py::test_seam_non_json_is_logged_then_reraised` | IN_MAIN; IMPLEMENTED_AND_TESTED | main-implemented | — |
| AI-REQ-007 | Apply RP-001/RP-002 on unexpected shape | Model client; Runtime Monitor: — | `src/call_llm.py::_post`; `src/call_llm.py::extract` | `test_pipeline_seam.py::test_post_raises_on_malformed_envelope`; `test_seam_non_json_is_logged_then_reraised` | IN_MAIN; IMPLEMENTED_AND_TESTED | main-implemented | — |
| AI-REQ-008 | AI must not modify requirements/scope | Governance; Runtime Monitor: — | `AGENTS.md`; `.opencode/permissions.jsonc` | process review (no code test) | IN_MAIN; IMPLEMENTED_NOT_TESTED | main-implemented | Process/governance control; not automatable as a unit test. |

### 2.5 Error-handling requirements (ERR-001 … ERR-005)

| Requirement ID | Description | Architecture Component | Source File/Function | Test File/Test Case | Verification Evidence | Status | Gap/Remarks |
|---|---|---|---|---|---|---|---|
| ERR-001 | Non-JSON → log not_json + reraise (RP-001) | Model client; Runtime Monitor: — | `src/call_llm.py::extract` | `test_pipeline_seam.py::test_seam_non_json_is_logged_then_reraised` | IN_MAIN; IMPLEMENTED_AND_TESTED (AC-009) | main-implemented | Asserts `error=="not_json"` and one log line. |
| ERR-002 | Transport/HTTP failure → LlmTransportError (RP-002) | Model client; Runtime Monitor: — | `src/call_llm.py::_post`; `src/call_llm.py::extract` | `test_pipeline_seam.py::test_seam_transport_error_logs_once`; `test_config_error_logs_once` | IN_MAIN; IMPLEMENTED_AND_TESTED (AC-010) | main-implemented | — |
| ERR-003 | Invariant violation → PolicyError, no state change (RP-003/005/006) | Policy core / pipeline; Runtime Monitor: — | `src/policy_core.py::validate_record`; `src/pipeline.py::process` | `test_policy_core_smoke.py::test_validate_record_stops_at_first_failure`; `test_pipeline_seam.py::test_policy_rejection_writes_one_review_line` | IN_MAIN; IMPLEMENTED_AND_TESTED (AC-011/012) | main-implemented | — |
| ERR-004 | Logging integrity fail-closed (RP-004) | Model client; Runtime Monitor: — | `src/call_llm.py::_append_log` | none (the `OSError`→`LlmTransportError` path is `# pragma: no cover`) | MISSING; IMPLEMENTED_NOT_TESTED | main-implemented; test-pending | Fail-closed code exists but the unwritable-log branch is not exercised by a test. |
| ERR-005 | Rejection evidence: one review line per rejection | Pipeline; Runtime Monitor: — | `src/pipeline.py::_append_rejection` | `test_pipeline_seam.py::test_policy_rejection_writes_one_review_line` (3 params) | IN_MAIN; IMPLEMENTED_AND_TESTED (AC-012) | main-implemented | Asserts exact field set `{error,amount,category,spent,total,review}`. |

### 2.6 Security requirements (SEC-001 … SEC-005)

| Requirement ID | Description | Architecture Component | Source File/Function | Test File/Test Case | Verification Evidence | Status | Gap/Remarks |
|---|---|---|---|---|---|---|---|
| SEC-001 | No secret in any committed file | Repo hygiene; Runtime Monitor: — | `.gitignore`; `.env.example` placeholders; `src/call_llm.py` reads env | none (no automated secret scan) | MISSING; PARTIALLY_IMPLEMENTED | main-implemented; test-pending | Enforced by process/gitignore; no automated scan on `main`. |
| SEC-002 | All model calls via `src/call_llm.py`; no other module imports `requests` for calls | Model client boundary; Runtime Monitor: — | `src/call_llm.py` (only `requests` importer); `src/pipeline.py` imports no `requests` | `test_policy_core_smoke.py::test_policy_core_has_no_io_imports` (policy_core has no `requests`) | IN_MAIN; IMPLEMENTED_NOT_TESTED | main-implemented | No test asserts pipeline/extract are the *only* `requests` user; only policy_core is checked. |
| SEC-003 | `policy_core` never bypassed; every output checked before affecting data | Pipeline / policy core; Runtime Monitor: — | `src/pipeline.py::process` (always calls `validate_record`) | `test_pipeline_seam.py::test_policy_rejection_writes_one_review_line` | IN_MAIN; IMPLEMENTED_AND_TESTED (AC-011) | main-implemented | Rejection path proves no bypass; no persistence to observe "before affecting data". |
| SEC-004 | `.env` not readable/writable by agent; secrets never logged | Governance / client; Runtime Monitor: — | `.opencode/permissions.jsonc`; `src/call_llm.py` (logs input/raw/parsed/error only) | none (no automated test) | MISSING; PARTIALLY_IMPLEMENTED | main-implemented; test-pending | Enforced by permission model; no automated test that secrets never appear in logs. |
| SEC-005 | Logging fail-closed; unlogged result not used | Model client; Runtime Monitor: — | `src/call_llm.py::_append_log` | none (see ERR-004) | MISSING; IMPLEMENTED_NOT_TESTED | main-implemented; test-pending | Same gap as ERR-004. |

> Note: there is no `SEC` acceptance-criterion id in `requirements.yaml`; where an AC exists it is
> cited inline in the Verification Evidence/Remarks. SEC rows are traced to code/governance and are
> marked tested **only** when a real offline test exercises them.

---

## 3. Branch-evidence separation (Phase 1 as of `0dda36b` → Phase 2 as of `94b0ec4`)

> **Historical vs current.** The "Phase 1 (`0dda36b`)" column records what was true at the Phase 1
> baseline; the "Now on `main` (`94b0ec4`)" column records the verified current state (as of
> 2026-11-16). Items that were `PENDING_MERGE` in Phase 1 were later merged via **PR #11**
> (`feat/e-ci-skeleton`) plus the Phase 1 Role B docs.

| Artifact | Phase 1 (`0dda36b`) | Now on `main` (`94b0ec4`) | What it is |
|---|---|---|---|
| `src/call_llm.py`, `src/policy_core.py`, `src/pipeline.py` | Yes | Yes | Implementation. |
| `test/offline/test_policy_core_smoke.py` | Yes | Yes | Smoke tests for INV-001/002/003 + validate_record. |
| `test/offline/test_pipeline_seam.py` | Yes | Yes | Seam + rejection-logging tests. |
| `.github/workflows/ci.yml` | No (PENDING_MERGE) | **Yes** (merged via PR #11) | CI workflow. |
| `pytest.ini` | No (PENDING_MERGE) | **Yes** (merged via PR #11) | Offline/live markers. |
| `requirements.txt` (`jsonschema`, `ruff`) additions | No (PENDING_MERGE) | **Yes** (merged via PR #11) | New dev deps. |
| `test/offline/test_invariants.py` | No (PENDING_MERGE) | **Yes** — but **only 2 INV-001 tests** on `main` | E's invariant test file (see note). |

**Note (INV coverage).** `main`'s `test/offline/test_invariants.py` contains **2 INV-001 tests only**.
The **unmerged** E branch `feat/e-phase2-verification` (`cab1901`, verified 2026-11-16) adds a fuller
`test_invariants.py` with **12 INV-related tests covering INV-001/002/003** (guard-removal negatives).
E's branch results are **E's local results on an unmerged branch — not `main` or CI results**; they
must not be reported as passing on `main`/CI until merged and run in the hosted pipeline.

---

## 4. Coverage summary (computed from this matrix)

**Formal requirement total: 36.** Counted rows: FR (8) + NFR (7) + formal INV (3) + AI-REQ (8) +
ERR (5) + SEC (5) = **36 formal requirements**.

**Counting rules (explicit):**
- `INV-PENDING-01` is a **placeholder for an unconfirmed decision**, kept in §2.3 for traceability but
  **not counted** in the total of 36.
- `PD-001 … PD-008` are **pending decisions**, not requirement rows; they are **not** counted.
- Nothing was deleted to reach 36 — the placeholder row remains, only excluded from the count.

### 4.1 Mapping coverage

| Metric | Count | Definition used |
|---|---|---|
| Total formal requirements traced | 36 | FR 8 + NFR 7 + INV 3 + AI-REQ 8 + ERR 5 + SEC 5. `INV-PENDING-01` excluded (placeholder). |
| With architecture-component mapping | 36 | Every row names a component (Runtime Monitor folded in; `—` where none). |
| With source-file/function mapping | 33 | 3 rows have no concrete function: NFR-001, NFR-002 (**no committed measurement evidence**; measurement code exists only on the unmerged `feat/D-phase2-measurement`) and AI-REQ-008 (governance only). |
| With a cited test-case mapping (incl. unmerged) | 28 | A concrete test function name is cited in the "Test File/Test Case" column (including unmerged-branch tests cited in Remarks). |
| Without a cited test-case mapping | 8 | NFR-001, NFR-002, NFR-004, AI-REQ-008, ERR-004, SEC-001, SEC-004, SEC-005. 28 + 8 = 36. |

### 4.2 Evidence-status distribution (over the 36 formal requirements; each row carries one Evidence Status)

| Evidence Status | Count | Rows |
|---|---|---|
| IN_MAIN | 29 | every FR/AI-REQ/ERR/SEC/invariant row traced to `main` code/tests, plus NFR-003/005/006/007 (their `main` smoke evidence is the primary status; unmerged-branch tests are noted only in Remarks). |
| PENDING_MERGE | 0 | No row uses `PENDING_MERGE` as its **primary** status. E's `test_invariants.py` tests appear `PENDING_MERGE` in the Remarks of FR-003 / INV-001 / NFR-007 and in §3, never as a row status. |
| MISSING | 7 | NFR-001, NFR-002 (no committed measurement evidence; code only on the unmerged D branch); NFR-004, SEC-001, SEC-004 (no automated secret scan); ERR-004, SEC-005 (no fail-closed OSError test). |
| **Total** | **36** | Equals the formal-requirement row count. |

> Each formal row carries a **single** Evidence Status, so the per-row counts equal 36. Unmerged
> evidence is surfaced as `PENDING_MERGE` only in its own Remarks cell and is **not** promoted to
> `IN_MAIN`.
>
> **Phase-2 labels do not affect this count.** The multi-valued Phase-2 labels
> (`main-implemented` / `D-branch-implemented-unmerged` / `test-pending` / `runtime-evidence-pending`)
> are folded into the Status column and may coexist for one row; they are orthogonal to the
> single-valued Evidence Status and do **not** change the 36-row tally or the distribution above.

### 4.3 Verification-status distribution (over the 36 formal requirements)

| Verification Status | Count | Rows (examples) |
|---|---|---|
| IMPLEMENTED_AND_TESTED | 22 | FR-001..008; INV-001/002/003; AI-REQ-001/002/003/004/006/007; ERR-001/002/003/005; SEC-003; NFR-007 (original testability AC met on `main`). |
| IMPLEMENTED_NOT_TESTED | 5 | AI-REQ-005, AI-REQ-008, SEC-002, ERR-004, SEC-005. |
| PARTIALLY_IMPLEMENTED | 6 | NFR-003, NFR-004, NFR-005, NFR-006, SEC-001, SEC-004. |
| NOT_IMPLEMENTED | 0 | — |
| NOT_VERIFIED | 3 | NFR-001, NFR-002, `INV-PENDING-01 (placeholder, excluded from the formal requirement count)`. |

> Counts use the 36 formal requirements. `INV-PENDING-01` is NOT_VERIFIED but is excluded from these
> per-group totals (placeholder). A requirement is `IMPLEMENTED_AND_TESTED` only when its cited test is
> on `main`; unmerged tests never raise a row's status.

---

## 5. Known gaps carried forward

> Status column distinguishes **Resolved** (fixed on `main`) from **Open** (still a gap). Phase-1
> history is preserved in the Note; current state is as of 2026-11-16.

| Gap | Evidence source | Requirement(s) | Owner | Status | Note |
|---|---|---|---|---|---|
| CI configuration missing | Phase 1: `feat/e-ci-skeleton` `7d29552`; now `.github/workflows/ci.yml` on `main` | NFR-007 | E | **Resolved** | CI + `pytest.ini` + `requirements.txt`(jsonschema,ruff) are now on `main@94b0ec4` (merged via PR #11). Historical Phase-1 note: not on `main` then. |
| No committed latency/token measurement evidence | thresholds null; `logs/`/`data/` are runtime artifacts | NFR-001, NFR-002 | B (records) / E (runs) | **Open** | D's branch (`df729a9`, **unmerged**) has `measure_latency.py` / `measure_tokens.py` / `report_tokens.py`, but there is **no committed runtime evidence** and D-reported figures are not independent verification. PD-007. Do not substitute pytest timing. |
| Fail-closed log branch untested | `src/call_llm.py` `# pragma: no cover` | ERR-004, SEC-005 | D/E | **Open** | Environment-failure branch. |
| No automated secret scan | `.gitignore` only | NFR-004, SEC-001, SEC-004 | B/C | **Open** | Manual verification only. |
| Only `policy_core` import-checked | `test_policy_core_has_no_io_imports` | SEC-002 | E | **Open** | No test asserts pipeline/extract import `requests` alone. |
| INV-002/003 boundary suite absent on `main` | `main` `test_invariants.py` has only INV-001 (2 tests); E branch `cab1901` has 12 INV tests | INV-002/003, NFR-007 | E | **Open on `main`; covered on E's unmerged branch** | E's `feat/e-phase2-verification` (`cab1901`) covers INV-001/002/003 with guard-removal negatives, but it is **unmerged** and its results are E's **local** results — not `main` or CI. |
| Runtime Monitor | `trace-matrix.md` §1.3 fold rule (Runtime Monitor folded into Architecture Component) | all | B | **Open / unconfirmed** | No confirmed continuous monitor exists; log files are outputs, not monitors, so every row's Runtime Monitor field remains `—`. |
