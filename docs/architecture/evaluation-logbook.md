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
| Metric | Share of fixture inputs whose parsed `(amount, category)` equals the expected record. |
| Threshold | Defined by the requirements source; recorded here once confirmed. Until then the threshold is **not** asserted. |
| Input / data source | Fixed offline fixture set under `data/` (deterministic inputs with expected outputs); no network. |
| Measurement command / procedure | Run the offline extraction over the fixtures and tally matches against expected records. Exact command is fixed when the harness lands; until then: procedure only. |
| Expected evidence files | `docs/measurements/` report for NFR-001; the fixture file under `data/`. |
| Owner | E (measurement), D (pipeline). |
| Status | pending |
| Observed result | Not measured. |

### NFR-002 — Token Usage statistics

| Field | Value |
|---|---|
| NFR | Token usage per request and per session. |
| Metric | Per-request aggregation, per-session aggregation, actual API-call count, usage-source distribution, missing-usage count, and `usage_source`↔`tokens` consistency. |
| Threshold | No approved numeric pass/fail threshold. Per-request, per-session, actual API-call count, usage-source distribution and missing-usage count are reported as statistics only. The consistency rule is checked structurally: `usage_source` must agree with `tokens`; it has no separately approved numeric threshold. |
| Input / data source | `logs/llm_calls.jsonl` records produced by the measurement run, including `session_id`, `request_id`, `call_id`, `tokens`, `usage_source` and `request_made`. |
| Measurement command / procedure | Over the produced `llm_calls` records, compute: (a) **per-session aggregation** grouped by `session_id`; (b) **per-request aggregation** grouped by `request_id` (one request may span multiple calls); (c) **`api_call_count`** = number of rows with `request_made: true` (the actual API-call count); no separate user-request-count metric is required; (d) the **usage-source distribution** over rows that participated in a request (`request_made: true`) across the three stored `usage_source` values `gateway`, `partial`, `missing`; (e) **missing-usage count** = `request_made: true` rows with `usage_source: missing`. Rows with `request_made: false` are counted separately as **`not_called_calls`** and are **excluded** from the usage-source distribution and the missing-usage count; `not_called` is a derived operational category, not a fourth `usage_source` enum value. Token classification: three integers → `gateway`; at least one integer and at least one `null` → `partial`; all `null` → `missing`; non-integer values normalize to `null`. Check that `usage_source` agrees with `tokens`, that missing usage is never replaced with `0` or an estimate, and that `tokens` is always an object with `input`, `output` and `total` (missing values `null`). All values are reported only; no pass/fail judgment is made. |
| Expected evidence files | `docs/measurements/` report for NFR-002 and the `llm_calls` excerpts used for the aggregation and consistency checks. |
| Owner | B (definition), E (measurement), D (logging fields). |
| Status | pending |
| Observed result | Not measured. |

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

> **Why NFR-006 is pending.** D's implementation now emits the call-id and the applicable
> evidence records. The procedure has not yet been run by E, so no observed result is claimed.

---

## 3. Summary table

| NFR | Metric | Threshold | Owner | Status | Observed result |
|---|---|---|---|---|---|
| NFR-001 | fixture parse-match rate | as per requirements (not asserted yet) | E / D | pending | not measured |
| NFR-002 | per-request/per-session token aggregation, `api_call_count`, usage-source/missing-usage counts, and `usage_source`↔`tokens` consistency | statistics only; no approved numeric pass/fail threshold | B / E / D | pending | not measured |
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
- NFR-002's logging-metadata aggregates (`session_id`, `request_id`, `request_made`,
  `usage_source`, missing-usage counts) are computed from the same `llm_calls` records;
  `gateway` usage is never treated as zero when usage is `missing`. The token aggregates are
  descriptive statistics only and do not receive a pass/fail threshold.
