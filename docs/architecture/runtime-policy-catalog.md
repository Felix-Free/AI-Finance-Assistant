# Runtime Policy Catalog (owner: role C)

> Purpose: the deterministic runtime policies that govern *how* the application degrades
> when something goes wrong — a bad model response, a transport failure, a rejected
> record, or an unwritable log. Distinct from `invariants.md`, which defines the business
> rules that must never be violated.
>
> Status: **Phase 1 · C-Security (transcript 60339160); extended in Phase 2 (§5).**
> Specs only. Role C defines the trigger, action and degradation; role D implements; role
> E verifies. Phase 1 policies RP-001..RP-006 keep their ids and meaning; Phase 2 adds
> **RP-007 (storage write failure)** plus the `call_id`, token, storage-failure and NFR-006
> evidence contracts, without renaming or renumbering any existing policy.

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

### RP-001 — Model returns non-JSON

- **Trigger:** the model response body is not a JSON object.
- **Action:** `reject`; do not retry (a second malformed answer is likely).
- **Degradation:** log `error="not_json"` with the raw text; surface a rejection to the
  caller. The `JSONDecodeError` is not swallowed (`call_llm.py` re-raises).
- **Evidence:** one `logs/llm_calls.jsonl` line: `input`, `raw`, `parsed=null`, `error`.

### RP-002 — Transport / HTTP failure

- **Trigger:** network error, timeout, auth failure, or non-200 status.
- **Action:** surface `LlmTransportError`; do not persist anything.
- **Degradation:** distinct from a policy rejection so tests can tell "correctly refused"
  from "crashed" (`structural-constraints.md §4`).
- **Evidence:** log `error="transport: ..."` or `error="http <code>"`.

### RP-003 — Invariant violation

- **Trigger:** any of `C-INV-001`, `C-INV-002`, `C-INV-003` fails.
- **Action:** `reject`; raise `PolicyError`.
- **Degradation:** stored data and running totals stay unchanged; the record is not
  applied. `C-INV-002` and `C-INV-003` additionally flag `REVIEW`.
- **Evidence:** log `error="policy:<subject>"` with the offending field and value in `logs/review.jsonl`, carrying the relevant `call_id` so the line joins to its `llm_calls` record.

### RP-004 — Logging integrity (fail-closed)

- **Trigger:** the per-call audit line cannot be written, or a call would produce zero or
  more than one line, or the four required fields (`input`, `raw`, `parsed`, `error`)
  are renamed/dropped.
- **Action:** the result of that call **must not be used**. Effectively `reject`.
- **Degradation:** raise rather than proceed; a call that cannot be logged is a call that
  did not happen. This is the logging-integrity rule — it is a **runtime policy**, not a
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
- **Evidence:** log `error="policy:budget"` with amount and running total in `logs/review.jsonl`, carrying the relevant `call_id` so the line joins to its `llm_calls` record.

### RP-006 — Category out of vocabulary (guard for C-INV-002)

- **Trigger:** category not in the closed whitelist.
- **Action:** `reject` + `REVIEW`.
- **Degradation:** never coerce, never fuzzy-match, never ask the model to fix it.
- **Evidence:** log `error="policy:category"` with the rejected value in `logs/review.jsonl`, carrying the relevant `call_id` so the line joins to its `llm_calls` record.

### RP-007 — Storage write failure

- **Trigger:** a validated record cannot be written to storage (I/O error, unwritable path,
  persistence error).
- **Action:** raise an **independent `StorageError`**. It is an infrastructure failure, not
  a rule decision.
- **Reserved prefix:** `policy:*` is reserved **only** for deterministic policy/rule
  rejection (RP-003/005/006). A storage failure **must not** be rewritten as `policy:*`.
- **No partial state:** no partial state change is allowed; the previous stored state
  remains authoritative (the write either completes or the prior state stands).
- **Not a policy rejection:** a storage failure is **not** a normal policy rejection and
  **must not** create a policy review line (`logs/review.jsonl`).
- **Evidence:** the failure surfaces as `StorageError` to the caller.

