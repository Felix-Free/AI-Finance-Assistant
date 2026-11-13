# Evaluation Logbook (owner: roles C and E)

> Purpose: the running record of **non-functional requirements (NFRs)** for the finance
> assistant — what is measured, against which threshold, from which input, by which
> procedure, with which evidence, and what was actually observed. This logbook is where an
> NFR moves from "pending" to a measured result; a threshold without an observed result is
> marked **pending**, never assumed to pass.
>
> Status: **Phase 2 documentation (transcript 60339160).** C defines the metric,
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
| Canonical requirement ID | **Unconfirmed — pending confirmation.** The repository has no requirements file that maps this behaviour to a canonical `REQ-NFR-###`. D's measurement scripts label **latency** and **token usage** as "NFR-002"; that is not evidence for renumbering input parsing. This entry keeps the working label `NFR-001` until role B confirms the canonical id. |
| Metric | Share of fixture inputs whose parsed `(amount, category)` equals the expected record. |
| Threshold | Defined by the requirements source; recorded here once confirmed. Until then the threshold is **not** asserted. No numeric threshold is stated in the repository, so no value is attributed to it. |
| Input / data source | Fixed offline fixture set under `data/` (deterministic inputs with expected outputs); no network. |
| Measurement command / procedure | Run the offline extraction over the fixtures and tally matches against expected records. Exact command is fixed when the harness lands; until then: procedure only. |
| Expected evidence files | `docs/measurements/` report for input parsing; the fixture file under `data/`. |
| Owner | E (measurement), D (pipeline). |
| Status | pending |
| Observed result | Not measured. |

### NFR-002 — Token Usage statistics

| Field | Value |
|---|---|
| NFR | Token usage per request and per session. |
| Metric | Per-request aggregation, per-session aggregation, attempted API-call count, usage-source distribution, missing-usage count, and `usage_source`↔`tokens` consistency. |
| Session grouping | D generates `session_id` once when `src/call_llm.py` is loaded and shares it across calls in that process. A `session_id` group therefore represents a process run, not necessarily one user's session if the process serves multiple users. |
| Threshold | No approved numeric pass/fail threshold. Per-request, per-session, attempted API-call count, usage-source distribution and missing-usage count are reported as statistics only. The consistency rule is checked structurally: `usage_source` must agree with `tokens`; it has no separately approved numeric threshold. No numeric threshold is stated in the repository. |
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

### Latency — model-call wall-clock time (requirement ID unconfirmed)

| Field | Value |
|---|---|
| NFR | Wall-clock latency of actual LLM calls. |
| Canonical requirement ID | **Unconfirmed.** D's `src/measure_latency.py` labels this "NFR-002", the same label its token script uses; the repository maps no canonical `REQ-NFR-###` to latency. This entry deliberately does **not** claim NFR-001 or NFR-002; the id awaits role B's confirmation. |
| Metric | `attempted`, `ok`, `failed`, `failure_rate`; `p50` and `p95` in ms each printed with `(n=ok)`, plus `max_ms` without an inline sample count. All three use the `ok` successful samples. |
| Threshold | No numeric latency threshold is stated in the repository. A pass/fail threshold is **pending confirmation**; none is invented. |
| Input / data source | `logs/latency.jsonl` samples produced by `src/measure_latency.py`, measured against a fixed probe sentence (`"hotpot last night cost 350"`). Successful attempts only feed the percentiles. |
| Measurement command / procedure | `python -m src.measure_latency` (module invocation; see the manifest EP-005). Attempts `n` real calls; `LlmTransportError` and model-content `JSONDecodeError` are counted without ending the run. Other failures, including inability to append a successful sample to `logs/latency.jsonl`, are not caught and can stop it early. Successful samples produce nearest-rank p50/p95 with `(n=ok)`; `max_ms` is printed separately. |
| Expected evidence files | `logs/latency.jsonl` (gitignored, runtime); any `docs/measurements/` latency report, if produced. |
| Owner | C (contract), D (measurement script), E (run/verification). |
| Status | pending |
| Observed result | Not measured. |

> **Reported by D; not verified by committed run evidence.** D's debt ledger reports
> `n=20: p50 2356.7 ms / p95 4759.5 ms / max 5771.2 ms`. No committed latency evidence
> exists in the repository, so this is **not** recorded as a measured result.

