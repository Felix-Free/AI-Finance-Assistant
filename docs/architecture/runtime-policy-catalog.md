# Runtime Policy Catalog (owner: role C)

> Purpose: the deterministic runtime policies that govern *how* the application degrades
> when something goes wrong — a bad model response, a transport failure, a rejected
> record, or an unwritable log. Distinct from `invariants.md`, which defines the business
> rules that must never be violated.
>
> Status: **Phase 1 · C-Security (transcript 60339160); extended in Phase 2 (§5).**
> Specs only. Role C defines the trigger, action and degradation; role D implements; role
> E verifies. Phase 1 policies RP-001..RP-006 keep their ids and meaning; the Phase 2
> addendum adds the `call_id`, token, storage-failure and NFR-006 evidence contracts
> without renaming or renumbering any existing policy.

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
- **Evidence:** log `error="policy:<subject>"` with the offending field and value in `logs/review.jsonl`.

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

### RP-005 — Budget exceeded (guard for C-INV-003)

- **Trigger:** accepted total + new amount > `budget_limit`.
- **Action:** `reject` + `REVIEW`.
- **Degradation:** previous total is authoritative; the new record is never applied.
- **Evidence:** log `error="policy:budget"` with amount and running total in `logs/review.jsonl`.

### RP-006 — Category out of vocabulary (guard for C-INV-002)

- **Trigger:** category not in the closed whitelist.
- **Action:** `reject` + `REVIEW`.
- **Degradation:** never coerce, never fuzzy-match, never ask the model to fix it.
- **Evidence:** log `error="policy:category"` with the rejected value in `logs/review.jsonl`.

---

## 3. Precedence

1. **Logging (RP-004) first.** If the call cannot be logged, stop — nothing else runs.
2. **Transport (RP-002)** before parse — a failed call has no output to judge.
3. **Parse (RP-001)** before business rules.
4. **Invariants (RP-003/005/006)** last, before any state change.

Later stages never run when an earlier stage rejects.

---

## 4. Definition of done for each policy

- [ ] A test in `test/offline/` exercises the trigger (deterministic, no network).
- [ ] The degradation matches the `Action` column.
- [ ] The evidence is exactly one log line with the documented `error` code.

---

## 5. Phase 2 addendum (C2–C6)

> **Scope.** Phase 2 introduces a `call_id` that joins a model call to its downstream
> evidence, optional token accounting, an independent storage-failure error, and the
> NFR-006 evidence-join rule. This section records the agreed contracts. It **does not
> change** RP-001..RP-006: their triggers, actions and evidence codes stay exactly as
> written in §2. The pipeline behavior that implements C2/C3/C4 is D's; the NFR-006
> measurement is E's. C defines the contracts only.

### 5.1 C2 — `call_id` generation and carriage

- **Generation.** `call_id` is generated **inside `src/call_llm.py`** as
  `uuid4().hex[:12]` — a 12-hex-character string. No other format is valid; no caller
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

### 5.2 C3 — `llm_calls.jsonl` logging contract

- **Required fields, unchanged.** `input`, `raw`, `parsed` and `error` keep their names and
  meaning (RP-004). They are never renamed, dropped or reinterpreted.
- **Extra fields.** `call_id` and `tokens` **may** be added as extra fields. They are
  additive: a reader that ignores them still sees the four required fields as before.
- **Token semantics.** `tokens` records model-token accounting supplied by the gateway
  (for example prompt/completion token counts from the response usage object). Its meaning
  is "tokens the gateway reported for this call"; it is **not** a derived estimate.
- **Never fabricate.** `tokens` is recorded **only when the gateway supplies it**. If the
  gateway omits usage data, the field is absent (or `null`); it is never estimated,
  back-filled, or computed from the raw text.
- **One line per call.** Exactly **one** `logs/llm_calls.jsonl` record per model call is
  preserved. Adding `call_id` / `tokens` does not add a second line, and policy outcomes
  still go to `logs/review.jsonl` (RP-003/RP-005/RP-006), not here.

### 5.3 C4 — storage failure is not a policy rejection

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

### 5.4 C6 — NFR-006 evidence join (threshold and conditional evidence shape)

**NFR-006 threshold (strict).** Three relevant `call_id` locations/evidence records for
the same decision must carry the same `call_id`. This is the agreed threshold in full; it
is not weakened to a two-record join, it has no "where applicable" escape, and it is not
redefined from whatever records happen to exist.

> **Pending clarification.** The exact names of the three required `call_id` locations are
> not available in this repository yet. Until they are fixed by the pipeline/spec, the
> threshold keeps the agreed wording — three relevant `call_id` locations/evidence records
> for the same decision carry the same `call_id` — and the precise measurement mapping is
> marked pending. It is not replaced with a weaker rule.

**Conditional evidence shape (a separate rule, not the threshold).** This rule describes
*which evidence records a decision has*. It is distinct from the threshold above, which
governs *how many of those records must share the `call_id`*.

- **Accepted decision.** Evidence shape = the `llm_calls` record **plus** the normal
  storage evidence. The storage record for the decision carries the same `call_id` as its
  call line.
- **Rejected decision.** Evidence shape = the `llm_calls` record **plus** the review
  evidence (`logs/review.jsonl`). The review line for that rejection carries the same
  `call_id`.
- **A rejected decision must not create a normal storage record.** Rejection means the
  stored data is unchanged (RP-003/005/006); the review line is the second evidence record
  instead, and no normal storage record exists to join.
- **Conditional, one shape per decision.** A decision has exactly one of the two shapes; it
  never has both a storage record and a review line for the same decision.

### 5.5 Approved D decisions (recorded here for the shared boundary)

- **`call_id` format:** `uuid4().hex[:12]`. Fixed; see §5.1.
- **`_append_review` preserves the original rejection code.** When review evidence is
  written, `_append_review` keeps the **original** `error` code (for example
  `policy:category`) rather than replacing or re-coding it. The code that caused the
  rejection is the one recorded, so the review line and the routing decision agree.

---
