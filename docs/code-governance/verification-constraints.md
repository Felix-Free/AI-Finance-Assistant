# Verification Constraints (owner: role E)

> Purpose: state how this repository's verification evidence is produced and judged, so
> that a passing report means something specific. This is a governance document; it
> constrains claims, not code.
>
> Status: **Phase 2 (D4 QA).** Baseline: `main f73e9b4` + D #18 `eec1724` + C #19 `6808d7e`.
> It records what verification must demonstrate; results computed under a configuration
> that was not actually observed are never written as passed.

---

## 1. Four dimensions

Verification here is judged along four independent dimensions. A claim is only as strong
as the weakest dimension it relies on; a dimension that was not exercised is reported as
unverified, not as passed.

### 1.1 Test traceability

- Every offline test traces to a requirement id (`INV-###`, `NFR-###`, `RP-###`) or a named
  gap; tests with no traceable target are not treated as coverage.
- Positive and negative cases are both required. A happy-path-only suite cannot claim a
  guard is covered.
- The suite must be deterministic and network-free (`pytest test/offline -q`), and must not
  write to the repository's runtime paths (`logs/`, `data/`). Any test that mutates
  tracked or runtime state is a traceability defect, even if it passes.

### 1.2 The three invariants, as negative cases

- `INV-001` (finite positive amount, ≤ 2 decimals), `INV-002` (category in the code
  whitelist, exact match), `INV-003` (cumulative spend ≤ budget, equality allowed) must
  each have an offline negative test that **fails when its guard is removed**.
- `test/offline/test_invariants.py` isolates one negative per guard
  (`test_inv001_rejects_negative_amount`, `test_inv002_rejects_unknown_category`,
  `test_inv003_rejects_one_cent_over_budget`), so disabling one guard turns exactly that
  test red. A guard-removal run is the evidence, not the existence of the test.
- A negative test that also passes when its guard is disabled is not evidence of that
  guard.

### 1.3 Three-layer structure: structural, regression, semantic

- **Structural** — the freeze checks: single model entry point (`src/call_llm.py`), API
  shape, protected permissions, ADR present for security-critical changes
  (`.github/ci_checks.py::gate_static_analysis`, Gate 2).
- **Regression** — the full offline suite (Gate 5 / `branch-offline`): deterministic
  invariants and evidence-join wiring.
- **Semantic** — the live evaluation against the real gateway (Gate 4): spending inputs map
  to the expected `(amount, category)` and a non-expense sentence yields `not_a_record`.
  Semantic evidence requires the protected environment and a live call; it cannot be
  substituted by offline results.
- Each layer is reported separately. Passing structural and regression layers does not
  imply the semantic layer passed.

### 1.4 Real review

- Approval must be a real human, non-author, member approval on a **test-first** commit
  (implementation commits descend from it), not an AI-use-log entry
  (`.github/ci_checks.py::gate_test_approval`, Gate 1).
- A review is not "real" if it merely records that a session happened; the test-approval
  gate reads PR review state, not the log.
- Whether this gate has actually blocked a non-compliant PR on GitHub is itself a
  verification item (see §2).

---

## 2. Not to be claimed without evidence

The following are **still not verified** as of this document and must not be reported as
passed:

- An end-to-end real **test-first** review on GitHub that a human non-author approved on a
  test-only commit (Gate 1 was exercised in hosted CI, but an actual compliant approval flow
  is not demonstrated).
- A failing PR actually **being blocked** by the gates (merge blocking is unobserved).
- Semantic evaluation against a **live gateway** (`test/live`); it needs the protected
  environment and an approved key and has not been observed here. Offline mock results never
  establish NFR-001/002/003 or any semantic-layer pass.
- Independent online evidence for performance, permissions or the runtime contract beyond
  what a local review observed.

