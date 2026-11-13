# Runtime Policy Catalog (owner: role C)

> Purpose: the deterministic runtime policies that govern *how* the application degrades
> when something goes wrong — a bad model response, a transport failure, a rejected
> record, or an unwritable log. Distinct from `invariants.md`, which defines the business
> rules that must never be violated.
>
> Status: **Phase 1 · C-Security (transcript 60339160); extended in Phase 2 (§5).**
> Role C defines the trigger, action and degradation; role D implements; role E verifies.
> Phase 1 policy ids RP-001..RP-006 are retained. Phase 2 clarifies RP-001/002 against
> D's implemented failure classification and adds **RP-007 (storage boundary failure)**
> plus the `call_id`, token, storage-failure and NFR-006 evidence contracts.

---

## 1. Action vocabulary

| Action | Meaning |
|---|---|
| `accept` | record passes all invariants; may affect stored data |
| `reject` | record is discarded; stored data unchanged |
| `REVIEW` | record is rejected but flagged for human inspection (never auto-applied) |
| `retry` | the call may be repeated, bounded; never on an invariant violation |
| `quarantine` | record is set aside for audit but cannot be used to change state |

A rejected record must never partially affect state: validation happens **before** any
write (`structural-constraints.md §4`).

---

## 2. Policies

### RP-001 — Model returns invalid JSON

- **Trigger:** the model's content cannot be parsed by `json.loads` (invalid JSON syntax).
- **Action:** surface `JSONDecodeError`; do not retry.
- **Degradation:** log `error="not_json"` with the raw text; do not use the result.
  `call_llm.py` re-raises the `JSONDecodeError`.
- **Evidence:** one `logs/llm_calls.jsonl` line: `input`, `raw`, `parsed=null`, `error`.

> **Valid JSON that is not an object (current D behavior).** A JSON array, string or
> number parses successfully, so it does **not** trigger RP-001 or `not_json`.
> `call_llm.extract` logs the parsed value with `error=null` and returns it without
> `__call_id__`. In the normal `pipeline.process` path, the missing id raises
> `StorageError("missing call_id from model client")` before `policy_core` runs; no
> policy review line or stored record is produced. Calling `policy_core.validate_record`
> directly with a non-object instead raises `PolicyError(code="policy:amount")`.
> This difference in failure classification is an **unresolved D implementation gap**;
> `StorageError` here does not mean a storage write was attempted.

### RP-002 — Model-client configuration / transport / response-protocol failure

- **Trigger:** missing base URL or API key before HTTP; network error, timeout, auth
  failure, non-200 status, or an HTTP 200 response
  whose envelope is not valid JSON, lacks the expected `choices[0].message.content`, or
  has a non-string `content`.
- **Action:** surface `LlmTransportError`; do not persist anything.
- **Retry:** no automatic retry for configuration, transport, HTTP-status or response-envelope
  failure. D's `extract` makes at most one HTTP attempt per invocation and propagates the
  failure after writing its call log when that log is writable.
- **Degradation:** distinct from a policy rejection so tests can tell "correctly refused"
  from "crashed" (`structural-constraints.md §4`). A protocol error concerns the HTTP
  response envelope; invalid JSON inside a valid string `content` follows RP-001 instead.
- **Evidence:** one `logs/llm_calls.jsonl` line. For missing configuration, `error` is
  `config: missing base url or key` and `request_made` is `false`. For HTTP-attempt failures,
  `error` begins `transport:`, `http <code>` or `protocol:` and `request_made` is `true`.
  In both cases `raw`, `parsed` and `tokens` are `null`. D-02 (§5) tracks the unresolved
  risk that some error text includes raw exception or response details.

### RP-003 — Invariant violation

- **Trigger:** any of `C-INV-001`, `C-INV-002`, `C-INV-003` fails.
- **Action:** `reject`; raise `PolicyError`.
- **Degradation:** stored data and running totals stay unchanged; the record is not
  applied. `C-INV-002` and `C-INV-003` additionally flag `REVIEW`.
- **Evidence:** log `error="policy:<subject>"` with the offending field and value in `logs/review.jsonl`, carrying the relevant `call_id` (the evidence-join key) and its `request_id` (user-request grouping) so the line joins to its `llm_calls` record.

