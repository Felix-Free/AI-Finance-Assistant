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
>   Adds `src/storage.py`, `src/report_tokens.py`, `src/measure_latency.py`, `src/measure_tokens.py`,
>   token/usage capture in `src/call_llm.py`, `call_id` threading in `src/pipeline.py`, and tests
>   (`test_token_usage.py`, `test_storage.py`, `test_measurement_scripts.py`,
>   `test_evidence_join.py` — the last is **skipped** on this branch).
> - `origin/feat/e-phase2-verification` HEAD `cc6e650` — **UNMERGED** (41 ahead / 0 behind `main`).
>   Carries the E verification work (un-skips `test_evidence_join.py`, local evidence in
>   `docs/measurements/phase2-qa-evidence.md`, guard-removal negatives; 12 INV-related tests covering
>   INV-001/002/003). Neither branch's results are evidence on `main` or in CI.
> - `origin/feat/c-phase2-policy-60339160` HEAD `6808d7e` — **UNMERGED** (17 ahead / 18 behind `main`).
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

### 1.3 Runtime Monitor and the four Phase-2 status labels

"Enforcing Component", "Test Evidence" and "Runtime Monitor" are three **independent** facts about a
requirement and are recorded separately. A requirement may carry **more than one** of the following
labels at once; a single NFR is **not** forced into one and only one label.