**Hosted CI status:** hosted CI already executed on PR #20
([run 43743304655](https://github.com/Felix-Free/AI-Finance-Assistant/actions/runs/43743304655)).
Real hosted test-first approval, the runtime semantic pass and merge blocking remain
unverified; "CI ran" is not "the gates verified the contract".

Local offline results (deterministic suite, guard-removal runs) are reported only with the
exact command and observed output recorded alongside them.

---

## 3. Requirements-to-test matrix (full offline inventory)

Scope: every module in `test/offline/` and the targeted regressions in
`test/offline/test_ci_regressions.py`. Node names are `module::function` with the `test_`
prefix stripped only where noted for brevity; `[param]` marks a parametrised case. A test
that verifies an implementation seam, tool handling, path or evidence but has **no formal
requirement** maps to an explicitly named **QA gap** (tension between this matrix and the
"no traceable target → not coverage" rule in §1.1 is resolved by naming the gap, not by
inventing a requirement).

IDs: `INV-001` amount, `INV-002` category, `INV-003` budget; `FR`/`NFR`/`RP` from
`requirements.yaml` and `runtime-policy-catalog.md`. `RP-001` invalid JSON, `RP-002`
config/transport/response-protocol, `RP-003` invariant violation, `RP-004` logging
integrity (fail-closed), `RP-005` budget, `RP-006` category, `RP-007` storage boundary.

### 3.1 `test_invariants.py` (12 test functions, 39 collected cases; E boundary suite)

| Requirement | Tests |
|---|---|
| INV-001 / FR-003 / RP-003 | `test_inv001_rejects_negative_amount`; `test_inv001_rejects_invalid_amount` |
| INV-001 / FR-003 (boundary, unchanged passthrough) | `test_inv001_accepts_boundary_amount_and_returns_unchanged` |
| INV-002 / FR-004 / RP-006 | `test_inv002_rejects_unknown_category`; `test_inv002_rejects_out_of_vocabulary` |
| INV-002 / FR-004 (positive vocabulary) | `test_inv002_accepts_every_implemented_category` |
| INV-003 / FR-005 / RP-005 | `test_inv003_rejects_one_cent_over_budget`; `test_inv003_rejects_over_the_limit` |
| INV-003 / FR-005 (equality allowed) | `test_inv003_accepts_up_to_the_limit` |
| FR-002 / FR-007 (order: amount first) | `test_validate_record_reports_amount_failure_first` |
| FR-004 / FR-007 (order: category before budget) | `test_validate_record_reports_category_failure_before_budget` |
| FR-005 / FR-007 (order: budget last) | `test_validate_record_reports_budget_failure` |

This is the suite §1.2 rests on: the `inv001/inv002/inv003` negatives are isolated so one
disabled guard reddens exactly one test.

### 3.2 `test_evidence_join.py` (12 tests)

| Requirement | Tests |
|---|---|
| RP-003 + NFR-006 evidence join (accepted) | `acceptance_call_id_joins_record` |
| RP-003/005/006 + NFR-006 join (rejected → review, storage unchanged) | `rejection_joins_review_and_leaves_storage_unchanged` |
| RP-004 (ten-key additive schema) | `every_log_line_has_exactly_ten_keys` |
| RP-002 / RP-004 token `usage_source` (`gateway`/`partial`/`missing`) | `usage_complete_is_gateway`; `usage_partial_keeps_missing_as_none`; `usage_missing_when_envelope_has_no_usage`; `usage_not_requested_when_config_missing` |
| NFR-006 / RP-004 fail-closed on call-log write | `call_log_append_open_failure_raises_and_persists_nothing` |
| RP-007 fail-closed on storage write (append open failure) | `accept_append_open_failure_raises_and_keeps_old_bytes` |
| **QA gap — evidence write** (review-log append failure is `StorageError`, not `policy:*`; RP-007 §5) | `rejection_append_open_failure_raises_storage_error` |

`NFR-006` here is the **Phase 2 `call_id` join contract** (one evidence pair per decision),
not a numeric coverage threshold; that threshold is `null` and unmeasured, so no NFR-006
*pass* is claimed from these checks.

### 3.3 `test_measurement_scripts.py` (36 tests; tooling → QA gap)

These exercise the measurement tooling behind NFR-001/002. An offline mock harness proves
the **reporting logic**, never a measured latency/token result; NFR-001/002 stay
`pending_confirmation` with `threshold: null`.

| Requirement | Tests |
|---|---|
| NFR-002 reporting / tooling (log-coverage counter, session completeness) | `report_no_file_prints_no_calls_and_exits_zero`; `report_mixed_log_counters_and_incomplete_session`; `report_mixed_session_is_incomplete_and_missing_shown_dash`; `report_all_gateway_session_complete`; `report_counts_only_request_made_true`; `existing_blocks_unchanged`; `report_tokens_log_path_matches_call_llm` |
| RP-002 `request_made` request grouping (NFR-002 session accounting) | `request_block_one_request_three_calls`; `request_block_two_requests_interleaved`; `request_block_missing_line_is_incomplete_and_footnoted`; `request_block_no_known_values_prints_dash_not_zero`; `request_block_excludes_not_called_lines`; `request_block_single_call_request` |
| QA gap — latency tool handling (NFR-001 reporting: dry-run, percentile, failure tally, low-confidence) | `measure_latency_dry_run_exits_zero_writes_nothing`; `percentile_nearest_rank`; `latency_failures_do_not_end_the_run`; `latency_counts_json_decode_error_as_failure`; `latency_percentiles_use_successes_only`; `latency_exits_2_when_nothing_succeeded`; `latency_low_confidence_line`; `latency_no_low_confidence_when_five_or_more`; `latency_dry_run_does_not_call_extract` |
| QA gap — token corpus / tool handling (NFR-002 tooling) | `token_corpus_has_at_least_twenty_sentences`; `token_corpus_has_at_least_eight_distinct_lengths`; `token_dry_run_does_not_call_extract`; `token_mixed_run_counts_failures_and_does_not_stop`; `token_all_fail_run_returns_two`; `token_file_corpus_cycles_when_n_exceeds_size`; `token_dry_run_reads_file_corpus_without_calling` |
| SEC-004 (no secret in *tool* failure labels; does not validate production call-log redaction or committed-secret scans) | `failure_kind_whitelist_shapes`; `failure_kind_label_never_carries_secrets`; `latency_failure_tally_carries_no_secrets` |
| QA gap — evidence-path anchoring (RP-007 §5 path contract) | `evidence_path_constants_point_at_distinct_files`; `evidence_paths_are_absolute_and_inside_repo`; `evidence_paths_follow_the_module_not_the_cwd`; `no_relative_evidence_path_literal_in_src` |

### 3.4 `test_pipeline_seam.py` (20 tests)

| Requirement | Tests |
|---|---|
| FR-001 / FR-008 / RP-004 (one call line) | `seam_returns_parsed_object_and_logs_once` |
| FR-001 / RP-001 (non-JSON logged once, re-raised) | `seam_non_json_is_logged_then_reraised` |
| FR-006 / RP-002 transport error logged once | `seam_transport_error_logs_once`; `config_error_logs_once` |
| FR-006 / RP-002 malformed envelope → `LlmTransportError` | `post_raises_on_malformed_envelope` |
| FR-008 / RP-003/005/006 (one review line per rejection) | `policy_rejection_writes_one_review_line` |
| NFR-006 (`call_id` joins call log and record) | `seam_success_call_id_joins_log_and_record` |
| RP-001 valid-nonobject gap (missing `call_id` → `StorageError`) | `process_without_call_id_raises_storage_error` |
| RP-007 §5 (review-write failure → `StorageError`, not `policy:*`) | `rejection_write_failure_raises_storage_error_not_policy` |
| RP-003 §5 / SEC-003 (`__call_id__` popped before `policy_core`) | `private_key_is_popped_before_validation` |
| FR-005 / INV-003 (`spent`) — default `None` reads stored total | `process_reads_running_total_from_storage`; `process_without_spent_passes_persisted_as_expected_spent` |
| FR-005 / INV-003/RP-005 (explicit under/over budget routing) | `process_explicit_spent_over_budget_is_policy_not_storage_error` |
| QA gap — pipeline defaults (budget default 1000; UTC seconds timestamp) | `process_default_budget_limit_is_1000`; `decided_at_is_utc_iso_seconds` |
| RP-007 (storage error from persist propagates) | `storage_error_from_persist_propagates` |
| FR-007 / RP-003/005/006 (rejection never persisted) | `rejection_is_evidence_only_never_persisted` |
| QA gap — request grouping (one `request_id` per process, RP-002 §5.2.1) | `request_id_generated_once_per_process` |

Note: D HEAD `df729a9` implements the `expected_spent` safeguard
(`runtime-policy-catalog.md` §5): `process_without_spent_passes_persisted_as_expected_spent`
and the `under/overreported_spent` rows in §3.6 exercise the persisted-total check that
rejects under-reporting, not an unsecured gap.

### 3.5 `test_policy_core_smoke.py` (32 tests, D smoke — overlaps §3.1)

| Requirement | Tests |
|---|---|
| INV-001 / FR-003 / RP-003 (negative + boundary) | `inv001_rejects_invalid_amount`; `inv001_rejects_minus_zero_point_zero_one` |
| INV-001 / FR-003 (unchanged passthrough, never `Decimal`) | `inv001_accepts_boundary_and_returns_unchanged`; `inv001_never_returns_decimal` |
| INV-002 / FR-004 / RP-006 | `inv002_rejects_out_of_vocabulary`; `inv002_accepts_every_whitelisted_category` |
| INV-003 / FR-005 / RP-005 (equality + over budget) | `inv003_equality_is_allowed`; `inv003_over_budget_rejected_with_review` |
| FR-002 (non-dict → `policy:amount`; normalised record) | `validate_record_rejects_non_dict`; `validate_record_returns_normalised_record` |
| FR-007 (stops at first failure) | `validate_record_stops_at_first_failure` |
| SEC-002 / structural (no I/O imports in `policy_core`) | `policy_core_has_no_io_imports` |

Several names appear twice with different `nodeid`s (`test/policy_core_smoke` vs
`test/invariants`); the fully qualified node disambiguates. Smoke does **not** replace the
boundary negatives of §3.1 for guard-removal evidence.

### 3.6 `test_storage.py` (42 tests)

| Requirement | Tests |
|---|---|
| FR-008 / RP-007 (append validated, create dir, one line) | `append_validated_writes_one_line`; `append_validated_creates_parent_directory` |
| RP-007 (duplicate / missing / non-string `call_id`) | `append_validated_rejects_duplicate_call_id`; `append_validated_rejects_missing_call_id`; `append_validated_rejects_non_string_call_id`; `stored_call_id_must_be_non_empty_string` |
| RP-007 (shape/type checks) | `append_validated_rejects_non_numeric_fields`; `append_validated_rejects_missing_required_field`; `append_validated_rejects_unknown_private_key`; `append_validated_rejects_non_string_category` |
| RP-007 (read path) | `current_total_raises_on_non_numeric_amount`; `current_total_sums_amounts`; `current_total_zero_when_absent`; `iter_records_yields_stored_records`; `iter_records_malformed_line_raises` |
| INV-001/002/003 still enforced via storage (direct pass-through is policy) | `append_validated_direct_overbudget_is_policy_rejection`; `append_validated_direct_negative_amount_is_policy_rejection`; `append_validated_direct_bad_category_is_policy_rejection` |
| RP-005 / INV-003 — `expected_spent` safeguard (under persisted total rejected; inconsistent arithmetic rejected; valid total written) | `append_validated_underreported_spent_is_storage_error`; `append_validated_overreported_spent_writes`; `append_validated_expected_spent_equal_to_persisted_writes`; `append_validated_arithmetic_inconsistency_is_storage_error`; `append_validated_none_expected_spent_uses_persisted`; `append_validated_rejects_non_numeric_expected_spent` |
| INV-003 / RP-005 (decimal sum not a float error) | `append_validated_decimal_sum_is_not_rejected_by_float_error` |
| RP-007 boundary (non-serialisable field → `StorageError`, not raw `TypeError`) | `append_validated_rejects_non_serialisable_field` |
| SEC-002 (storage has no network import) | `storage_has_no_network_import` |
| SEC-003 / structural (policy_core must not import storage) | `policy_core_does_not_import_storage` |

### 3.7 `test_token_usage.py` (20 tests)

| Requirement | Tests |
|---|---|
| RP-002 / RP-004 (config fail no request; transport/non-200/malformed/non-JSON request made) | `config_failure_no_request`; `transport_failure_request_made_no_usage`; `non_200_request_made_no_usage`; `malformed_envelope_request_made_no_usage`; `non_json_request_made_no_usage` |
| NFR-002 / RP-004 token accounting (`gateway`/`partial`; missing → `null`, never zero) | `success_without_usage`; `success_with_full_usage`; `success_with_partial_usage_keeps_known_values` |
| RP-004 ten-key schema + `usage_source` consistency | `all_ten_fields_present_on_success`; `failure_line_has_exactly_ten_keys`; `every_path_is_consistent`; `every_path_key_set_is_exactly_ten` |
| RP-004 §5.2.1 identifiers (32-hex; session stable, request differs) | `ids_are_32_hex`; `session_id_stable_across_calls_request_id_differs`; `explicit_request_id_is_used` |
| RP-004 (one line per call) | `one_line_per_call_on_success` |
| RP-002 / NFR-002 `post` usage mapping (unknown keys → `None`, non-int → null) | `post_maps_usage`; `post_without_usage_returns_none`; `post_partial_usage_unknown_keys_none`; `post_non_int_usage_becomes_null` |

Offline token tests verify the **contract** (fields, `usage_source`, no fabrication); they
do **not** measure NFR-002 token consumption against a live gateway.

### 3.8 `test_ci_regressions.py` (3 test functions, 4 collected cases; present, targeted GitHub #20 review regressions)

| Requirement / gap | Tests |
|---|---|
| QA gap — Gate 1 (BUG-01): docs-only approval rejected, test-only accepted | `test_gate1_rejects_docs_only_approval[docs-only-rejected]`; `test_gate1_rejects_docs_only_approval[test-only-accepted]` |
| QA gap — offline isolation (BUG-02 / RP-004 fail-closed / §1.1 no runtime writes): budget node runs network-blocked and mutates no file under `logs/` or `data/` | `test_budget_regression_leaves_runtime_paths_unchanged` |
| QA gap — Gate 1 PR #20 one-time waiver: real `ci.yml` approval step expression pins the repo + PR #20 + `skip-test-gate` conjunction, and the actual step shell is run (via `bash -s`) with a `python` stub | `test_gate1_pr20_waiver` |

Each carries `pytestmark = pytest.mark.offline`. The Gate 1 node drives the real
`gate_test_approval` in a synthetic repo: it verifies the **rule**, not a live GitHub PR, so
it does not by itself verify real test-first approval or merge blocking (§2).
`test_gate1_pr20_waiver` reads the step from the real `ci.yml` and runs its real shell body;
it **pins the exact policy expression locally** and does **not** emulate GitHub's expression
engine, PR metadata or hosted CI, and it makes no network call.

### 3.9 Inventory baseline and coverage notes

- **Published baseline inventory (not a future fixed count):** the original seven modules
  collect **201** offline cases = **51 marked** (`pytest.mark.offline`) + **150 unmarked**;
  `test_invariants` 39, `test_evidence_join` 12, `test_measurement_scripts` 36,
  `test_pipeline_seam` 20, `test_policy_core_smoke` 32, `test_storage` 42, `test_token_usage`
  20. `test_ci_regressions` adds **4 new marked offline cases**. Total offline collected =
  **205** (51 + 150 + 4). The **5 live cases** in `test/live/` are collected separately and
  are not part of the 205. These are the published baseline at this phase, not a promised,
  frozen post-change number; counts move with parametrisation and future E tests.
- **Marker enforcement:** `pytest.ini` sets `addopts = --strict-markers`, so an **unknown
  marker name is an error**, not a silent skip. `offline` and `live` are the registered
  custom suite markers; pytest's built-in markers remain available.
- **Complete directory, no exclusions:** Gate 5 runs `python -m pytest test/offline -q`
  (the **whole** `test/offline/` directory). There is **no** `--ignore`, `-k`, or
  `-m` selection, so **no known unmarked offline test is excluded** — every module above,
  marked or not, runs.
- **Live is separate:** `test/live/` is not in `test/offline/`; it is run only by Gate 4 in
  the protected `semantic-eval` environment. Offline green never implies live/semantic green.
- **No NFR pass from offline mocks:** NFR-001 (latency), NFR-002 (tokens) and NFR-003 (API
  failure handling) have `threshold: null` or a live-only verification; offline tests of the
  contract are reported as **contract coverage**, never as a **measured NFR pass**.