### NFR-006 — Evidence join by `call_id`

| Field | Value |
|---|---|
| NFR | Evidence records belonging to one decision carry the same `call_id` (see the `Evidence linkage by call_id` section in `runtime-policy-catalog.md`). |
| Metric | Share of decisions whose path-specific evidence records carry the same `call_id`. |
| Threshold | Accepted decision: `llm_calls.call_id` equals the accepted record's `data/records.jsonl` `call_id`. Rejected decision: `llm_calls.call_id` equals the rejection's `logs/review.jsonl` `call_id`. A decision is not required to produce all three records. |
| Threshold mapping | Confirmed as two possible evidence shapes: accepted → `llm_calls` + storage; rejected → `llm_calls` + review. The three possible evidence locations are the two logs plus `data/records.jsonl`; the applicable pair depends on the decision outcome. |
| Conditional evidence shape | The path-specific rule is also the evidence shape. Accepted decision → `llm_calls` + normal storage evidence. Rejected decision → `llm_calls` + review evidence. A rejected decision must not create a normal storage record. |
| Input / data source | The logs produced by a measurement run: `logs/llm_calls.jsonl` plus `logs/review.jsonl`, and the stored records for accepted decisions. |
| Measurement command / procedure | For each accepted decision, join `logs/llm_calls.jsonl` to `data/records.jsonl` and compare `call_id`. For each rejected decision, join `logs/llm_calls.jsonl` to `logs/review.jsonl` and compare `call_id`. Any decision with a storage record *and* a review line, or with mismatched ids, is a failure. |
| Expected evidence files | `docs/measurements/` report for NFR-006; the joined `logs/llm_calls.jsonl`, `logs/review.jsonl` and `data/records.jsonl` excerpts used for the check. |
| Owner | E (measurement), D (pipeline: `call_id` generation and carriage), C (contract). |
| Status | pending |
| Observed result | Not measured. The call-id and logging pipeline is available; E still needs to run the measurement. |

> **Why NFR-006 is pending.** The evidence-join tests in `test/offline/test_evidence_join.py`
> are currently all `pytest.skip(...)` (a skeleton for role E to fill in), so the join has
> **not been verified by tests**, and the procedure has not been run by E. No observed
> result is claimed.

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
| NFR-001 (canonical id unconfirmed) | fixture parse-match rate | not asserted; no numeric threshold in repo | E / D | pending | not measured |
| NFR-002 | per-session/per-request token aggregation, `api_call_count`, usage-source/missing-usage counts, `usage_source`↔`tokens` consistency (per-request not yet in `report_tokens`) | statistics only; no numeric threshold in repo | B / E / D | pending | not measured |
| Latency (requirement id unconfirmed) | attempted/ok/failed/failure_rate, p50/p95/max ms | not asserted; no numeric threshold in repo | C / D / E | pending | not measured |
| NFR-006 | decisions whose applicable evidence pair shares one `call_id` | accepted: `llm_calls`↔storage; rejected: `llm_calls`↔review | E / D / C | pending | not measured |

---

## 4. Change protocol

- Adding an NFR means adding a full entry in §2 and a row in §3.
- Recording a result means filling `Status` → `measured` and `Observed result` with the
  actual value **and** the evidence file that holds the run. A result without an evidence
  file is not recorded.
- Thresholds are owned by role B's requirements; C records them here from the requirements
  source and does not invent them. If the requirements source does not state a threshold,
  the cell says so rather than guessing.
  - **Threshold sources.** `docs/code-governance/structural-constraints.md` allocates
    threshold decisions to role C but states **no numeric threshold**; it is therefore not
    cited as the source of any value here. No numeric threshold for input parsing, token
    usage, latency or evidence join appears in a committed requirements file, so each is
    marked **pending confirmation** rather than assigned a number.
- NFR-002's logging-metadata aggregates (`session_id`, `request_id`, `request_made`,
  `usage_source`, missing-usage counts) are computed from the same `llm_calls` records;
  `gateway` usage is never treated as zero when usage is `missing`. The token aggregates are
  descriptive statistics only and do not receive a pass/fail threshold.