| Label | Meaning |
|---|---|
| `main-implemented` | The named code/test exists on `main` (`94b0ec4`) and runs from merged code. |
| `D-branch-implemented-unmerged` | The implementation exists only on `origin/feat/D-phase2-measurement` and is **not** on `main`. Treat as not yet present in the product. |
| `test-pending` | The relevant automated test is absent, **or** present but **skipped** (e.g. D's `test_evidence_join.py`), **or** the assertion is still E's to complete. A skipped test is never counted as passing. |
| `runtime-evidence-pending` | No committed, reproducible run evidence exists. Runtime artifacts (`logs/*.jsonl`, `data/records.jsonl`) are produced at run time and are **not** repository evidence; D-reported figures are not independent verification. |

**Runtime Monitor** column: names an actual continuous monitor/observer if one exists; otherwise `—`.
Running log files (`logs/llm_calls.jsonl`, `logs/review.jsonl`, `data/records.jsonl`) are **outputs**,
not monitoring mechanisms, so they are **not** listed as a Runtime Monitor — they appear, if at all,
only as uncommitted runtime artifacts under `runtime-evidence-pending`.

---

## 2. Full traceability matrix

### 2.1 Functional requirements (FR-001 … FR-008)

| Requirement ID | Requirement Summary | Acceptance Criteria | Architecture Component | Source File / Function | Test File / Test Case | Evidence Status | Verification Status | Gap / Remarks |
|---|---|---|---|---|---|---|---|---|
| FR-001 | NL sentence → model parse via single entry point | AC-001 (valid→JSON+1 log line), AC-009 (non-JSON→log+reraise) | Model client (single seam) | `src/call_llm.py::extract` | `test_pipeline_seam.py::test_seam_returns_parsed_object_and_logs_once`; `test_pipeline_seam.py::test_seam_non_json_is_logged_then_reraised` | IN_MAIN | IMPLEMENTED_AND_TESTED | Live-gateway path (`test/live`) not run without an approved key. |
| FR-002 | Structured extraction + field checks (non-dict rejected) | AC-013 (JSON array→policy:amount) | Policy core | `src/policy_core.py::validate_record` | `test_policy_core_smoke.py::test_validate_record_rejects_non_dict`; `test_policy_core_smoke.py::test_validate_record_returns_normalised_record` | IN_MAIN | IMPLEMENTED_AND_TESTED | — |
| FR-003 | Amount validity (finite, >0, ≤2 dp) | AC-002/003/004 | Policy core | `src/policy_core.py::enforce_amount` | `test_policy_core_smoke.py::test_inv001_rejects_invalid_amount` (params: `-1,0,0.005,100.001,"350",None,True,nan,inf`); `test_inv001_accepts_boundary_and_returns_unchanged`; `test_inv001_never_returns_decimal` | IN_MAIN | IMPLEMENTED_AND_TESTED | E's `test_invariants.py::test_inv001_rejects_negative_amount` / `test_inv001_accepts_valid_amount` are `PENDING_MERGE`; they are a subset of the smoke coverage and add no new boundary. |
| FR-004 | Category validity (closed whitelist, case-sensitive) | AC-005/006 | Policy core | `src/policy_core.py::enforce_category` | `test_policy_core_smoke.py::test_inv002_rejects_out_of_vocabulary` (params: `Food,餐饮,meal,"",None,1`); `test_inv002_accepts_every_whitelisted_category` (all 8 values) | IN_MAIN | IMPLEMENTED_AND_TESTED | Whitelist finality is `INV-PENDING-01` (owner C). |
| FR-005 | Budget rule (cumulative, equality allowed) | AC-007/008 | Policy core | `src/policy_core.py::enforce_budget` | `test_policy_core_smoke.py::test_inv003_equality_is_allowed`; `test_inv003_over_budget_rejected_with_review` | IN_MAIN | IMPLEMENTED_AND_TESTED | `budget_limit` origin (storage) absent → PD-003. Off-by-one boundary (`budget+0.01`) not separately parameterised. |
| FR-006 | Abnormal parse / illegal result handling | AC-010 (malformed envelope→LlmTransportError) | Model client | `src/call_llm.py::_post`; `src/call_llm.py::extract` | `test_pipeline_seam.py::test_post_raises_on_malformed_envelope`; `test_pipeline_seam.py::test_seam_transport_error_logs_once` | IN_MAIN | IMPLEMENTED_AND_TESTED | — |
| FR-007 | Block invalid data before state change | AC-011 (stop at first failure) | Policy core / pipeline | `src/policy_core.py::validate_record`; `src/pipeline.py::process` | `test_policy_core_smoke.py::test_validate_record_stops_at_first_failure` | IN_MAIN | IMPLEMENTED_AND_TESTED | No persistence layer exists, so "no state change" is structural, not observable in a store. |
| FR-008 | Logging & rejection-reason recording | AC-012 (one review line per rejection) | Pipeline | `src/call_llm.py::_append_log`; `src/pipeline.py::_append_review`; `src/pipeline.py::process` | `test_pipeline_seam.py::test_policy_rejection_writes_one_review_line` (params: `inv001-amount, inv002-category, inv003-budget`); `test_seam_returns_parsed_object_and_logs_once` | IN_MAIN | IMPLEMENTED_AND_TESTED | Fail-closed `OSError` branch is `# pragma: no cover` (environment failure) and therefore not exercised by a test. |

### 2.2 Non-functional requirements (NFR-001 … NFR-007)

| Requirement ID | Requirement Summary | Acceptance Criteria | Architecture Component | Source File / Function | Test File / Test Case | Runtime Monitor | Evidence Status | Verification Status | Phase-2 labels | Gap / Remarks |
|---|---|---|---|---|---|---|---|---|---|---|
| NFR-001 | Model API response time | — (no AC; threshold null) | Model client | `src/call_llm.py::extract` (live round-trip); D `src/measure_latency.py` | none on `main`; D `test/offline/test_measurement_scripts.py` (unmerged) | — | MISSING | NOT_VERIFIED | D-branch-implemented-unmerged; test-pending; runtime-evidence-pending | No approved latency budget; no committed live measurement (logs/ is a runtime artifact). D-reported p50/p95 are self-reported, not independent verification. pytest duration is **not** a proxy for API latency. PD-007 (owner B). |
| NFR-002 | Token consumption | — (threshold null) | Model client | `src/call_llm.py` (gateway usage capture); D `src/report_tokens.py` | none on `main`; D `test/offline/test_token_usage.py` (unmerged) | — | MISSING | NOT_VERIFIED | D-branch-implemented-unmerged; test-pending; runtime-evidence-pending | Per-request/per-session/api_call_count/usage_source(three-state)/missing-usage implemented on D's **unmerged** branch; `user_request_count` NOT implemented. No committed token-run evidence. Statistics only, no approved threshold. PD-007 (owner B). |
| NFR-003 | API call failure handling | transport-failure behaviour | Model client / policy | `src/call_llm.py::_post`; `src/call_llm.py::extract` | `test_pipeline_seam.py::test_seam_transport_error_logs_once`; `test_config_error_logs_once`; `test_post_raises_on_malformed_envelope` | — | IN_MAIN | PARTIALLY_IMPLEMENTED | main-implemented | Behaviour (RP-002) is tested; a pass/fail **threshold** (retry policy) and retry are pending C (PD-008). |
| NFR-004 | Data security (secrets), threshold = 0 | count of committed secrets | Call client / repo | `.env` gitignored; `.env.example` placeholders (`src/call_llm.py` reads env only) | none (no automated secret scan on `main`) | — | MISSING | PARTIALLY_IMPLEMENTED | main-implemented; test-pending | Threshold 0 is `approved`, but there is **no automated secret-scan test**; verification is manual grep only. |
| NFR-005 | Input/output reliability | rate of accepted records failing later checks | Policy core / pipeline | `src/policy_core.py::validate_record` (validation precedes return) | `test_policy_core_smoke.py::test_validate_record_stops_at_first_failure`; `test_validate_record_rejects_non_dict`; `test_pipeline_seam.py::test_policy_rejection_writes_one_review_line` | — | IN_MAIN | PARTIALLY_IMPLEMENTED | main-implemented | Behaviour is tested; no defined reliability tolerance / rate measurement. PD-007 (owner B). |
| NFR-006 | Log traceability | % calls and rejections with a log line | Model client / pipeline | `src/call_llm.py::_append_log`; `src/pipeline.py::_append_rejection`; D `src/storage.py` (call_id join) | `test_pipeline_seam.py::test_seam_returns_parsed_object_and_logs_once`; `test_seam_non_json_is_logged_then_reraised`; `test_policy_rejection_writes_one_review_line`; D `test/offline/test_evidence_join.py` (**skipped**) | — | IN_MAIN | PARTIALLY_IMPLEMENTED | main-implemented; D-branch-implemented-unmerged; test-pending | "Exactly one line" behaviour tested on `main`; call_id accepted/rejected join implemented on D's **unmerged** branch; the join test is **skipped** on D and only asserted on E's unmerged branch. No numeric coverage threshold. PD-008 (owner C). |
| NFR-007 | Testability | fraction of invariants with an offline negative test | test suite / CI | `test/offline/test_policy_core_smoke.py`; `test/offline/test_invariants.py` (E) | smoke INV tests on `main` (IN_MAIN); E `test/offline/test_invariants.py` (PENDING_MERGE) | — | IN_MAIN | IMPLEMENTED_AND_TESTED | main-implemented; D-branch-implemented-unmerged; test-pending | Original acceptance criterion (`verification`: "map each INV to at least one test that fails without the guard; run pytest test/offline") is **met on `main`**: INV-001/002/003 each have a `pytest.raises(PolicyError)` negative smoke test in `test_policy_core_smoke.py` that fails if the guard is removed, and `pytest test/offline` passes. **`main`'s `test/offline/test_invariants.py` has only 2 INV-001 tests.** E's dedicated `test_invariants.py` on the **unmerged** branch `feat/e-phase2-verification` (`cc6e650`) has **12 INV-related tests covering INV-001/002/003** (guard-removal negatives); those are E's **local** results on an unmerged branch and are **not** `main` or CI results. Status reflects the met original AC on `main`, not E's pending enhancement. |

### 2.3 Business invariants (INV-001 … INV-003, INV-PENDING-01)

| Requirement ID | Requirement Summary | Acceptance Criteria | Architecture Component | Source File / Function | Test File / Test Case | Evidence Status | Verification Status | Gap / Remarks |
|---|---|---|---|---|---|---|---|---|
| INV-001 | Amount finite, >0, ≤2 dp | AC-002/003/004 | Policy core guard | `src/policy_core.py::enforce_amount` | `test_policy_core_smoke.py::test_inv001_rejects_invalid_amount` (9 params); `test_inv001_accepts_boundary_and_returns_unchanged`; `test_inv001_never_returns_decimal` | IN_MAIN | IMPLEMENTED_AND_TESTED | Negative test fails if the guard is removed. E's INV-001 tests are `PENDING_MERGE`. |
| INV-002 | Category in closed whitelist (case-sensitive) | AC-005/006 | Policy core guard | `src/policy_core.py::enforce_category`; `src/policy_core.py::CATEGORY_WHITELIST` | `test_policy_core_smoke.py::test_inv002_rejects_out_of_vocabulary`; `test_inv002_accepts_every_whitelisted_category` | IN_MAIN | IMPLEMENTED_AND_TESTED | E branch adds **no** INV-002 test. Whitelist membership finality: `INV-PENDING-01`. |
| INV-003 | Cumulative spend ≤ budget (equality allowed) | AC-007/008 | Policy core guard | `src/policy_core.py::enforce_budget` | `test_policy_core_smoke.py::test_inv003_equality_is_allowed`; `test_inv003_over_budget_rejected_with_review` | IN_MAIN | IMPLEMENTED_AND_TESTED | E branch adds **no** INV-003 test. No separate `budget+0.01` / `budget-0.01` parametrised cases (equality + over-budget covered). |
| INV-PENDING-01 | Exact category whitelist membership final | — (pending) | Policy core constant | `src/policy_core.py::CATEGORY_WHITELIST` | `test_inv002_accepts_every_whitelisted_category` (reads current 8 values) | IN_MAIN | NOT_VERIFIED | Membership is exercised, but whether the 8 values are **final** is unconfirmed (owner C, PD-002). |

### 2.4 AI requirements (AI-REQ-001 … AI-REQ-008)

| Requirement ID | Requirement Summary | Acceptance Criteria | Architecture Component | Source File / Function | Test File / Test Case | Evidence Status | Verification Status | Gap / Remarks |
|---|---|---|---|---|---|---|---|---|
| AI-REQ-001 | AI does NLU/parsing only | — | Model client | `src/call_llm.py::extract` | `test_pipeline_seam.py::test_seam_returns_parsed_object_and_logs_once` | IN_MAIN | IMPLEMENTED_AND_TESTED | Design-level; exercised indirectly. |
| AI-REQ-002 | Model proposes, code disposes | — | Pipeline | `src/pipeline.py::process` | `test_pipeline_seam.py::test_policy_rejection_writes_one_review_line` | IN_MAIN | IMPLEMENTED_AND_TESTED | Behavioural (rejection path) proves code decides. |
| AI-REQ-003 | AI output passes schema validation before use | — | Policy core | `src/policy_core.py::validate_record` | `test_policy_core_smoke.py::test_validate_record_rejects_non_dict` | IN_MAIN | IMPLEMENTED_AND_TESTED | — |
| AI-REQ-004 | After schema, deterministic rule validation | — | Policy core | `src/policy_core.py::validate_record` (order INV-001→002→003) | `test_policy_core_smoke.py::test_validate_record_stops_at_first_failure` | IN_MAIN | IMPLEMENTED_AND_TESTED | — |
| AI-REQ-005 | Prompt injection can't alter safety rules | — | Policy core (rules in code) | `src/policy_core.py` (guards are code, not prompt) | `test_policy_core_smoke.py::test_policy_core_has_no_io_imports`; structural review | IN_MAIN | IMPLEMENTED_NOT_TESTED | No dedicated injection test; guarantee is structural (rules live in code). |
| AI-REQ-006 | Failed AI parse must not fabricate a record | — | Pipeline | `src/call_llm.py::extract` re-raises; `src/pipeline.py::process` | `test_pipeline_seam.py::test_seam_non_json_is_logged_then_reraised` | IN_MAIN | IMPLEMENTED_AND_TESTED | — |
| AI-REQ-007 | Apply RP-001/RP-002 on unexpected shape | — | Model client | `src/call_llm.py::_post`; `src/call_llm.py::extract` | `test_pipeline_seam.py::test_post_raises_on_malformed_envelope`; `test_seam_non_json_is_logged_then_reraised` | IN_MAIN | IMPLEMENTED_AND_TESTED | — |
| AI-REQ-008 | AI must not modify requirements/scope | — | Governance | `AGENTS.md`; `.opencode/permissions.jsonc` | process review (no code test) | IN_MAIN | IMPLEMENTED_NOT_TESTED | Process/governance control; not automatable as a unit test. |

### 2.5 Error-handling requirements (ERR-001 … ERR-005)

| Requirement ID | Requirement Summary | Acceptance Criteria | Architecture Component | Source File / Function | Test File / Test Case | Evidence Status | Verification Status | Gap / Remarks |
|---|---|---|---|---|---|---|---|---|
| ERR-001 | Non-JSON → log not_json + reraise (RP-001) | AC-009 | Model client | `src/call_llm.py::extract` | `test_pipeline_seam.py::test_seam_non_json_is_logged_then_reraised` | IN_MAIN | IMPLEMENTED_AND_TESTED | Asserts `error=="not_json"` and one log line. |
| ERR-002 | Transport/HTTP failure → LlmTransportError (RP-002) | AC-010 | Model client | `src/call_llm.py::_post`; `src/call_llm.py::extract` | `test_pipeline_seam.py::test_seam_transport_error_logs_once`; `test_config_error_logs_once` | IN_MAIN | IMPLEMENTED_AND_TESTED | — |
| ERR-003 | Invariant violation → PolicyError, no state change (RP-003/005/006) | AC-011/012 | Policy core / pipeline | `src/policy_core.py::validate_record`; `src/pipeline.py::process` | `test_policy_core_smoke.py::test_validate_record_stops_at_first_failure`; `test_pipeline_seam.py::test_policy_rejection_writes_one_review_line` | IN_MAIN | IMPLEMENTED_AND_TESTED | — |
| ERR-004 | Logging integrity fail-closed (RP-004) | — | Model client | `src/call_llm.py::_append_log` | none (the `OSError`→`LlmTransportError` path is `# pragma: no cover`) | MISSING | IMPLEMENTED_NOT_TESTED | Fail-closed code exists but the unwritable-log branch is not exercised by a test. |
| ERR-005 | Rejection evidence: one review line per rejection | AC-012 | Pipeline | `src/pipeline.py::_append_review` | `test_pipeline_seam.py::test_policy_rejection_writes_one_review_line` (3 params) | IN_MAIN | IMPLEMENTED_AND_TESTED | Asserts exact field set `{error,amount,category,spent,total,review}`. |

### 2.6 Security requirements (SEC-001 … SEC-005)

| Requirement ID | Requirement Summary | Acceptance Criteria | Architecture Component | Source File / Function | Test File / Test Case | Evidence Status | Verification Status | Gap / Remarks |
|---|---|---|---|---|---|---|---|---|
| SEC-001 | No secret in any committed file | — | Repo hygiene | `.gitignore`; `.env.example` placeholders; `src/call_llm.py` reads env | none (no automated secret scan) | MISSING | PARTIALLY_IMPLEMENTED | Enforced by process/gitignore; no automated scan on `main`. |
| SEC-002 | All model calls via `src/call_llm.py`; no other module imports `requests` for calls | — | Model client boundary | `src/call_llm.py` (only `requests` importer); `src/pipeline.py` imports no `requests` | `test_policy_core_smoke.py::test_policy_core_has_no_io_imports` (policy_core has no `requests`) | IN_MAIN | IMPLEMENTED_NOT_TESTED | No test asserts pipeline/extract are the *only* `requests` user; only policy_core is checked. |
| SEC-003 | `policy_core` never bypassed; every output checked before affecting data | AC-011 | Pipeline / policy core | `src/pipeline.py::process` (always calls `validate_record`) | `test_pipeline_seam.py::test_policy_rejection_writes_one_review_line` | IN_MAIN | IMPLEMENTED_AND_TESTED | Rejection path proves no bypass; no persistence to observe "before affecting data". |
| SEC-004 | `.env` not readable/writable by agent; secrets never logged | — | Governance / client | `.opencode/permissions.jsonc`; `src/call_llm.py` (logs input/raw/parsed/error only) | none (no automated test) | MISSING | PARTIALLY_IMPLEMENTED | Enforced by permission model; no automated test that secrets never appear in logs. |
| SEC-005 | Logging fail-closed; unlogged result not used | — | Model client | `src/call_llm.py::_append_log` | none (see ERR-004) | MISSING | IMPLEMENTED_NOT_TESTED | Same gap as ERR-004. |

> Note: there is no `SEC` acceptance-criterion id in `requirements.yaml`; the "Acceptance Criteria"
> column for SEC rows cites the related AC where one exists, otherwise "—". SEC rows are traced to
> code/governance, and are marked tested **only** when a real offline test exercises them.

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
The **unmerged** E branch `feat/e-phase2-verification` (`cc6e650`, verified 2026-11-16) adds a fuller
`test_invariants.py` with **12 INV-related tests covering INV-001/002/003** (guard-removal negatives).
E's branch results are **E's local results on an unmerged branch — not `main` or CI results**; they
must not be reported as passing on `main`/CI until merged and run in the hosted pipeline.

---

## 4. Coverage summary (computed from this matrix)

Counted rows: FR (8) + NFR (7) + invariants (4) + AI-REQ (8) + ERR (5) + SEC (5) = **37 requirement rows**.

### 4.1 Mapping coverage

| Metric | Count | Definition used |
|---|---|---|
| Total requirements traced | 37 | All real ids across the six groups. |
| With architecture-component mapping | 37 | Every row names a component. |
| With source-file/function mapping | 34 | 3 rows have no concrete function: NFR-001, NFR-002 (**no committed measurement evidence**; measurement code exists only on the unmerged `feat/D-phase2-measurement`) and AI-REQ-008 (governance only). |
| With a cited test-case mapping (incl. `PENDING_MERGE`) | 29 | A concrete test function name is cited in the "Test File / Test Case" column (including the two `PENDING_MERGE` E tests cited in remarks). |
| Without a cited test-case mapping | 8 | NFR-001, NFR-002, NFR-004, AI-REQ-008, ERR-004, SEC-001, SEC-004, SEC-005. These are **requirement rows**, not "gap rows": ERR-004 and SEC-005 share the same missing `OSError`→fail-closed test, but they remain two separate requirement rows and are counted as two. 29 + 8 = 37. |

### 4.2 Evidence-status distribution (per row; each row carries exactly one Evidence Status)

| Evidence Status | Count | Rows |
|---|---|---|
| IN_MAIN | 30 | every FR/AI-REQ/ERR/SEC/invariant row traced to `main` code/tests, plus NFR-003/005/006/007 (their `main` smoke evidence is the primary status; E's unmerged tests are noted only in remarks). |
| PENDING_MERGE | 0 | No row uses `PENDING_MERGE` as its **primary** status. The E `test_invariants.py` tests (both INV-001) are recorded as `PENDING_MERGE` in the remarks of FR-003 / INV-001 / NFR-007 and in §3, never as a row status. |
| MISSING | 7 | NFR-001, NFR-002 (**no committed measurement evidence**; measurement code only on the unmerged D branch); NFR-004, SEC-001, SEC-004 (no automated secret scan); ERR-004, SEC-005 (no fail-closed OSError test). |
| **Total** | **37** | Equals the matrix row count. |

> Because each row carries a **single** Evidence Status, the per-row counts above already equal the
> row count. Unmerged E evidence is always surfaced as `PENDING_MERGE` in its own remarks cell and is
> never promoted to `IN_MAIN`.
>
> **Phase-2 labels do not affect this count.** §2.2 adds a separate "Phase-2 labels" column whose
> values (`main-implemented` / `D-branch-implemented-unmerged` / `test-pending` /
> `runtime-evidence-pending`) are **multi-valued** and may coexist for one row. They are orthogonal to
> the single-valued Evidence Status counted here, so they do **not** change the 37-row tally or the
> distribution above.

### 4.3 Verification-status distribution

| Verification Status | Count | Rows (examples) |
|---|---|---|
| IMPLEMENTED_AND_TESTED | 23 | FR-001/002/003/004/005/006/007/008; INV-001/002/003; AI-REQ-001/002/003/004/006/007; ERR-001/002/003/005; SEC-003; NFR-007 (original testability AC met on `main`). |
| IMPLEMENTED_NOT_TESTED | 5 | AI-REQ-005, AI-REQ-008, SEC-002, ERR-004, SEC-005. |
| PARTIALLY_IMPLEMENTED | 6 | NFR-003, NFR-004, NFR-005, NFR-006, SEC-001, SEC-004. |
| NOT_IMPLEMENTED | 0 | — |
| NOT_VERIFIED | 3 | NFR-001, NFR-002, INV-PENDING-01. |

> Counts are conservative: a requirement is `IMPLEMENTED_AND_TESTED` only when its cited test is
> `IN_MAIN`. `PENDING_MERGE` tests never raise a row's status. The exact per-group tally is
> reproducible from the tables in §2.

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
| INV-002/003 boundary suite absent on `main` | `main` `test_invariants.py` has only INV-001 (2 tests); E branch `cc6e650` has 12 INV tests | INV-002/003, NFR-007 | E | **Open on `main`; covered on E's unmerged branch** | E's `feat/e-phase2-verification` (`cc6e650`) covers INV-001/002/003 with guard-removal negatives, but it is **unmerged** and its results are E's **local** results — not `main` or CI. |
| Runtime Monitor | `trace-matrix.md` §2.2 Runtime Monitor column | all | B | **Open / unconfirmed** | No confirmed continuous monitor exists; log files are outputs, not monitors (all Runtime Monitor cells remain `—`). |
