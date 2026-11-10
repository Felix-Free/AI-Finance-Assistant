# Traceability Matrix (owner: role B)

> Purpose: a **standalone** requirement-to-evidence trace, mapping every real requirement id in
> `docs/req/requirements.yaml` to its architecture component, source function, and test case, with
> an explicit evidence-status field that distinguishes what is on `main` from what only exists on an
> unmerged branch.
>
> Baseline recorded for this matrix:
>
> - `main` HEAD `0dda36b` (Merge pull request #9, `feat/D-policy-core`). `main` contains
>   `src/call_llm.py`, `src/policy_core.py`, `src/pipeline.py`, and the offline tests
>   `test/offline/test_policy_core_smoke.py` + `test/offline/test_pipeline_seam.py`. CI is **not**
>   on `main`.
> - `origin/feat/e-ci-skeleton` HEAD `7d29552` adds `.github/workflows/ci.yml`, `pytest.ini`,
>   `test/offline/test_invariants.py` (two INV-001 tests) and a `requirements.txt` update. **None of
>   this is on `main` yet.**
>
> This file does **not** modify or restate requirement text; `requirements.yaml` remains the single
> source of truth for requirement content. It does **not** invent ids: every id below appears in
> `requirements.yaml`.

---

## 1. How to read this matrix

### 1.1 Evidence Status (where the evidence lives)

| Value | Meaning |
|---|---|
| `IN_MAIN` | The named test/CI exists on `main` (`0dda36b`) and runs from the merged code. |
| `PENDING_MERGE` | The evidence exists only on an unmerged remote branch (`origin/feat/e-ci-skeleton`) and must be treated as **not yet present** on `main`. |
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

---

## 2. Full traceability matrix

### 2.1 Functional requirements (FR-001 … FR-008)

| Requirement ID | Requirement Summary | Acceptance Criteria | Architecture Component | Source File / Function | Test File / Test Case | Evidence Status | Verification Status | Gap / Remarks |
|---|---|---|---|---|---|---|---|---|
| FR-001 | NL sentence → model parse via single entry point | AC-001 (valid→JSON+1 log line), AC-009 (non-JSON→log+reraise) | Model client (single seam) | `src/call_llm.py::extract` | `test_pipeline_seam.py::test_seam_returns_parsed_object_and_logs_once`; `test_pipeline_seam.py::test_seam_non_json_is_logged_then_reraised` | IN_MAIN | IMPLEMENTED_AND_TESTED | Live-gateway path (`test/live`) not run without an approved key. |
| FR-002 | Structured extraction + field checks (non-dict rejected) | AC-013 (JSON array→policy:amount) | Policy core | `src/policy_core.py::validate_record` | `test_policy_core_smoke.py::test_validate_record_rejects_non_dict`; `test_policy_core_smoke.py::test_validate_record_returns_normalised_record` | IN_MAIN | IMPLEMENTED_AND_TESTED | — |
| FR-003 | Amount validity (finite, >0, ≤2 dp) | AC-002/003/004 | Policy core | `src/policy_core.py::enforce_amount` | `test_policy_core_smoke.py::test_inv001_rejects_invalid_amount` (params: `-1,0,0.005,100.001,"350",None,True,nan,inf`); `test_inv001_accepts_boundary_and_returns_unchanged`; `test_inv001_never_returns_decimal` | IN_MAIN | IMPLEMENTED_AND_TESTED | E's `test_invariants.py::test_inv001_rejects_negative_amount` / `test_inv001_accepts_valid_amount` are `PENDING_MERGE`; they are a subset of the smoke coverage and add no new boundary. |
| FR-004 | Category validity (closed whitelist, case-sensitive) | AC-005/006 | Policy core | `src/policy_core.py::enforce_category` | `test_policy_core_smoke.py::test_inv002_rejects_out_of_vocabulary` (params: `Food,餐饮,meal,"",None,1`); `test_inv002_accepts_every_whitelisted_category` (all 8 values) | IN_MAIN | IMPLEMENTED_AND_TESTED | Whitelist finality is `C-INV-PENDING-01` (owner C). |
| FR-005 | Budget rule (cumulative, equality allowed) | AC-007/008 | Policy core | `src/policy_core.py::enforce_budget` | `test_policy_core_smoke.py::test_inv003_equality_is_allowed`; `test_inv003_over_budget_rejected_with_review` | IN_MAIN | IMPLEMENTED_AND_TESTED | `budget_limit` origin (storage) absent → PD-003. Off-by-one boundary (`budget+0.01`) not separately parameterised. |
| FR-006 | Abnormal parse / illegal result handling | AC-010 (malformed envelope→LlmTransportError) | Model client | `src/call_llm.py::_post`; `src/call_llm.py::extract` | `test_pipeline_seam.py::test_post_raises_on_malformed_envelope`; `test_pipeline_seam.py::test_seam_transport_error_logs_once` | IN_MAIN | IMPLEMENTED_AND_TESTED | — |
| FR-007 | Block invalid data before state change | AC-011 (stop at first failure) | Policy core / pipeline | `src/policy_core.py::validate_record`; `src/pipeline.py::process` | `test_policy_core_smoke.py::test_validate_record_stops_at_first_failure` | IN_MAIN | IMPLEMENTED_AND_TESTED | No persistence layer exists, so "no state change" is structural, not observable in a store. |
| FR-008 | Logging & rejection-reason recording | AC-012 (one review line per rejection) | Pipeline | `src/call_llm.py::_append_log`; `src/pipeline.py::_append_review`; `src/pipeline.py::process` | `test_pipeline_seam.py::test_policy_rejection_writes_one_review_line` (params: `inv001-amount, inv002-category, inv003-budget`); `test_seam_returns_parsed_object_and_logs_once` | IN_MAIN | IMPLEMENTED_AND_TESTED | Fail-closed `OSError` branch is `# pragma: no cover` (environment failure) and therefore not exercised by a test. |

### 2.2 Non-functional requirements (NFR-001 … NFR-007)

| Requirement ID | Requirement Summary | Acceptance Criteria | Architecture Component | Source File / Function | Test File / Test Case | Evidence Status | Verification Status | Gap / Remarks |
|---|---|---|---|---|---|---|---|---|
| NFR-001 | Model API response time | — (no AC; threshold null) | Model client | `src/call_llm.py::extract` (live round-trip) | none (no latency test on `main`) | MISSING | NOT_VERIFIED | No approved latency budget; no live measurement. pytest duration is **not** a proxy for API latency. PD-007 (owner B). |
| NFR-002 | Token consumption | — (threshold null) | Model client | `src/call_llm.py` (gateway usage) | none | MISSING | NOT_VERIFIED | Gateway may not expose token usage; no measurement. PD-007 (owner B). |
| NFR-003 | API call failure handling | transport-failure behaviour | Model client / policy | `src/call_llm.py::_post`; `src/call_llm.py::extract` | `test_pipeline_seam.py::test_seam_transport_error_logs_once`; `test_config_error_logs_once`; `test_post_raises_on_malformed_envelope` | IN_MAIN | PARTIALLY_IMPLEMENTED | Behaviour (RP-002) is tested; a pass/fail **threshold** (retry policy) and retry are pending C (PD-008). |
| NFR-004 | Data security (secrets), threshold = 0 | count of committed secrets | Call client / repo | `.env` gitignored; `.env.example` placeholders (`src/call_llm.py` reads env only) | none (no automated secret scan on `main`) | MISSING | PARTIALLY_IMPLEMENTED | Threshold 0 is `approved`, but there is **no automated secret-scan test**; verification is manual grep only. |
| NFR-005 | Input/output reliability | rate of accepted records failing later checks | Policy core / pipeline | `src/policy_core.py::validate_record` (validation precedes return) | `test_policy_core_smoke.py::test_validate_record_stops_at_first_failure`; `test_validate_record_rejects_non_dict`; `test_pipeline_seam.py::test_policy_rejection_writes_one_review_line` | IN_MAIN | PARTIALLY_IMPLEMENTED | Behaviour is tested; no defined reliability tolerance / rate measurement. PD-007 (owner B). |
| NFR-006 | Log traceability | % calls and rejections with a log line | Model client / pipeline | `src/call_llm.py::_append_log`; `src/pipeline.py::_append_review` | `test_pipeline_seam.py::test_seam_returns_parsed_object_and_logs_once`; `test_seam_non_json_is_logged_then_reraised`; `test_policy_rejection_writes_one_review_line` | IN_MAIN | PARTIALLY_IMPLEMENTED | "Exactly one line" behaviour is tested; no numeric coverage threshold. PD-008 (owner C). |
| NFR-007 | Testability | fraction of invariants with an offline negative test | test suite / CI | `test/offline/test_policy_core_smoke.py`; `test/offline/test_invariants.py` (E) | smoke INV tests on `main` (IN_MAIN); E `test/offline/test_invariants.py::test_inv001_rejects_negative_amount` and `test_inv001_accepts_valid_amount` (PENDING_MERGE) | IN_MAIN | IMPLEMENTED_AND_TESTED | Original acceptance criterion (`verification`: "map each C-INV to at least one test that fails without the guard; run pytest test/offline") is **met on `main`**: C-INV-001/002/003 each have a `pytest.raises(PolicyError)` negative smoke test in `test_policy_core_smoke.py` that fails if the guard is removed, and `pytest test/offline` passes. Enhancement NOT yet done (and NOT part of the original AC — appears only in E's `notes`): E's dedicated `test/offline/test_invariants.py` covers only INV-001 (two tests, a subset; it does NOT cover INV-002/003) and is PENDING_MERGE; CI is PENDING_MERGE. Status reflects the met original AC, not the pending enhancement. |

### 2.3 Business invariants (C-INV-001 … C-INV-003, C-INV-PENDING-01)

| Requirement ID | Requirement Summary | Acceptance Criteria | Architecture Component | Source File / Function | Test File / Test Case | Evidence Status | Verification Status | Gap / Remarks |
|---|---|---|---|---|---|---|---|---|
| C-INV-001 | Amount finite, >0, ≤2 dp | AC-002/003/004 | Policy core guard | `src/policy_core.py::enforce_amount` | `test_policy_core_smoke.py::test_inv001_rejects_invalid_amount` (9 params); `test_inv001_accepts_boundary_and_returns_unchanged`; `test_inv001_never_returns_decimal` | IN_MAIN | IMPLEMENTED_AND_TESTED | Negative test fails if the guard is removed. E's INV-001 tests are `PENDING_MERGE`. |
| C-INV-002 | Category in closed whitelist (case-sensitive) | AC-005/006 | Policy core guard | `src/policy_core.py::enforce_category`; `src/policy_core.py::CATEGORY_WHITELIST` | `test_policy_core_smoke.py::test_inv002_rejects_out_of_vocabulary`; `test_inv002_accepts_every_whitelisted_category` | IN_MAIN | IMPLEMENTED_AND_TESTED | E branch adds **no** INV-002 test. Whitelist membership finality: `C-INV-PENDING-01`. |
| C-INV-003 | Cumulative spend ≤ budget (equality allowed) | AC-007/008 | Policy core guard | `src/policy_core.py::enforce_budget` | `test_policy_core_smoke.py::test_inv003_equality_is_allowed`; `test_inv003_over_budget_rejected_with_review` | IN_MAIN | IMPLEMENTED_AND_TESTED | E branch adds **no** INV-003 test. No separate `budget+0.01` / `budget-0.01` parametrised cases (equality + over-budget covered). |
| C-INV-PENDING-01 | Exact category whitelist membership final | — (pending) | Policy core constant | `src/policy_core.py::CATEGORY_WHITELIST` | `test_inv002_accepts_every_whitelisted_category` (reads current 8 values) | IN_MAIN | NOT_VERIFIED | Membership is exercised, but whether the 8 values are **final** is unconfirmed (owner C, PD-002). |

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

## 3. Branch-evidence separation (main vs. E `feat/e-ci-skeleton`)

| Artifact | On `main` (`0dda36b`)? | Status | What it is |
|---|---|---|---|
| `src/call_llm.py`, `src/policy_core.py`, `src/pipeline.py` | Yes | IN_MAIN | Implementation. |
| `test/offline/test_policy_core_smoke.py` | Yes | IN_MAIN | Smoke tests for INV-001/002/003 + validate_record. |
| `test/offline/test_pipeline_seam.py` | Yes | IN_MAIN | Seam + rejection-logging tests. |
| `.github/workflows/ci.yml` | **No** | PENDING_MERGE | CI workflow (branch `feat/e-ci-skeleton`, `7d29552`). |
| `pytest.ini` | **No** | PENDING_MERGE | Offline/live markers. |
| `requirements.txt` (`jsonschema`, `ruff`) additions | **No** | PENDING_MERGE | New dev deps. |
| `test/offline/test_invariants.py::test_inv001_rejects_negative_amount` | **No** | PENDING_MERGE | Negative INV-001 (subset of smoke). |
| `test/offline/test_invariants.py::test_inv001_accepts_valid_amount` | **No** | PENDING_MERGE | Positive INV-001 (subset of smoke). |

**Important:** the E branch adds **no** INV-002 or INV-003 test. Any statement that E supplied a
"full boundary suite" is **incorrect**; on the current E HEAD only two INV-001 tests exist.

---

## 4. Coverage summary (computed from this matrix)

Counted rows: FR (8) + NFR (7) + invariants (4) + AI-REQ (8) + ERR (5) + SEC (5) = **37 requirement rows**.

### 4.1 Mapping coverage

| Metric | Count | Definition used |
|---|---|---|
| Total requirements traced | 37 | All real ids across the six groups. |
| With architecture-component mapping | 37 | Every row names a component. |
| With source-file/function mapping | 34 | 3 rows have no concrete function: NFR-001, NFR-002 (no measurement code) and AI-REQ-008 (governance only). |
| With a cited test-case mapping (incl. `PENDING_MERGE`) | 29 | A concrete test function name is cited in the "Test File / Test Case" column (including the two `PENDING_MERGE` E tests cited in remarks). |
| Without a cited test-case mapping | 8 | NFR-001, NFR-002, NFR-004, AI-REQ-008, ERR-004, SEC-001, SEC-004, SEC-005. These are **requirement rows**, not "gap rows": ERR-004 and SEC-005 share the same missing `OSError`→fail-closed test, but they remain two separate requirement rows and are counted as two. 29 + 8 = 37. |

### 4.2 Evidence-status distribution (per row; each row carries exactly one Evidence Status)

| Evidence Status | Count | Rows |
|---|---|---|
| IN_MAIN | 30 | every FR/AI-REQ/ERR/SEC/invariant row traced to `main` code/tests, plus NFR-003/005/006/007 (their `main` smoke evidence is the primary status; E's unmerged tests are noted only in remarks). |
| PENDING_MERGE | 0 | No row uses `PENDING_MERGE` as its **primary** status. The E `test_invariants.py` tests (both INV-001) are recorded as `PENDING_MERGE` in the remarks of FR-003 / C-INV-001 / NFR-007 and in §3, never as a row status. |
| MISSING | 7 | NFR-001, NFR-002 (no measurement code); NFR-004, SEC-001, SEC-004 (no automated secret scan); ERR-004, SEC-005 (no fail-closed OSError test). |
| **Total** | **37** | Equals the matrix row count. |

> Because each row carries a **single** Evidence Status, the per-row counts above already equal the
> row count. Unmerged E evidence is always surfaced as `PENDING_MERGE` in its own remarks cell and is
> never promoted to `IN_MAIN`.

### 4.3 Verification-status distribution

| Verification Status | Count | Rows (examples) |
|---|---|---|
| IMPLEMENTED_AND_TESTED | 23 | FR-001/002/003/004/005/006/007/008; C-INV-001/002/003; AI-REQ-001/002/003/004/006/007; ERR-001/002/003/005; SEC-003; NFR-007 (original testability AC met on `main`). |
| IMPLEMENTED_NOT_TESTED | 5 | AI-REQ-005, AI-REQ-008, SEC-002, ERR-004, SEC-005. |
| PARTIALLY_IMPLEMENTED | 6 | NFR-003, NFR-004, NFR-005, NFR-006, SEC-001, SEC-004. |
| NOT_IMPLEMENTED | 0 | — |
| NOT_VERIFIED | 3 | NFR-001, NFR-002, C-INV-PENDING-01. |

> Counts are conservative: a requirement is `IMPLEMENTED_AND_TESTED` only when its cited test is
> `IN_MAIN`. `PENDING_MERGE` tests never raise a row's status. The exact per-group tally is
> reproducible from the tables in §2.

---

## 5. Known gaps carried forward

| Gap | Evidence source | Requirement(s) | Owner | Note |
|---|---|---|---|---|
| CI not on `main` | `feat/e-ci-skeleton` `7d29552` | NFR-007 | E | Merge after B's requirements files land (CI schema step depends on them). |
| No live latency/token measurement | `test/live/` empty; thresholds null | NFR-001, NFR-002 | B | PD-007; do not substitute pytest timing. |
| Fail-closed log branch untested | `src/call_llm.py` `# pragma: no cover` | ERR-004, SEC-005 | D/E | Environment-failure branch. |
| No automated secret scan | `.gitignore` only | NFR-004, SEC-001, SEC-004 | B/C | Manual verification only. |
| Only `policy_core` import-checked | `test_policy_core_has_no_io_imports` | SEC-002 | E | No test asserts pipeline/extract import `requests` alone. |
| Dedicated INV-002/003 boundary suite absent | E `test_invariants.py` has only INV-001 | C-INV-002/003, NFR-007 | E | Smoke tests cover them on `main`; "exhaustive" suite is still E's deliverable. |
