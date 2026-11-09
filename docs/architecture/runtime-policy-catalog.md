# Runtime Policy Catalog (owner: role C)

> Purpose: the deterministic runtime policies that govern *how* the application degrades
> when something goes wrong — a bad model response, a transport failure, a rejected
> record, or an unwritable log. Distinct from `invariants.md`, which defines the business
> rules that must never be violated.
>
> Status: **Phase 1 · C-Security (transcript 60339160).** Specs only. Role C defines the
> trigger, action and degradation; role D implements; role E verifies.

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
- **Evidence:** log `error="policy:<subject>"` with the offending field and value.

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
- **Evidence:** log `error="policy:budget"` with amount and running total.

### RP-006 — Category out of vocabulary (guard for C-INV-002)

- **Trigger:** category not in the closed whitelist.
- **Action:** `reject` + `REVIEW`.
- **Degradation:** never coerce, never fuzzy-match, never ask the model to fix it.
- **Evidence:** log `error="policy:category"` with the rejected value.

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