### RP-004 — Logging integrity (fail-closed)

- **Trigger:** the per-call audit line cannot be written, or a call would produce zero or
  more than one line, or the four required fields (`input`, `raw`, `parsed`, `error`)
  are renamed/dropped.
- **Action:** the result of that call **must not be used**. Effectively `reject`.
- **Degradation:** raise rather than proceed; the HTTP attempt may already have happened,
  but its unlogged result cannot be used or reach storage. This is a **runtime policy**, not a
  business invariant, because it protects the audit trail rather than a spend outcome.
- **Evidence:** the failure is surfaced to the caller; no unlogged result reaches storage.

> Note: `call_llm.py::_append_log` already implements the fail-closed write
> (`AGENTS.md §3`, `structural-constraints.md §5`). RP-004 records it as a policy and
> tells D/E what must stay true when the module is extended.

> **Appended fields (Phase 2).** The original four fields — `input`, `raw`, `parsed`,
> `error` — are never renamed or removed. The Phase 2 fields are **additive**:
> `call_id`, `tokens`, `session_id`, `request_id`, `usage_source`, `request_made`. A
> reader that ignores them still sees the four original fields unchanged.

### RP-005 — Budget exceeded (guard for C-INV-003)

- **Trigger:** accepted total + new amount > `budget_limit`.
- **Action:** `reject` + `REVIEW`.
- **Degradation:** previous total is authoritative; the new record is never applied.
- **Evidence:** log `error="policy:budget"` with amount and running total in `logs/review.jsonl`, carrying the relevant `call_id` (the evidence-join key) and its `request_id` (user-request grouping) so the line joins to its `llm_calls` record.

### RP-006 — Category out of vocabulary (guard for C-INV-002)

- **Trigger:** category not in the closed whitelist.
- **Action:** `reject` + `REVIEW`.
- **Degradation:** never coerce, never fuzzy-match, never ask the model to fix it.
- **Evidence:** log `error="policy:category"` with the rejected value in `logs/review.jsonl`, carrying the relevant `call_id` (the evidence-join key) and its `request_id` (user-request grouping) so the line joins to its `llm_calls` record.

### RP-007 — Storage boundary failure

- **Trigger:** storage rejects a record's shape or duplicate `call_id`, cannot read existing
  records (including malformed JSON, an invalid stored `call_id`, or a nonnumeric stored
  amount), or cannot write a validated record (I/O error, unwritable path, persistence or
  JSON serialization error).
- **Action:** raise an **independent `StorageError`**. It is an infrastructure failure, not
  a rule decision.
- **Reserved prefix:** `policy:*` is reserved **only** for deterministic policy/rule
  rejection (RP-003/005/006). A storage failure **must not** be rewritten as `policy:*`.
