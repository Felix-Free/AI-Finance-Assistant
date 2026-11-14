# Invariants — Deterministic Safety Boundaries (owner: role C)

> Purpose: the closed set of business invariants the application must enforce in
> deterministic code (`src/policy_core.py`, implemented by D) before any model output
> may affect stored data. The model proposes; code disposes.
>
> Status: **Phase 1 · C-Security (transcript 60339160).** Specs only — role C defines the
> rules; role D implements each guard as `enforce_<subject>` plus a negative test;
> role E verifies the test fails when the guard is removed. Neither C nor D edits a
> generated file by hand (`structural-constraints.md §2.2`).

---

## 1. Numbering decision (explicit)

The repository convention in `structural-constraints.md §3` uses global `INV-###` ids.
However, the Phase 1 transcript of another role (`transcripts/60915652-LiuWanyang.md`)
**already reserved `INV-002` for "category must be in a closed list"**.

To avoid duplicating or silently redefining a global id that another role has claimed,
this document uses **role-scoped ids**: `C-INV-###`, where `C` records the role that
owns the specification. Consequences:

- `C-INV-002` and the transcript's `INV-002` refer to the **same rule** (closed category
  list). The transcript's reservation stays valid; this document is its written spec.
- When the invariants are merged into one global register (Phase 3), the mapping is
  recorded in the table below and `INV-###` becomes the canonical id. Until then, never
  refer to a `C-INV-###` without the `C-` prefix.
- Guards and tests may reference either id, but the test name must contain the id it
  implements (`test_inv###_<behaviour>` per §3) — D chooses which, and records the choice.

| Role-scoped id | Global id (on merge) | Rule |
|---|---|---|
| `C-INV-001` | `INV-001` | amount is a finite positive number |
| `C-INV-002` | `INV-002` (reserved in 60915652) | category is in the closed whitelist |
| `C-INV-003` | `INV-003` | cumulative spending never exceeds the budget |

---

## 2. Guard specification blocks (handoff format, `structural-constraints.md §2.2`)

> **Rejection evidence (decision 2026-11-09, option B; aligned in Phase 2 with the call-id contract).** Every policy
> rejection — for all three invariants, including `C-INV-001` — attempts to append exactly
> one line to `logs/review.jsonl` with the fields `error`, `amount`, `category`, `spent`,
> `total`, `review`, `call_id` and `request_id`. If the review write fails, D surfaces
> `StorageError` and does not persist the rejected record. With a writable call log,
> `logs/llm_calls.jsonl` keeps exactly one line per `extract` attempt, including a
> pre-HTTP configuration failure (`runtime-policy-catalog.md` RP-004). A policy outcome
> never adds a second line there. The
> rejection line must carry the **same `call_id`** as the related `llm_calls` record, so a
> rejection can be joined to its call. The rejection line does **not** duplicate the full input
> text; the input remains on the `llm_calls` line that shares the `call_id`.

### C-INV-001 — amount must be a finite positive number

```
C-INV-001
Condition   : if amount is missing, not a finite number, or <= 0 then reject
Threshold   : amount > 0; more than 2 decimal places is rejected (money is cents)
Exception   : PolicyError
On failure  : reject  (record discarded; no persistence; one log line)
Boundary    : -0.01, 0, 0.01, 0.005  (and non-numeric: "350", null, NaN, Inf, 100.001)
Evidence    : logs/review.jsonl line with error="policy:amount" and review=false
```

### C-INV-002 — category must be in the closed whitelist

```
C-INV-002
Condition   : if category is not exactly one of the code-defined closed vocabulary then reject
Threshold   : case-sensitive exact match against the whitelist defined in code
Exception   : PolicyError
On failure  : reject, flag REVIEW  (record discarded; no persistence)
Boundary    : "Food", "餐饮", "meal", ""  (all rejected) vs each whitelisted value (accepted)
Evidence    : logs/review.jsonl line with error="policy:category" and review=true
```

> The whitelist itself is defined in code (`src/policy_core.py`), never in a prompt, and
> never inferred from the model. C does not fix the vocabulary here; D places it in code
> and E tests every member.

### C-INV-003 — cumulative spending must never exceed the budget

```
C-INV-003
Condition   : if existing accepted total + new amount > budget_limit then reject the new record
Threshold   : budget_limit is passed to pipeline.process (current default 1000.0); equality (==) is allowed. A stored per-period configuration source is not implemented in D.
Exception   : PolicyError
On failure  : reject  (new record discarded; the existing total is unchanged); flag REVIEW
Boundary    : budget-0.01 (accepted), budget (accepted), budget+0.01 (rejected)
              — proves the check is cumulative, not per-record, and has no off-by-one
Evidence    : logs/review.jsonl line with error="policy:budget", amount and running total,
              review=true
```

> Rationale: the budget limit is the core safety property of a personal finance
> assistant. It is deliberately kept as a business invariant, not downgraded to a runtime
> policy. Logging integrity (which is also required) is captured as a runtime policy —
> see `runtime-policy-catalog.md RP-004` — because it guards the audit trail, not the
> business outcome.

---

## 3. Definition of done for each invariant (handed to D and E)

- [ ] One guard function `enforce_<subject>` in `src/policy_core.py`.
- [ ] Raises `PolicyError` (the single rejection type, `structural-constraints.md §4`).
- [ ] At least one test whose name contains the id and which **fails when the guard is
      removed**, covering every boundary value in its block.
- [ ] Validation happens **before** any state change (`§2.2`, no write-then-check).
- [ ] No rule is enforced by prompt text; only by code.
