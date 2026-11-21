# ADR-004 — Pipeline Budget Authority and Audit Redaction

- **Status:** Proposed — pending role C confirmation.
- **Owner after review:** Role C (with B) — `docs/architecture/` is C/B-owned.
- **Date:** Phase 3+, 2026-11-21.
- **Related:** `docs/architecture/adr/003-atomic-append-and-locking.md`;
  `docs/architecture/invariants.md` (INV-001/002/003); `docs/architecture/runtime-policy-catalog.md`
  (RP-004 fail-closed logging); `src/storage.py`; `src/pipeline.py`; `src/call_llm.py`;
  `test/offline/test_evidence_join.py`.

> **Reading this document.** Everything below is *(source)* unless marked *(derived — proposed)*.
> The behaviour is implemented; this ADR records the reasoning for C to confirm or reject.

---

## 1. Context

Two problems surfaced in the final audit:

1. **Budget authority.** INV-003 (cumulative spend ≤ budget) must be decided against what is
   actually persisted, not against a caller-supplied number. A stale `spent` (too low *or* too
   high) must not decide the budget and must not raise `StorageError` by itself.
2. **Audit safety.** `logs/llm_calls.jsonl` and `logs/review.jsonl` are committed evidence, so they
   must never carry user text, raw model output, amounts, or IO details (paths, raw `OSError`,
   URLs, credentials).

---

## 2. Decision

### 2.1 Locked persisted total is authoritative

The pipeline's `storage.current_total()` read is only an **advisory pre-check**. The authoritative
decision happens inside `storage._append_from_pipeline`, which under `_locked()`:

- re-reads `persisted = current_total()`;
- recomputes `total = persisted + amount`;
- enforces INV-001/002/003 against the locked value.

The locked `total` is the value written **and** returned. Equality
(`persisted + amount == budget_limit`) is accepted. Over budget raises
`PolicyError(code="policy:budget", review=True)` before any byte is written.

### 2.2 Public `append_validated` default remains direct

`storage.append_validated(record, expected_spent=None, *, origin=None)` keeps its **direct**
semantics for ordinary callers: `expected_spent` below the persisted total is a `StorageError`;
direct policy failures remain `PolicyError`; the total-consistency and duplicate checks are
unchanged. The default (`origin=None`) never selects the pipeline path.

### 2.3 `_PIPELINE_ORIGIN` is a controlled internal marker

A module-level `_PIPELINE_ORIGIN = object()` sentinel is the only way to select the authoritative
persisted-total path:

```python
if origin is _PIPELINE_ORIGIN:
    return _append_from_pipeline(record)
```

Only `pipeline.process` passes `origin=storage._PIPELINE_ORIGIN`. There is **no** public
`stale_ok` / `recompute` / `allow_stale` flag; the marker is private and cannot be constructed by an
external caller except by importing the module-private name.

### 2.4 A′ log redaction and safe errors

- `logs/llm_calls.jsonl`: `input` and `raw` become `redacted:len=<n>` (Python `len`, characters);
  `raw` is `None` when no response text existed. `parsed` is `None` on every path (success,
  non-JSON, transport, config). `call_id`, `request_id`, `session_id`, `tokens`, `usage_source`,
  `request_made`, and the safe `error` code are preserved.
- `logs/review.jsonl`: `amount`, `category`, `spent`, `total` are `None`; `call_id`, `request_id`,
  the safe `error` code and `review` are preserved. The key set stays exactly eight keys.
- The ledger (`data/records.jsonl`) keeps the real validated values; it is never redacted.
- Public `StorageError` messages carry field/type names only — no paths, raw `OSError` text,
  amounts, category, spend or totals. `raise ... from exc` is kept where the cause is inspected.

---

## 3. Known limitations *(derived — proposed)*

- **Review append is not atomic.** `logs/review.jsonl` uses a plain append; a crash mid-write can
  leave a partial line. This is evidence, not state, and does not affect the ledger's atomic
  commit point (ADR-003).
- **The private marker is not a hard security boundary.** `_PIPELINE_ORIGIN` is module-private by
  convention only; in-process code that deliberately imports it can select the pipeline path. It
  prevents accidental misuse, not a determined in-process caller.
- **Two reads, one authority.** The pipeline pre-check and the locked re-read are separate; only the
  locked value is authoritative, so a concurrent commit between them cannot cause an over-budget
  write, but the pre-check exists only to fail fast on obvious rejections.

---

## 4. Consequences

- INV-003 is decided deterministically against persisted state; a stale caller `spent` is inert.
- Audit logs are safe to commit; the ledger retains real values for the runtime contract.
- No public API flag exposes the internal path; the direct API contract is stable.