> **Pending clarification.** The exact storage-failure evidence detail (whether it is
> logged at all and, if so, in what record and format) is **not** defined elsewhere in this
> repository. RP-007 requires only `StorageError` and the absence of a `policy` review line;
> it does not invent a new log format. The precise evidence record is pending clarification
> until the pipeline/spec fixes it.

---

## 3. Precedence

1. **Logging (RP-004) first.** If the call cannot be logged, stop — nothing else runs.
2. **Transport (RP-002)** before parse — a failed call has no output to judge.
3. **Parse (RP-001)** before business rules.
4. **Invariants (RP-003/005/006)** last, before any state change.
5. **Storage write (RP-007)** runs where the state change would happen. If it fails, raise
   `StorageError` and leave the previous state authoritative — never convert it into a
   `policy:*` rejection.

Later stages never run when an earlier stage rejects.

---

## 4. Definition of done for each policy

- [ ] A test in `test/offline/` exercises the trigger (deterministic, no network).
- [ ] The degradation matches the `Action` column.
- [ ] The evidence is exactly one log line with the documented `error` code.

---

## 5. Phase 2 additions

> **Scope.** Phase 2 introduces a `call_id` that joins a model call to its downstream
> evidence, optional token accounting, an independent storage-failure error, and the
> NFR-006 evidence-join rule. This section records the agreed contracts. It **does not
> change** RP-001..RP-006: their triggers, actions and evidence codes stay exactly as
> written in §2. The pipeline behavior that implements the call-id, logging and storage contracts is D's; the NFR-006
> measurement is E's. C defines the contracts only.

### Call identifiers

- **Generation.** `call_id` is generated **inside `src/call_llm.py`** as
  `uuid4().hex` — a 32-hex-character string. No other format is valid; no caller
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
- **Token semantics.** `tokens` is **always an object** with exactly the keys `input`,
  `output` and `total`; a missing value is written as `null`, never omitted. Its meaning is
  "tokens the gateway reported for this call"; it is **not** a derived estimate. The
  `usage_source` is derived from the three token values:
  - **three integer values** → `usage_source = gateway`;
  - **at least one integer and at least one `null`** → `usage_source = partial`;
  - **all three values `null`** → `usage_source = missing`.
  Non-integer values (for example strings or booleans) normalize to `null` before this
  classification.
- **Never fabricate.** Zero is **never** written as a substitute for a missing token value,
  and token usage is **never** estimated. When all values are missing the object is
  `{"input": null, "output": null, "total": null}` with `usage_source = missing`; it is never
  `0`. The stored `usage_source` values remain exactly `gateway`, `partial` and `missing`.
- **One line per call.** Exactly **one** `logs/llm_calls.jsonl` record per actual model
  call is preserved. Adding `call_id` / `tokens` / the approved metadata fields does not add
  a second line, and policy outcomes still go to `logs/review.jsonl`
  (RP-003/RP-005/RP-006), not here.

#### 5.2.1 Approved additional metadata fields

The user approved four further logging fields for Phase 2. They are **additive** next to
the required four (`input`, `raw`, `parsed`, `error`) and the additional fields (`call_id`,
`tokens`); nothing above is renamed or removed.

- **`session_id`** — a stable identifier for the user/session context, used for
  **per-session aggregation** (all calls in one user session share it). It is distinct from
  `call_id`: one session may span many calls.
- **`request_id`** — an identifier for **one user request**. One request may trigger
  **multiple** actual LLM API calls, so several `llm_calls` records may share one
  `request_id`. `call_id` remains the unique identifier for **one actual LLM API call**;
  `request_id` groups calls, `call_id` identifies a call.
- **`usage_source`** — an enum with **exactly** these values: `gateway`, `partial`,
  `missing`. It records where the token-usage figure came from: `gateway` = supplied by the
  gateway, `partial` = only part of the usage was supplied, `missing` = none was supplied.
- **`request_made`** — a boolean; **`true` only when an HTTP request was actually sent**,
  **`false` for local/configuration/preflight failures** (missing config, no API key, a
  preflight rejection, and any other failure that never reached the network). It is a
  structured boolean, not inferred from `error` text: error-message wording must not be the
  only machine-readable definition of `request_made`.
- **Derived `not_called` category** — reporting may count `request_made: false` rows as
  `not_called`. This is an operational reporting category, not a fourth `usage_source` value;
  the stored `usage_source` enum remains exactly `gateway`, `partial`, or `missing`.

