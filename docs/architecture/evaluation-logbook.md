# Evaluation Logbook (owner: roles C and E)

> Purpose: the running record of **non-functional requirements (NFRs)** for the finance
> assistant — what is measured, against which threshold, from which input, by which
> procedure, with which evidence, and what was actually observed. This logbook is where an
> NFR moves from "pending" to a measured result; a threshold without an observed result is
> marked **pending**, never assumed to pass.
>
> Status: **Phase 2 NFR registry with Phase 3 C audit evidence.** Main supplies the NFR
> registry and threshold fields; C records the policy and evidence contract, E runs the
> measurement, and D implements the pipeline. No measurement result is recorded here
> until it has actually been run. The post-merge security audit is recorded in §6 against
> `main@06ec2f5`; §5 is retained as the historical audit of the earlier C checkout.

---

## 1. How to read this logbook

- **Result states.** `pending` — not yet measured. `measured` — the procedure in §2 was
  actually run and the observed value is recorded below. `blocked` — the procedure cannot
  run yet because the pipeline/evidence it needs does not exist. A `pending` or `blocked`
  NFR is **not** a pass.
- **No invented results.** The observed result is copied from a run whose output is
  attached (evidence file or command output). If it was not run, it says so.
- **IDs and source.** The current [`main` requirements registry](https://github.com/Felix-Free/AI-Finance-Assistant/blob/main/docs/req/requirements.yaml)
  uses `NFR-001` through `NFR-007`; those IDs and descriptions govern this logbook.
  `docs/code-governance/structural-constraints.md §3` separately specifies a
  `REQ-NFR-###` document convention. A formal mapping between the two namespaces has
  not been recorded; the extra prefix is not assumed here.

---

## 2. Logbook entries

### NFR-001 — Model API response time

| Field | Value |
|---|---|
| NFR | Model API response time for an `extract` round trip. |
| Metric | Wall-clock latency per round trip; D's report also shows `attempted`, `ok`, `failed`, `failure_rate`, and successful-call p50/p95/max in ms. |
| Threshold | `null` in main; no approved latency budget. |
| Input / data source | Live gateway samples in `logs/latency.jsonl`, produced by `scripts/measure_latency.py` with a fixed probe sentence. |
| Measurement command / procedure | PR #42 ran `python -m scripts.measure_latency --n 20`; report p50/p95 for successful samples with `(n=ok)` and max separately. Transport and model-content JSON errors are counted as failures. Other errors, including failure to append a successful sample, may stop the run. |
| Expected evidence files | `logs/latency.jsonl` and a run report under `docs/measurements/`. |
| Owner | B (requirement), D (script), E (measurement). |
| Status | measured |
| Observed result | [PR #42 final NFR report](../measurements/final-nfr-verification.md) records 20 successful real-gateway calls with a fixed synthetic input: p50 2422.222 ms, p95 2850.720 ms, max 3072.404 ms; 0 failures. |

> **Historical C-checkout note.** This C branch snapshot predates the merged measurement
> script. The measurement evidence is from the merged main baseline documented in PR #42,
> not from a local run on this C checkout.

> **Superseded historical report.** D's debt ledger reported
> `n=20: p50 2356.7 ms / p95 4759.5 ms / max 5771.2 ms`. This does not count as a
> measured result; it is retained as historical context. The newer reproducible E result is
> recorded above and in PR #42's final NFR report.

### NFR-002 — Token Usage statistics

| Field | Value |
|---|---|
| NFR | Token usage per request and per session. |
| Metric | Per-request aggregation, per-session aggregation, attempted API-call count, usage-source distribution, missing-usage count, and `usage_source`↔`tokens` consistency. |
| Session grouping | D generates `session_id` once when `src/call_llm.py` is loaded and shares it across calls in that process. A `session_id` group therefore represents a process run, not necessarily one user's session if the process serves multiple users. |
| Threshold | `null` in main; no approved token budget. Per-request, per-session, attempted API-call count, usage-source distribution and missing-usage count are reported as statistics only. The consistency rule is checked structurally: `usage_source` must agree with `tokens`; it has no separately approved numeric threshold. |
| Input / data source | `logs/llm_calls.jsonl` records produced by the measurement run, including `session_id`, `request_id`, `call_id`, `tokens`, `usage_source` and `request_made`. |
| Measurement command / procedure (required by C) | Over the produced `llm_calls` records, compute: (a) **per-session aggregation** grouped by `session_id`; (b) **per-request aggregation** grouped by `request_id` (one request may span multiple calls); (c) **`api_call_count`** = number of rows with `request_made: true`; (d) the **usage-source distribution** over `request_made: true` rows across the three stored `usage_source` values `gateway`, `partial`, `missing`; (e) **missing-usage count** = `request_made: true` rows with `usage_source: missing`. Rows with `request_made: false` are counted separately as **`not_called_calls`** and **excluded** from the usage-source distribution and missing-usage count; `not_called` is derived from `request_made=false`, not a fourth `usage_source` value. Three recorded integers → `gateway`; at least one recorded integer and one `null` → `partial`; `tokens: null` or three `null` counts → `missing`. Non-integer counts in a processed usage object normalize to `null`. Check `usage_source` agrees with recorded `tokens` and missing counts are never replaced with `0` or estimates. `tokens` is always present: it is `null` when usage was not recorded (including model-content JSON parse failure), or an object with `input`, `output` and `total` when usage was processed (missing counts `null`). These are descriptive statistics, with no pass/fail judgment. |
| Meaning of `api_call_count` | `request_made: true` counts attempted HTTP calls, including DNS, connection and timeout failures. It does not count only requests known to have reached the gateway. |
| Meaning of `usage_source: missing` | No usable token counts were recorded in that log line. On a JSON parsing failure, D records `tokens: null` and `usage_source: missing` even if the gateway response included usage. Therefore the missing-usage count cannot establish how often the gateway omitted usage. |
| Report implementation on `main@06ec2f5` | `src/report_tokens.py` produces per-call rows (including `call_id`, `request_id`, `session_id`, token counts and `usage_source`), per-session aggregation, per-request aggregation, and global counters (`total_api_calls`, `usage_complete_calls`, `usage_missing_calls`, `usage_partial_calls`, `not_called_calls`). PR #42 records a real-gateway sample and token aggregation from 20 calls. |
| Expected evidence files | `docs/measurements/` report for NFR-002 and the `llm_calls` excerpts used for the aggregation and consistency checks. |
| Owner | B (definition), E (measurement), D (logging fields and report). |
| Status | measured |
| Observed result | [PR #42 final NFR report](../measurements/final-nfr-verification.md): 20/20 calls had complete gateway usage; each reported 125 input, 12 output, 137 total tokens. One process session totaled 2500 input, 240 output, 2740 total tokens. |

> **Superseded historical report.** D's debt ledger reported token totals
> `1339* (incomplete, 1 missing) / 2154 (complete) / 2060 (complete)` for three sessions.
> PR #42 supplies the committed E measurement report used for the current result above.

### NFR-003 — API call failure handling

| Field | Value |
|---|---|
| NFR | Behaviour when a model API call fails at the transport or HTTP layer. |
| Metric | Failure classification, surfaced error, and retry behaviour for transport/HTTP failures. |
| Threshold / fallback | `null` numeric threshold in main. C's fallback is no automatic retry for configuration, transport, HTTP-status or response-envelope failure; D currently makes at most one HTTP attempt per `extract` invocation and surfaces `LlmTransportError` after logging when the call log is writable. No record is persisted. |
| Input / data source | Offline transport/HTTP failure fixtures and `logs/llm_calls.jsonl`. |
| Measurement command / procedure | Inject configuration, transport, HTTP-status and response-envelope failures; check one call-log line per `extract` attempt when writable, at most one HTTP attempt per invocation, the surfaced `LlmTransportError`, and no persisted record. A call-log write failure follows RP-004 and must prevent use of the result. |
| Expected evidence files | Offline test output and failure log excerpts under `docs/measurements/`. |
| Owner | C (policy), D (implementation), E (verification). |
| Status | measured |
| Observed result | PR #42's [final NFR report](../measurements/final-nfr-verification.md) records five passing extract failure paths (missing config, timeout, HTTP 503, malformed envelope, invalid model JSON), plus the PR #38 hosted offline suite (237 passed). These are offline failure-path checks, not live gateway failure-rate measurements. |

### NFR-004 — Data security (secrets)

| Field | Value |
|---|---|
| NFR | No secrets committed to tracked repository files. |
| Metric | Count of committed secret occurrences. |
| Threshold | **0**, approved in main. |
| Threshold source and rationale | Main `docs/req/requirements.yaml` sets 0. One committed secret occurrence would violate the no-committed-secrets requirement, so the acceptable count is zero. This explains the recorded threshold; no scan result is inferred from it. |
| Input / data source | Tracked repository files; `.env` is gitignored. |
| Measurement command / procedure | Run a secret scan over tracked files and review findings. |
| Expected evidence files | Scan command, scope, findings and review result under `docs/measurements/`. |
| Owner | B (requirement), E (verification). |
| Status | measured |
| Observed result | PR #42's [final NFR report](../measurements/final-nfr-verification.md) records zero credential-pattern matches from `python .github/ci_checks.py secret-scan` over eligible tracked readable files, locally and in hosted CI. `.env` is ignored; `.env.example` is tracked. The scan does not cover committed history or every possible secret format. |

### NFR-005 — Input/output reliability

| Field | Value |
|---|---|
| NFR | Records accepted by the pipeline satisfy the deterministic invariants. |
| Metric | Rate of accepted records that later fail deterministic checks. |
| Threshold | `null` in main; no approved numeric rate. |
| Input / data source | Accepted records, negative/property test fixtures and architecture review. |
| Measurement command / procedure | Test valid and invalid inputs; recheck accepted records against the policy invariants and verify validation precedes state change. Include the direct-storage and caller-supplied-`spent` gaps documented below. |
| Expected evidence files | Offline test output and reviewed records under `docs/measurements/`. |
| Owner | B (requirement), C (policy), E (verification). |
| Status | measured |
| Observed result | PR #42's [final NFR report](../measurements/final-nfr-verification.md) records 0/16 accepted synthetic records failing independent deterministic re-validation (0% in this sample); all 16 were checked for amount, category, running total, cap and stored totals. |

### NFR-006 — Log traceability

| Field | Value |
|---|---|
| NFR | Model calls and policy rejections have corresponding log lines; Phase 2 additionally requires the applicable evidence pair to share `call_id`. |
| Metric | Percentage of model calls with an `llm_calls.jsonl` line and policy rejections with a `review.jsonl` line; separately, share of decisions whose applicable evidence pair joins on `call_id`. |
| Threshold / fallback | Numeric log-coverage threshold is `null` in main; no numeric target is asserted. D writes one call-log line per `extract` attempt and one review line per policy rejection when the respective log is writable. A failed evidence write stops the operation (RP-004 for call logging; `StorageError` for rejection evidence), never a successful unlogged decision. Phase 2 additionally requires matching `call_id` in each applicable pair. |
| Phase 2 evidence shape | Accepted → `llm_calls` + storage; rejected → `llm_calls` + review. A decision is not required to produce all three records. |
| Rejection invariant | A rejected decision must not create a normal storage record. |
| Input / data source | The logs produced by a measurement run: `logs/llm_calls.jsonl` plus `logs/review.jsonl`, and the stored records for accepted decisions. |
| Measurement command / procedure | Use an offline harness to count `extract` invocations (including pre-HTTP failures) against `llm_calls.jsonl` lines and policy rejections against `review.jsonl` lines; missing log lines cannot be detected by counting logs alone. Inject evidence-write failures separately and check fail-closed behavior. For accepted decisions join `llm_calls` to storage on `call_id`; for rejected decisions join `llm_calls` to review. Mismatched ids or both a normal record and review line for one decision violate the Phase 2 contract. |
| Expected evidence files | `docs/measurements/` report for NFR-006; the joined `logs/llm_calls.jsonl`, `logs/review.jsonl` and `data/records.jsonl` excerpts used for the check. |
| Owner | E (measurement), D (pipeline: `call_id` generation and carriage), C (contract). |
| Status | measured |
| Observed result | PR #42's [final NFR report](../measurements/final-nfr-verification.md) records 48/48 attempts with exactly one call row, 16/16 accepted ledger joins, and 32/32 rejected review joins by `call_id` and `request_id`; rejected IDs were absent from the ledger. |

> **Measurement scope.** These coverage figures are from the synthetic offline sample in
> PR #42. The behavioral criteria are one call line per attempt, applicable `call_id` joins,
> and fail-closed evidence writes; this sample does not claim to characterize every possible
> production run.

### NFR-007 — Testability

| Field | Value |
|---|---|
| NFR | Approved invariants have offline negative tests that fail when the guard is removed. |
| Metric | Fraction of approved invariants with such tests. |
| Threshold | **1.0** in main, with requirement status still `pending_confirmation`. |
| Threshold source and rationale | Main `docs/req/requirements.yaml` lists 1.0. For this fraction, 1.0 means every approved invariant has an offline negative test that fails when its guard is removed; any missing test lowers coverage. The requirement and threshold still await confirmation; the observed measurement is recorded separately below. |
| Input / data source | Approved invariant list and offline negative tests. |
| Measurement command / procedure | Map each approved invariant to a negative test and verify the test fails when its guard is removed. |
| Expected evidence files | Invariant-to-test mapping and run output under `docs/measurements/`. |
| Owner | E. |
| Status | measured |
| Observed result | PR #42's [final NFR report](../measurements/final-nfr-verification.md) records 3/3 guard-removal negatives (1.0): each control test passed and its corresponding guard-disabled mutant failed. The threshold's `pending_confirmation` status in B's requirements registry remains a separate approval question. |

### Additional proposal — Input parsing reliability (not a main NFR)

Fixture parse-match rate can be evaluated with fixed offline inputs and expected
`(amount, category)` records. Main has no registered NFR ID or approved numeric
threshold for this metric. A fixture report can be added if B registers it as a
separate requirement.

### C-side storage security review

> **HISTORICAL / UNMERGED — NOT CURRENT-BRANCH EVIDENCE.**
> This review describes **D's unmerged branch** (`src/storage.py`, `data/records.jsonl`,
> `call_id`). **`src/storage.py` does not exist on the current branch**
> (`feat/c-phase3-policy-60339160`, `src/`/`test/` byte-identical to `origin/main` `6997cef`).
> Nothing in this table is evidence from the current branch; it is retained for history and
> must not be read as a property the current code possesses. Where this table says "what the
> code shows", it means what D's unmerged branch showed, not this branch.

A C review of the storage boundary, separated into **what the code shows** and **what tests
have verified**. D has committed offline storage tests, but no committed test-run or
measurement output proves these checks passed in the reviewed branch. The evidence-join
tests are skipped, so the join remains unverified.

| Check | What the code shows (verified by reading `src/pipeline.py`, `src/storage.py`) | Verified by a run/test? |
|---|---|---|
| Validation before writing | `pipeline.process` calls `policy_core.validate_record(...)` **before** `storage.append_validated(record)`. Storage checks field names/basic types and duplicate `call_id`; it does **not** repeat the business invariants. Direct calls to `append_validated` can bypass `policy_core` and write a negative amount, an unknown category, or a total beyond the budget. | Code path only; D's storage tests cover shape/duplicate checks, not direct-call business-invariant bypass. |
| Rejected records are not persisted | On `PolicyError`, `process` attempts to write a rejection line to `logs/review.jsonl` and re-raises **before** any `append_validated` call. If that evidence write fails, D raises `StorageError` instead; it still does not persist the rejected record. | Code path only; evidence-join tests skipped. |
| Independent `StorageError` | A storage write failure raises `storage.StorageError`, distinct from `PolicyError`; it is not converted to a `policy:*` code. | Code only. |
| Other storage failures | Storage also raises `StorageError` on invalid record shape, duplicate `call_id`, unreadable/malformed persisted data, and a nonnumeric stored amount. `pipeline.process` can encounter read failures when `spent is None`, before business validation. | D has offline tests for several read/shape/duplicate cases; no committed test-run output. |
| Unhashable persisted `call_id` | `_existing_call_ids` adds stored IDs to a set without checking hashability. A JSON list as `call_id` raises uncaught `TypeError`, not RP-007's required `StorageError`. | Code review only; no failure-injection result recorded. |
| Nonserializable record value | `append_validated` does not validate `decided_at` as JSON-serializable. A direct call with a date/time object passes the structural checks, then `json.dumps` raises uncaught `TypeError`; only `OSError` is wrapped. | Code review only; no failure-injection result recorded. |
| Rejection-evidence write failure | `pipeline._append_rejection` raises `storage.StorageError` if it cannot write `logs/review.jsonl`, replacing the pending `PolicyError`; no normal data record is appended. Append-mode review writes have no demonstrated rollback of partial bytes. | No committed failure-injection result. |
| No partial state | **Required boundary; verification pending.** Append-mode write raises `StorageError` on `OSError`, but the code shows no rollback of bytes written before the error. Not demonstrated. | Not verified. |
| `call_id` linkage | The stored record and the rejection line both carry the same `call_id` as the `llm_calls` line; `request_id` is additionally present on the rejection line. | Code only; `test_evidence_join.py` skipped. |

- **Budget-bypass gap on `main` (addressed on D's unmerged branch).** The current `main`
  snapshot still trusts a caller-supplied `spent` when it is passed through the old
  storage boundary. D's `df729a9` implementation passes `spent` as `expected_spent` and
  rejects values below persisted cumulative spend, but that protection is not on `main`
  until the branch is merged.
- **Direct storage-call gap on `main` (addressed on D's unmerged branch).** The current
  `main` `append_validated(record)` boundary does not re-run C-INV-001/002/003. D's
  `append_validated(record, expected_spent=None)` re-runs those guards before writing,
  but the implementation is still branch-only and must not be treated as merged evidence.

---

## 3. Summary table

| NFR | Metric | Threshold | Owner | Status | Observed result |
|---|---|---|---|---|---|
| NFR-001 | model API round-trip latency, p50/p95/max ms | `null`; no approved budget | B / D / E | measured | 20 live gateway calls; p50 2422.222 ms, p95 2850.720 ms, max 3072.404 ms |
| NFR-002 | per-request/per-session token totals and logging statistics | `null`; descriptive statistics only | B / D / E | measured | 20/20 complete; 125/12/137 tokens per request; session total 2500/240/2740 |
| NFR-003 | transport/HTTP failure handling and retry behaviour | `null` numeric target; no automatic retry | C / D / E | measured | 5 failure paths passed; hosted offline suite: 237 passed |
| NFR-004 | committed secret occurrences | **0**, approved | B / E | measured | Zero credential-pattern matches in eligible tracked readable files, locally and in CI |
| NFR-005 | accepted records failing later deterministic checks | `null`; numeric rate pending | B / C / E | measured | 0/16 accepted synthetic records failed independent re-validation |
| NFR-006 | log-line coverage for model calls/rejections; Phase 2 `call_id` joins | `null` numeric target; one line per writable evidence path, fail closed on write failure | C / D / E | measured | 48/48 call rows; 16/16 accepted joins; 32/32 rejected joins |
| NFR-007 | fraction of approved invariants with guard-sensitive offline negative tests | **1.0**, requirement pending confirmation | E | measured | 3/3 guard-removal negatives (1.0); requirement confirmation remains separate |

---

## 4. Change protocol

- Adding an NFR means adding a full entry in §2 and a row in §3.
- Recording a result means filling `Status` → `measured` and `Observed result` with the
  actual value **and** the evidence file that holds the run. A result without an evidence
  file is not recorded.
- C defines the runtime fallback and threshold decision; B maintains the requirements
  registry. This logbook uses the registry's numeric NFR values and does not invent a
  number where main records `null`. The behavioral fallback is stated separately from
  any numeric target and from E's observed result.
  - **Threshold sources.** The current main `docs/req/requirements.yaml` is the
    source for the NFR IDs, metrics and threshold fields. It gives **0** for NFR-004
    (approved) and **1.0** for NFR-007 (still pending confirmation). NFR-001/002/003/005/006
    have `null` thresholds. `docs/code-governance/structural-constraints.md` states no
    numeric threshold, so no value is attributed to it.
- NFR-002's logging-metadata aggregates (`session_id`, `request_id`, `request_made`,
  `usage_source`, missing-usage counts) are computed from the same `llm_calls` records;
  `gateway` usage is never treated as zero when usage is `missing`. The token aggregates are
  descriptive statistics only and do not receive a pass/fail threshold.

---

## 5. Phase 3 C audit and evidence

> Scope: `feat/c-phase3-policy-60339160`. On this branch `src/` and `test/` are
> **byte-identical to `origin/main`** (`6997cef`): `git diff origin/main -- src test` is
> empty and the `git ls-tree` blob hashes match. There is **no `src/storage.py`**, no
> `call_id` / `request_id` / `session_id`, no `tokens` / `usage_source` / `request_made` on
> this branch. The evidence below is what a reader can re-check on this branch; it is
> **not** a measurement of NFR-001/002/005/006 on this historical C snapshot. Their later
> merged-main measurements are recorded in §2, §3 and §6.3.

### 5.1 How this evidence was produced

- **Static inspection** (`rg`, `git ls-tree`, `git diff origin/main -- src test`, `ast` import
  scan) of `src/call_llm.py`, `src/policy_core.py`, `src/pipeline.py`, `test/offline/*.py`.
- **One offline test run:** `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test/offline -q`
  at commit `4624bb7` → **41 passed, 1 warning** (`urllib3 v2 only supports OpenSSL 1.1.1+`
  `NotOpenSSLWarning`), interpreter `Python 3.9.6` (`/usr/bin/python3`). A 41-test smoke pass
  is **not** proof of fail-closed logging, `call_id` joins, storage atomicity, or no-bypass.

### 5.2 Evidence table (description / policy → code path → test → command → result → status)

| Item | Code path | Test(s) | Command | Result | Status |
|---|---|---|---|---|---|
| Deterministic policy-core authority | `src/policy_core.py:91` `validate_record` → `enforce_amount/category/budget` | `test_validate_record_stops_at_first_failure`, `test_validate_record_rejects_non_dict`, `test_validate_record_returns_normalised_record` | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test/offline -q` | pass (within 41) | code + test observed |
| Rejection routing `review` flag | `src/policy_core.py:40-69,84-87` | `test_inv002_rejects_out_of_vocabulary` (`review is True`), `test_inv001_rejects_invalid_amount` (`review is False`) | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test/offline -q` | pass | code + test observed |
| Fail-closed call log | `src/call_llm.py:45-52` `_append_log` raises `LlmTransportError` on `OSError` | **none** (`# pragma: no cover`) | — | not exercised | **gap** (matches trace-matrix ERR-004) |
| Logging field-schema (four fields on all paths) | `src/call_llm.py:124,140-145,156` | **none** | — | success omits `error`; config/transport omit `raw`,`parsed` | **D gap** (see 5.3 #1) |
| Default-deny permissions | `.opencode/permissions.jsonc` `"*":"deny"` | n/a (config) | read + diff vs `permission-model.md` | **consistent, no mismatch found** | reviewed |
| Model-call boundary (only `call_llm` imports `requests`) | `src/call_llm.py:13`; `rg` shows no other `requests`/`urllib`/`httpx` in `src/` | `test_policy_core_has_no_io_imports` | `rg` + `pytest` | pass | code + test observed |
| `call_id` / `request_id` / `session_id` | absent on this branch | — | `git ls-tree`, `rg` | absent | doc-only/unmerged |
| Rejection evidence line | `src/pipeline.py:21-31,58-65` `_append_review`; fields `{error, amount, category, spent, total, review}` | `test_policy_rejection_writes_one_review_line` (3 params) | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test/offline -q` | pass; exact key set asserted (no `call_id`) | code + test observed |
| Review-write failure classification | `src/pipeline.py:27-31` raises `PolicyError(code="policy:budget")` on `OSError` | **none** | — | misclassified | **D gap** (see 5.3 #2) |
| Storage boundary (RP-007) | no `src/storage.py` | none on branch | `git ls-tree origin/main` | absent | pending D |
| Rejected records not persisted | on this branch there is no storage write at all; rejection re-raises after the review line | inferred from `src/pipeline.py:49-66` (no storage call) | — | code path shows no persistence | code only (trivially holds: no storage) |
| Secret scanning (NFR-004) | tracked files | — | `git grep -E 'sk-[A-Za-z0-9]{16,}|Bearer [A-Za-z0-9]{20,}…'` this pass | no match | partial scan, not a full tooled scan |

### 5.3 Remaining evidence gaps (must not be read as satisfied)

1. **Logging field-schema (RP-004 / FR-008).** The success path (`extract` at
   `src/call_llm.py:156`) omits `error`; the config-failure path (`:124`) and the
   transport/HTTP/protocol path (`:140-145`) omit `raw` and `parsed`. The contract requires
   all four fields (`input`, `raw`, `parsed`, `error`); the current code does not meet it on
   every path. D-dependent implementation gap.
2. **Review-write error classification.** `pipeline._append_review`
   (`src/pipeline.py:27-31`) collapses an `OSError` into
   `PolicyError(code="policy:budget", review=True)`. An infrastructure/evidence-write
   failure must be independent of `policy:*`. D-dependent defect.
3. **Fail-closed logging not tested.** No test triggers the `_append_log` `OSError` branch;
   "if it cannot be logged, the result is not used" is code-reviewed, not verified by a test.
4. **Complete no-bypass proof.** Only code review + `test_policy_core_has_no_io_imports`
   support the scoped rule "no model output may affect normal business data or storage before
   passing through `policy_core`; audit logging of raw model output occurs before policy
   validation by design". No end-to-end test proves that no other caller can consume `extract`
   output or write it without `validate_record` (there is no storage on this branch to test
   against).
5. **`call_id` evidence joins.** Absent on this branch (`doc-only/unmerged`); the
   `test_evidence_join.py` referenced in Phase 2 is not present here and would be skipped on
   D's branch. Not verified anywhere on this branch.
6. **Storage atomicity / no partial state / direct-call protection / `spent` source of truth.**
   Entirely `pending D` — no `src/storage.py` to review or test.
7. **Secret scan.** Only an ad-hoc `git grep` pattern scan was run this session; no dedicated
   secret-scanning tool/result is recorded, so NFR-004 stays `pending`.
8. **Review of `(call_id)` joins on unmerged branch.** Not verified; see #5.

### 5.4 Historical permission consistency check

In this earlier C snapshot, `permission-model.md` and `.opencode/permissions.jsonc` were
compared and found consistent under the rules then documented. That check predates the
runtime-ledger deny for `data/records.jsonl*`; it does not describe the current configuration.
The post-merge permission review and correction are recorded in §6.1 and §6.3. No config
edit was made during the historical check.

### 5.5 Historical NFR status at this audit

At the time of this branch-only audit, NFR-001/002/003/005/006 were `pending` for lack of
independent measurement on this branch; NFR-004 had no tooled scan; and the NFR-007
guard-removal mapping had not been run here. This is a historical status snapshot. Current
merged-main measurements are recorded in §2, §3 and §6.3.

## 6. Post-merge C security audit — `main@06ec2f5`

> **Audit baseline.** PR [#38](https://github.com/Felix-Free/AI-Finance-Assistant/pull/38)
> was merged by C into `main` as `06ec2f5` on 2026-11-22. This section supersedes the
> pre-merge status statements in §5 for the current mainline. The C branch used to edit this
> logbook still has the older source snapshot; the evidence below is based on review of the
> merged PR/source and its recorded checks, not a local test run on this C checkout.

### 6.1 Evidence and verification source

| Evidence | Source / command | Observed result | Scope / limit |
|---|---|---|---|
| Final offline regression | D's PR report: `python -m pytest test/offline -q` on the implementation head | **237 passed** | Reported in PR #38; not rerun in this stale C checkout. |
| Merge-head CI | GitHub checks attached to merge commit `06ec2f5` | **8 checks passed** | Proves these checks ran successfully; does not prove branch protection requires them. |
| E regression additions | `test/offline/test_evidence_join.py`, `test/offline/test_pipeline_seam.py`; existing storage/invariant regression selection | Included in the reported 237-pass offline suite | Test pass is not a measured NFR result and does not prove every property by itself. |
| Code path review | `src/call_llm.py`, `src/pipeline.py`, `src/policy_core.py`, `src/storage.py` at the PR #38 merge head | Findings in §6.2 | Static review of the merged implementation; no independent clean checkout was available in this C worktree. |
| Permission alignment | `docs/architecture/permission-model.md` compared with `.opencode/permissions.jsonc` and the merged storage path | The initial comparison found the ledger deny missing. After explicit human authorization, both `read` and `edit` now deny `data/records.jsonl*`; the broader `data/**` measurement allow remains. JSONC structure and both rule entries were checked. | **Configuration and document are aligned.** The OpenCode runtime matcher was not independently exercised, so effective enforcement is not claimed from syntax inspection alone. |

### 6.2 Final policy and security evidence

| Invariant / policy | Final code path and test evidence | Audit result |
|---|---|---|
| Model-output authority / no normal-data bypass | `call_llm.extract()` is the model client; `pipeline.process()` removes `__call_id__`, calls `policy_core.validate_record()`, and passes only its normalized business record onward. The pipeline storage path and direct storage path both call `policy_core` guards; storage does not make an independent business-rule decision. | **No bypass found in the reviewed production paths.** Raw model-output audit logging occurs before policy validation by design; it is redacted and is not normal business data. |
| A′ log privacy | Call logs store `input`/available `raw` as `redacted:len=<n>` using character count; `parsed` is null. Review fields `amount/category/spent/total` are null. IDs and safe codes remain. The normal ledger retains validated values. E added success, rejection, config, transport, HTTP, protocol and fault cases. | **Implemented and regression-tested** in PR #38. |
| Pipeline budget authority | The pipeline uses persisted spend for pre-validation; storage rereads the persisted total under the file lock and recomputes the canonical total before the atomic ledger replace. A stale caller `spent` does not determine pipeline decisions. | **Implemented and regression-tested.** Concurrent over-budget requests produce `PolicyError(policy:budget, review=True)` and do not append a ledger row; equality is accepted. |
| Direct storage semantics | Public `append_validated` retains direct-call `expected_spent < persisted` → `StorageError`; direct policy violations remain `PolicyError`; direct calls do not add review evidence. | **Preserved and covered by existing regression tests.** |
| Rejection evidence / fail-closed | Pipeline policy rejection attempts one redacted review line. Review-write failure raises `StorageError`; the rejected record is not appended. Call-log write failure prevents `extract()` from returning a usable result. | **Implemented and failure-tested.** Review-log append itself is not atomic; see §6.3. |
| Ledger atomicity / locking | Storage holds the OS file lock over read, duplicate check, budget enforcement, and write/replace; it writes through a unique same-directory temporary file, flushes/fsyncs, then `os.replace`s. The E fault test targets `mkstemp` and checks prior ledger bytes remain unchanged. | **Implemented and fault-tested** for the tested write failure. This evidence does not cover every possible filesystem/crash mode. |
| Safe error messages and evidence | I/O `StorageError` and review-write messages use fixed safe wording; logged failures use allowlisted error codes. Exception causes remain chained internally; C's accepted contract covers the public message and persisted evidence/log, not the internal `__cause__`. | **Meets the confirmed C wording** for messages and logs. A malformed direct-storage record with an arbitrary unknown field name can still have that field name echoed in a shape-error message; this is a low-risk, non-pipeline edge case accepted for this merge, not a universal guarantee for arbitrary direct callers. |

### 6.3 Remaining limits and NFR status

- `logs/review.jsonl` still uses append mode. A write that fails midway could leave a partial
  evidence line; the PR discloses this and does not claim atomic review writes. It does not
  affect the atomic commit point for `data/records.jsonl`.
- `_PIPELINE_ORIGIN` is an internal routing marker, not a hard privilege boundary. It does
  not bypass `policy_core`; code in the same Python process that deliberately imports the
  private marker can select the internal path.
- The hosted checks passed, but branch protection's required-check configuration and a
  deliberately blocked bad-merge scenario were not verified.
- NFR-001/002/003/004/005/006/007 have measured results recorded in PR #42's
  [final NFR report](../measurements/final-nfr-verification.md) and summarized in §2 and §3.
  NFR-001/002/005/006 have no approved numeric threshold; NFR-007's 1.0 threshold remains
  `pending_confirmation` in B's registry. These are measurement states, not blanket
  requirement approvals or claims beyond the reported samples.
- C confirmed the final eight-category whitelist in `invariants.md` on 2026-11-22; E's
  per-member category regression is included in the reported passing suite. The B-owned
  requirements registry still shows PD-002 as `pending_confirmation` and needs its owner to
  synchronize that status.
- **Permission configuration gap closed:** `.opencode/permissions.jsonc` grants `read` and
  `edit` to `data/**`, and now also denies `data/records.jsonl*` for both actions. This covers
  the runtime ledger, its lock sidecar, and same-prefix temporary files. The permission model
  and machine config agree; OpenCode's runtime matcher behavior was not independently tested.
- `AGENTS.md`, `docs/req/requirements.yaml`, and other B-owned wording are not changed here;
  any remaining broad “before any state change/write” language must be reconciled by those
  owners.

> **Conclusion.** PR #38 closes the previously pending D implementation and E regression
> items for A′ redaction, locked budget authority, atomic ledger append, and safe public
> I/O messages. The ledger permission mismatch is now corrected in both the permission model
> and machine config. NFR-001 through NFR-007 now each have measured evidence recorded; these
> measurements are limited to the samples and scan scope stated in §2 and the linked report.
> Remaining limits include unverified branch-protection
> enforcement, non-atomic review-log append, untested OpenCode runtime matcher behavior, and
> the documented direct-call error-message edge case.