- **No partial state (C's required boundary — implementation verification pending):** no
  partial state change is allowed; the previous stored state remains authoritative (the
  write either completes or the prior state stands). **Current status:** D's
  `storage.append_validated` uses an append-mode write that raises `StorageError` on
  `OSError`, but the code does **not** demonstrate rollback of bytes written before the
  error. The boundary is therefore **required by C and not yet verified by the
  implementation**; it must not be read as confirmed.
- **Not a policy rejection:** a storage failure is **not** a normal policy rejection and
  **must not** create a policy review line (`logs/review.jsonl`).
- **Evidence:** the required failure signal is `StorageError` to the caller. A read or
  validation failure stops before a new storage record is appended. A write failure has
  the separate no-partial-state requirement above, which is not yet verified. The two
  uncaught `TypeError` paths below do not yet meet this signal contract.

**Unresolved D exception paths (code review, not test-verified).** In
`src/storage.py::_existing_call_ids`, a persisted JSON object with an unhashable
`call_id` (for example a list) reaches `ids.add(...)` and raises `TypeError`; the read
path does not convert it to `StorageError`. In `append_validated(record)`, structural
checks do not validate `decided_at` for JSON serializability. A direct caller can pass a
nonserializable value (for example a date/time object); `json.dumps(record)` then raises
`TypeError`, while the write handler catches only `OSError`. Both failures must stop the
operation and surface as `StorageError` under RP-007; this conversion is **not implemented**.

> **Pending clarification.** The exact storage-failure evidence detail (whether it is
> logged at all and, if so, in what record and format) is **not** defined by D's current
> implementation. RP-007 requires only `StorageError`, no `policy:*` conversion, and the
> absence of a `policy` review line; it does not invent a new log format. The precise
> evidence record remains pending until the implementation/spec fixes it.

**Rejection-evidence write failure (current D behavior).** If `pipeline._append_rejection`
cannot append to `logs/review.jsonl`, D raises `storage.StorageError("evidence write
failure: ...")` instead of returning the original `PolicyError`. No rejected record is
persisted. This is an evidence-write failure, not an RP-007 record-storage write, and it
does not create a successful review line. C's required behavior is fail-closed; atomicity
of a partially written review line is not demonstrated by D's append-mode writer.

---

## 3. Precedence

1. **Model-client failures (RP-002/001).** Check configuration, then attempt HTTP and
   parse its response envelope, then parse the model's JSON content. A failure stops
   before business validation.
2. **Call-log integrity (RP-004).** D writes the call line after the attempt or failure
   is known, before returning a result or raising it. If logging fails, no result is
   usable; the HTTP attempt and response parsing may already have occurred.
3. **Pipeline metadata and storage read.** After `extract` returns, a missing `call_id`
   raises `StorageError` (the valid-nonobject gap under RP-001). If `spent is None`,
   `storage.current_total()` reads persisted amounts and can raise `StorageError`
   (RP-007) before policy validation.
4. **Invariants (RP-003/005/006).** `policy_core` validates before a normal record write.
   A rejection attempts one review line; a review-write failure raises `StorageError`
   instead of returning the pending `PolicyError`.
5. **Storage append (RP-007).** Accepted records are structurally checked and appended.
   A failure raises `StorageError`, never `policy:*`; partial-write rollback is unverified.

After a failure is detected, no later result is accepted or stored. The call log is
written after classification of model-client outcomes, including failure paths.

---

## 4. Definition of done for each policy

- [ ] A test in `test/offline/` exercises the trigger (deterministic, no network).
- [ ] The degradation matches the `Action` column.
- [ ] Where a policy defines log evidence (RP-001/002/003/005/006), the documented line
      and `error` code are verified. For RP-004, verify that a logging failure prevents use
      of the result; RP-007 surfaces `StorageError`, while its separate evidence format is
      pending and must not be treated as a required policy-review line. Also verify that a
      rejected record is not persisted when writing its review evidence fails.

---

## 5. Phase 2 additions

> **Scope.** Phase 2 introduces a `call_id` that joins a model call to its downstream
> evidence, optional token accounting, an independent storage-failure error, and the
> Phase 2 evidence-join contract supplementing NFR-006 log traceability. This section
> records the agreed contracts. It does not renumber RP-001..RP-006. RP-001/002 are
> clarified in §2 to match D's implemented
> distinction between invalid model-content JSON, malformed HTTP response envelopes and
> pre-HTTP configuration failure. The pipeline behavior that implements the call-id,
> logging and storage contracts is D's; the NFR-006 log-coverage and Phase 2 join
> measurements are E's. C defines the contracts only.

### Call identifiers

- **Generation.** `call_id` is generated **inside `src/call_llm.py`** as
  `uuid4().hex` — a 32-hex-character string for each `extract` attempt, including a
  configuration failure before HTTP is attempted. No other format is valid; no caller
  may synthesize or override one.
- **Return channel.** `call_llm` returns the value to its caller through the private
  dictionary key **`__call_id__`** on the returned object.
- **Carriage.** The pipeline carries that value along the evidence path so that the
  downstream evidence records for one decision can be joined by the same `call_id`.
- **Boundary.** `__call_id__` is **removed before the payload reaches
  `src/policy_core.py`**. `policy_core` never sees a private key; it judges only the
  business payload.
- **Fail-closed interaction.** Because the id is produced in the same module that writes
  the audit line (RP-004), a call that cannot be logged keeps producing no usable result;
  `call_id` never rescues an unlogged call.

### LLM call logging

- **Required fields, unchanged.** `input`, `raw`, `parsed` and `error` keep their names and
  meaning (RP-004). They are never renamed, dropped or reinterpreted.
- **Extra fields.** `call_id` and `tokens` **may** be added as extra fields. They are
  additive: a reader that ignores them still sees the four required fields as before.
- **Token semantics.** `tokens` is `null` when no gateway usage object is available or
  the call fails before usage is processed. When the gateway supplies a usage object on a
  successful parse, `tokens` is an object with the keys `input`, `output` and `total`;
  missing or non-integer values inside that object are `null`. It records gateway-reported
  usage that D recorded, never an estimate. On JSON parsing failure, D logs
  `tokens: null` and `usage_source = missing` even if the HTTP response included usage;
  that usage is not carried into the failure log. `usage_source` is classified as follows:
  - **three integer values** → `usage_source = gateway`;
  - **at least one integer and at least one `null`** → `usage_source = partial`;
  - **`tokens: null` or all three values `null`** → `usage_source = missing`.
  Non-integer values (for example strings or booleans) normalize to `null` before this
  classification when a usage object is present.
- **Never fabricate.** Zero is **never** written as a substitute for a missing token value,
  and token usage is **never** estimated. `tokens: null` means no usage was recorded,
  including when parsing failed; a processed usage object with no valid counts becomes
  `{"input": null, "output": null, "total": null}`. Both have `usage_source = missing`.
  The stored `usage_source` values remain exactly `gateway`, `partial` and `missing`.
- **One line per attempt.** With a writable log, exactly **one** `logs/llm_calls.jsonl`
  record is written per `extract` attempt, including pre-HTTP configuration failure.
  RP-004 is the exception when logging itself fails. Adding `call_id` /
  `tokens` / the approved metadata fields does not add a second line, and policy outcomes
  still go to `logs/review.jsonl`
  (RP-003/RP-005/RP-006), not here.

#### 5.2.1 Approved additional metadata fields

The user approved four further logging fields for Phase 2. They are **additive** next to
the required four (`input`, `raw`, `parsed`, `error`) and the additional fields (`call_id`,
`tokens`); nothing above is renamed or removed.

- **`session_id`** — a 32-character `uuid4().hex` generated once when `src/call_llm.py`
  is loaded. Every call in that process shares it, so **per-session aggregation** in D's
  current implementation means grouping by process run. It does not identify a separate
  user session when one process handles multiple users. It is distinct from `call_id`,
  which is generated for each call.
- **`request_id`** — an identifier for **one user request**. One request may trigger
  **multiple** `extract` attempts, so several `llm_calls` records may share one
  `request_id`. `call_id` remains the unique identifier for **one attempt**;
  `request_id` groups attempts, `call_id` identifies one attempt. In D's current
  `pipeline.process`, one `request_id` is created per invocation and only one `extract`
  call is made; multi-attempt grouping requires a caller to pass the same id explicitly
  to multiple `extract` calls and is not yet a pipeline behavior.
- **`usage_source`** — an enum with **exactly** these values: `gateway`, `partial`,
  `missing`. It describes the token counts **recorded in this log line**: `gateway` = all
  three counts present, `partial` = some counts present, `missing` = no counts recorded.
  `missing` does not prove the gateway supplied no usage: D also records it when JSON
  parsing fails before the returned usage is used.
- **`request_made`** — a boolean indicating whether the code **attempted an HTTP call**.
  It is `true` when `call_llm` enters its HTTP path, including connection, DNS and timeout
  failures; it does **not** prove that the request reached the gateway. It is `false` for
  local/configuration failures that stop before the HTTP path (for example missing base URL
  or API key). This is a structured boolean, not inferred from `error` text.
- **Derived `not_called` category** — reporting may count `request_made: false` rows as
  `not_called`. This is an operational reporting category, not a fourth `usage_source` value;
  the stored `usage_source` enum remains exactly `gateway`, `partial`, or `missing`.

Preserved requirements (unchanged by these fields):

- `input`, `raw`, `parsed` and `error` keep their names and meaning (RP-004).
- `call_id` remains the unique identifier for one `extract` attempt, even if HTTP was not attempted.
- `tokens` remains additive and is always present: `null` if usage was not recorded,
  otherwise an object with `input`, `output` and `total` (missing counts are `null`).
- Missing token usage is **never** written as zero or fabricated. Both `tokens: null` and
  an object with all three counts `null` have `usage_source = missing`.
- `policy:*` remains reserved for deterministic rule rejection (RP-003/005/006).
- Exactly one `llm_calls` record per `extract` attempt remains the contract when logging
  succeeds; RP-004 prevents use of an attempt whose log write fails.
- `usage_source` must stay consistent with `tokens`: `gateway`/`partial` imply token data
  exists, `missing` implies it does not.

#### 5.2.2 Pre-HTTP local failures (confirmed)

A missing base URL or API key stops the call before the HTTP attempt but **still writes
exactly one `llm_calls.jsonl` line**. The record uses the same ten-key schema as a normal
call; missing values are written as `null` and **never omitted**:

- **All ten schema keys are present** (`input`, `raw`, `parsed`, `error`, `call_id`,
  `tokens`, `session_id`, `request_id`, `usage_source`, `request_made`); a missing value is
  `null`, never an absent key.
- **Identifiers:** `call_id`, `session_id` and `request_id` are 32-character `uuid4().hex`.
- **`usage_source`** is `missing`.
- **`tokens`** is `null` because no gateway usage object exists before an HTTP request.
- **`raw`** and **`parsed`** are `null`.
- **`request_made`** is `false`.

This is the **only** `request_made = false` path in D's current implementation: missing
configuration stops before the HTTP attempt. Any path that attempts the call records
`request_made = true`, even if the connection fails before the gateway receives it.

### Storage failure is not a policy rejection

> This section is the contract rationale; the formal policy entry is **RP-007** (§2).

- **Trigger.** Storage input validation, duplicate-id checking, reading existing records
  or writing a record fails. These include malformed persisted data and I/O errors.
- **Action:** raise an **independent `StorageError`**. It is a transport/infrastructure
  failure, not a rule decision.
- **Reserved prefix.** `policy:*` error codes are reserved **only** for deterministic
  policy/rule rejection (amount, category, budget — RP-003/005/006). A storage failure
  **must not** be rewritten as `policy:*`; doing so would make "correctly refused" and
  "failed to persist" indistinguishable.
- **No partial state (required boundary; implementation verification pending).** A record
  write failure must leave **no partial state change**: the write either completes or the previous
  state stands. No write-then-check, no half-applied record. See RP-007 — the current
  append-mode write raises `StorageError` but does not demonstrate rollback, so this remains
  a C-required boundary rather than a verified property.
- **Evidence:** the failure surfaces as `StorageError` to the caller; it never produces a
  `review.jsonl` policy line.

### Evidence linkage by `call_id`

Main's NFR-006 measures **log coverage**: the percentage of model calls with a
`llm_calls.jsonl` line and policy rejections with a `review.jsonl` line. Its numeric
coverage threshold is `null` in main. D writes one call-log line per `extract` attempt
when the log is writable, including pre-HTTP configuration failures, and one review line
per policy rejection when the review log is writable. If either evidence write fails, the
operation fails closed (RP-004 or `StorageError`) rather than proceeding as a successful
decision. The Phase 2 `call_id` join below is an **additional structural traceability
check**, not a replacement definition or a numeric coverage threshold.

There are three possible evidence locations — the two log files (`llm_calls` and
`review`) plus the storage record in `data/records.jsonl` — but a
decision produces **one applicable pair**, not all three records at once. The check is
path-specific:

- **Accepted decision:** `llm_calls.call_id` equals the accepted record's
  `data/records.jsonl` `call_id`. Evidence shape = the `llm_calls` record **plus** the
  normal storage evidence.
- **Rejected decision:** `llm_calls.call_id` equals the `review.jsonl` line's `call_id`.
  Evidence shape = the `llm_calls` record **plus** the review evidence.
- **A rejected decision must not create a normal storage record.** Rejection means the
  stored data is unchanged (RP-003/005/006); the review line is the second evidence record
  instead, and no normal storage record exists to join.
- **Conditional, one shape per decision.** A decision has exactly one of the two shapes; it
  never has both a storage record and a review line for the same decision.

A decision is **not** required to produce all three records. The join rule does not require
"three relevant `call_id` locations" and does not set NFR-006's numeric log-coverage
threshold.

### 5.5 Approved D decisions (recorded here for the shared boundary)

- **`call_id` format:** `uuid4().hex`. Fixed 32-hex-character form; see the Call identifiers section.
- **`request_id` format and role:** also `uuid4().hex`, generated per **user request**. It is
  an **additive grouping** field: one request may span several calls, so several
  `llm_calls` records share one `request_id`. `call_id` remains the **primary evidence-join
  key**; `request_id` groups calls belonging to one user request.
- **`_append_rejection` preserves the original rejection code.** The rejection writer is
  `src/pipeline.py::_append_rejection`. It writes the **original** `PolicyError.code` (for
  example `policy:category`) as the line's `error`, rather than replacing or re-coding it,
  so the review line and the routing decision agree. Each rejection line carries both
  `call_id` (join key) and `request_id` (grouping).

#### Approved design not yet implemented — validated storage spend

- **Intended boundary (approved by C, not implemented in D's current code):**
  `append_validated(record, expected_spent=None)` with
  - `total == expected_spent + amount`, and
  - `expected_spent >= already persisted cumulative spend`.

  `expected_spent` would be a **numeric validation parameter, not a persisted record
  field**. Its purpose is to prevent **under-reporting prior spending**, which would
  otherwise let a record slip past the budget guard (`C-INV-003` / `RP-005`).
- **Current implementation (verified):** `src/storage.py::append_validated(record)` takes a
  **single `record` argument** and has no `expected_spent`; it validates the record's
  field names and basic types and rejects a duplicate `call_id`, but it does **not** run
  `policy_core` or compare the record against persisted cumulative spend. Direct callers
  can therefore pass a negative amount, an out-of-vocabulary category, or a total above
  the budget if the fields have acceptable types. The safety contract requires callers to
  use `pipeline.process` and not bypass `policy_core`; the storage entry point itself does
  **not** enforce that contract. A repository-wide search finds no `expected_spent` in D's
  tree.
- **Consequence — budget-bypass gap (not secured):** `src/pipeline.py::process(spent=None,
  budget_limit=...)` reads `storage.current_total()` **only when `spent is None`**. When a
  caller supplies `spent`, that value is trusted and is passed straight to
  `policy_core.validate_record`. Because neither `process` nor `append_validated` checks the
  caller-supplied `spent` against the persisted cumulative total, a **lower
  caller-supplied `spent` can weaken the cumulative budget check** (`C-INV-003` /
  `RP-005`). This is a **known gap**, not a secured property; closing it requires
  implementing the `expected_spent` boundary above.

#### Repository-root anchoring of evidence paths (verified per module)

Evidence paths are anchored to the repository root via
`pathlib.Path(__file__).resolve().parents[1]`, so they follow the module rather than the
process working directory. This is **confirmed** in:

- `src/call_llm.py` — `LOG_PATH` (`logs/llm_calls.jsonl`)
- `src/pipeline.py` — `REVIEW_PATH` (`logs/review.jsonl`)
- `src/storage.py` — `DATA_PATH` (`data/records.jsonl`)
- `src/measure_latency.py` — `LATENCY_PATH` (`logs/latency.jsonl`)

It is **not** used everywhere: `src/report_tokens.py` still defaults to a **relative**
`LOG_PATH = pathlib.Path("logs/llm_calls.jsonl")` (working-directory dependent, overridable
by an argument), and `src/measure_tokens.py` defines no path of its own. The anchoring
claim applies only to the four modules listed above.

#### D-02 — error logging short-code rule (unresolved implementation debt)

Short, **secret-safe** error information in logs is a **security requirement** (Phase 1,
`structural-constraints.md §5`): the `error` field is a short code, and a raw exception
string must not be able to leak a URL, query parameter or credential into the log. D's
current `src/call_llm.py::extract` constructs `error` using full `str(exc)` for transport
and protocol failures; `_append_log` then writes that record. This is an **unresolved D
implementation debt (D-02)**: the security requirement stands and the implementation
has not yet been brought into line with it.

---