Preserved requirements (unchanged by these fields):

- `input`, `raw`, `parsed` and `error` keep their names and meaning (RP-004).
- `call_id` remains the unique identifier for one actual LLM API call.
- `tokens` remains additive and is always an object with `input`, `output` and `total`;
  missing values are `null`, never omitted.
- Missing token usage is **never** written as zero and is **never** fabricated; when all
  three values are `null`, `usage_source` is `missing` and `tokens` is
  `{"input": null, "output": null, "total": null}`, not `0`.
- `policy:*` remains reserved for deterministic rule rejection (RP-003/005/006).
- Exactly one `llm_calls` record per actual model call remains the contract.
- `usage_source` must stay consistent with `tokens`: `gateway`/`partial` imply token data
  exists, `missing` implies it does not.

#### 5.2.2 Pre-HTTP local failures (confirmed)

A local/configuration/preflight failure — for example a missing config, a missing API key,
or a rejection before any network call — **still writes exactly one `llm_calls.jsonl`
line**. The record uses the same ten-key schema as a normal call; missing values are written
as `null` and **never omitted**:

- **All ten schema keys are present** (`input`, `raw`, `parsed`, `error`, `call_id`,
  `tokens`, `session_id`, `request_id`, `usage_source`, `request_made`); a missing value is
  `null`, never an absent key.
- **Identifiers:** `call_id`, `session_id` and `request_id` are 32-character `uuid4().hex`.
- **`usage_source`** is `missing`.
- **`tokens`** is always an object with `input`, `output` and `total`; missing values are
  `null`.
- **`raw`** and **`parsed`** are `null`.
- **`request_made`** is `false`.

This is the **only** `request_made = false` path: any failure that occurs before an HTTP
request is actually sent is logged this way, and every path that sends a request has
`request_made = true`. This lifecycle is confirmed by D and is no longer pending.

### Storage failure is not a policy rejection

> This section is the contract rationale; the formal policy entry is **RP-007** (§2).

- **Trigger.** A write to storage fails (I/O error, unwritable path, persistence error).
- **Action:** raise an **independent `StorageError`**. It is a transport/infrastructure
  failure, not a rule decision.
- **Reserved prefix.** `policy:*` error codes are reserved **only** for deterministic
  policy/rule rejection (amount, category, budget — RP-003/005/006). A storage failure
  **must not** be rewritten as `policy:*`; doing so would make "correctly refused" and
  "failed to persist" indistinguishable.
- **No partial state.** A storage failure must leave **no partial state change**: the
  write either completes or the previous state stands. No write-then-check, no
  half-applied record.
- **Evidence:** the failure surfaces as `StorageError` to the caller; it never produces a
  `review.jsonl` policy line.

### Evidence linkage by `call_id`

**NFR-006 evidence-join rule.** There are three possible evidence locations — the two log
files (`llm_calls` and `review`) plus the storage record in `data/records.jsonl` — but a
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

A decision is **not** required to produce all three records, and the acceptance threshold is
**not** phrased as "three relevant `call_id` locations must exist".

### 5.5 Approved D decisions (recorded here for the shared boundary)

- **`call_id` format:** `uuid4().hex`. Fixed 32-hex-character form; see the Call identifiers section.
- **`_append_review` preserves the original rejection code.** When review evidence is
  written, `_append_review` keeps the **original** `error` code (for example
  `policy:category`) rather than replacing or re-coding it. The code that caused the
  rejection is the one recorded, so the review line and the routing decision agree.
- **Validated storage spend.** The sole storage entry point is
  `append_validated(record, expected_spent=None)`. Its approved boundary is:
  - `total == expected_spent + amount` (the running total must equal the caller's expected
    prior spend plus this record's amount);
  - `expected_spent >= already persisted cumulative spend` — the caller may not claim a
    smaller prior spend than what is already stored.

  `expected_spent` is a **numeric validation parameter, not a persisted record field**. Its
  purpose is to prevent **under-reporting prior spending**, which would otherwise let a
  record slip past the budget guard (`C-INV-003`/`RP-005`). C specifies the boundary only;
  D owns the implementation in `src/`.

---
