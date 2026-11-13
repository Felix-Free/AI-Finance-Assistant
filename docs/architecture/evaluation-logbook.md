# Evaluation Logbook (owner: roles C and E)

> Purpose: the running record of **non-functional requirements (NFRs)** for the finance
> assistant — what is measured, against which threshold, from which input, by which
> procedure, with which evidence, and what was actually observed. This logbook is where an
> NFR moves from "pending" to a measured result; a threshold without an observed result is
> marked **pending**, never assumed to pass.
>
> Status: **Phase 2 documentation (transcript 60339160).** Main supplies the NFR
> registry and threshold fields; C records the policy and evidence contract, E runs the
> measurement, and D implements the pipeline. No measurement result is recorded here
> until it has actually been run.

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
| Input / data source | Live gateway samples in `logs/latency.jsonl`, produced by `src/measure_latency.py` with a fixed probe sentence. |
| Measurement command / procedure | `python -m src.measure_latency`; report p50/p95 for successful samples with `(n=ok)` and max separately. Transport and model-content JSON errors are counted as failures. Other errors, including failure to append a successful sample, may stop the run. |
| Expected evidence files | `logs/latency.jsonl` and a run report under `docs/measurements/`. |
| Owner | B (requirement), D (script), E (measurement). |
| Status | pending |
| Observed result | Not measured. |

> **Reported by D; not verified by committed run evidence.** D's debt ledger reports
> `n=20: p50 2356.7 ms / p95 4759.5 ms / max 5771.2 ms`. This does not count as a
> measured result here. D's latency script header calls this "NFR-002"; that script label
> conflicts with the main registry and needs correction by its owner.

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
| D's current report implementation (verified) | `src/report_tokens.py` produces: **per-call rows** (columns include `call_id`, `request_id`, `session_id`, `input`, `output`, `total`), **per-session aggregation** grouped by `session_id`, and **global counters** (`total_api_calls`, `usage_complete_calls`, `usage_missing_calls`, `usage_partial_calls`, `not_called_calls`). It does **not** implement per-request aggregation — `request_id` appears only as a per-call column, not as a grouping aggregate. So requirement (b) is **C-required but not yet implemented in `report_tokens`**. |
| Expected evidence files | `docs/measurements/` report for NFR-002 and the `llm_calls` excerpts used for the aggregation and consistency checks. |
| Owner | B (definition), E (measurement), D (logging fields and report). |
| Status | pending |
| Observed result | Not measured. |

> **Reported by D; not verified by committed run evidence.** D's debt ledger reports token
> totals `1339* (incomplete, 1 missing) / 2154 (complete) / 2060 (complete)` for three
> sessions. No committed `docs/measurements/` output or log evidence exists in the
> repository (`logs/` and `data/` are gitignored), so these are **not** recorded as a
> measured result and the status stays `pending`.

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
| Status | pending |
| Observed result | Not measured; the no-automatic-retry fallback is documented from D's code, not verified by an E run. |

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
| Status | pending |
| Observed result | No scan result recorded here. |

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
| Status | pending |
| Observed result | Not measured; storage boundary gaps remain open. |

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
| Status | pending |
| Observed result | Not measured. The call-id and logging pipeline is available; E still needs to run the measurement. |

> **Why NFR-006 is pending.** The main registry has no numeric coverage target. The
> evidence-join tests in `test/offline/test_evidence_join.py` are all `pytest.skip(...)`;
> neither log coverage nor the Phase 2 join has a recorded measurement here.

### NFR-007 — Testability

| Field | Value |
|---|---|
| NFR | Approved invariants have offline negative tests that fail when the guard is removed. |
| Metric | Fraction of approved invariants with such tests. |
| Threshold | **1.0** in main, with requirement status still `pending_confirmation`. |
| Threshold source and rationale | Main `docs/req/requirements.yaml` lists 1.0. For this fraction, 1.0 means every approved invariant has an offline negative test that fails when its guard is removed; any missing test lowers coverage. The requirement and threshold still await confirmation, and this is not a measured result. |
| Input / data source | Approved invariant list and offline negative tests. |
| Measurement command / procedure | Map each approved invariant to a negative test and verify the test fails when its guard is removed. |
| Expected evidence files | Invariant-to-test mapping and run output under `docs/measurements/`. |
| Owner | E. |
| Status | pending |
| Observed result | Not measured; `test_evidence_join.py` remains skipped. |

### Additional proposal — Input parsing reliability (not a main NFR)

Fixture parse-match rate can be evaluated with fixed offline inputs and expected
`(amount, category)` records. Main has no registered NFR ID or approved numeric
threshold for this metric. A fixture report can be added if B registers it as a
separate requirement.

### C-side storage security review

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

- **Budget-bypass gap (not secured).** `pipeline.process(spent=...)` trusts a caller-supplied
  `spent` and reads the persisted total only when `spent is None`; `append_validated` does not
  compare against persisted cumulative spend. A lower caller-supplied `spent` can weaken the
  cumulative budget check. See `runtime-policy-catalog.md §5.5` for the approved-but-unimplemented
  `expected_spent` boundary.
- **Direct storage-call gap (not secured).** The `append_validated(record)` name and its
  structural recheck do not guarantee the record passed `policy_core`. Calling it directly
  with correctly typed but policy-invalid values can bypass C-INV-001/002/003. C requires
  all production writes to follow `pipeline.process` until D enforces this boundary in code.

---

## 3. Summary table

| NFR | Metric | Threshold | Owner | Status | Observed result |
|---|---|---|---|---|---|
| NFR-001 | model API round-trip latency, p50/p95/max ms | `null`; no approved budget | B / D / E | pending | not measured |
| NFR-002 | per-request/per-session token totals and logging statistics (per-request aggregate absent from D's report) | `null`; descriptive statistics only | B / D / E | pending | not measured |
| NFR-003 | transport/HTTP failure handling and retry behaviour | `null` numeric target; no automatic retry | C / D / E | pending | not measured |
| NFR-004 | committed secret occurrences | **0**, approved | B / E | pending | no scan recorded |
| NFR-005 | accepted records failing later deterministic checks | `null`; numeric rate pending | B / C / E | pending | not measured |
| NFR-006 | log-line coverage for model calls/rejections; Phase 2 `call_id` joins | `null` numeric target; one line per writable evidence path, fail closed on write failure | C / D / E | pending | not measured |
| NFR-007 | fraction of approved invariants with guard-sensitive offline negative tests | **1.0**, requirement pending confirmation | E | pending | not measured |

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
