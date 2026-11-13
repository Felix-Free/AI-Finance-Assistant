# Memory Design — How Context and Persistence Work Today (owner: role D)

> Purpose: describe **how context and memory work in this system as built today** — what is
> persisted, where, what the model sees, and what is deliberately not kept. This document
> describes the mechanism only; it does not restate generic LLM theory.
>
> Status: Phase 2 · role D. Every claim below is checkable against the named source file.
> Role B's architecture blueprint may reference this document; the mechanism lives here.
>
> Locked contracts this document respects (not re-opened here):
> - `logs/llm_calls.jsonl` lines carry exactly ten keys:
>   `input, raw, parsed, error, call_id, request_id, session_id, tokens, usage_source,
>   request_made` (`src/call_llm.py::extract`).
> - `data/records.jsonl` records carry exactly six fields:
>   `call_id, amount, category, total, budget_limit, decided_at` (`src/storage.py`).
> - Identifiers: `session_id` once per process, `request_id` once per `process()` call,
>   `call_id` once per API call; all `uuid.uuid4().hex` (`src/call_llm.py`).

---

## 1. Scope and non-goals

This system has no conversational memory. One `process()` call takes one sentence, makes one
model call, validates once, and persists at most one record. "Memory" here means **files on
disk**, written by the pipeline and read back by a deterministic guard — not state carried by
the model.

What is kept:

- The **record log** — validated spending records, append-only (`data/records.jsonl`).
- The **call log** — one line per model call, for audit and token measurement
  (`logs/llm_calls.jsonl`).
- The **rejection log** — one line per policy rejection, for human review (`logs/review.jsonl`).

What is deliberately **not** kept, one sentence each so it can be cited:

- No conversation history is stored; each `process()` call is independent of every prior one.
- No user profiles are stored; the system knows nothing about the user across calls.
- No embeddings are computed or stored; text is never vectorised.
- No vector store exists; there is no database to retrieve from.
- No cross-session memory exists; a new process starts with no knowledge of earlier processes.
- No retriever or summariser runs; no past text is ever fed back into a later call.

---

## 2. What is persisted, and where

| artefact | path | written by | lifetime | contains |
|---|---|---|---|---|
| Record log | `data/records.jsonl` | `src/storage.py::append_validated` | persistent; append-only | one validated record per line: `call_id, amount, category, total, budget_limit, decided_at` |
| Call log | `logs/llm_calls.jsonl` | `src/call_llm.py::_append_log` | per run; append-only | one line per call: `input, raw, parsed, error, call_id, request_id, session_id, tokens, usage_source, request_made` |
| Rejection log | `logs/review.jsonl` | `src/pipeline.py::_append_rejection` | per run; append-only | one line per rejection: `call_id, request_id, error, amount, category, spent, total, review` |

`data/records.jsonl` is the only durable memory. The two logs under `logs/` are operational
evidence: the call log proves a call happened and how it finished; the rejection log proves a
record was refused. A rejection never writes to `data/records.jsonl`.

---

## 3. Context assembly (what the model sees, exactly)

Each model call sends exactly two messages:

- A **system message** — the constant `SYSTEM_PROMPT` in `src/call_llm.py`, which instructs the
  model to return one JSON object with `amount` and `category`, or `{"error": "not_a_record"}`.
- A **user message** — the raw sentence passed to `process()`, unchanged.

There is no history, no few-shot example set, and no retrieval. Context per call is therefore
`SYSTEM_PROMPT + one sentence`, and nothing else. This is constant for every call in every
process.

This is a **decision, not an omission**: the model's only job is extraction — turning one sentence
into candidate `amount` / `category` values. All judgement (is the amount positive, is the
category allowed, is the budget exceeded) is performed in code by `src/policy_core.py`, never by
the model. Keeping context minimal makes the model's output small and easy to re-check.

The consequence is structural: memory cannot make a decision wrong, because no decision reads
memory. The only memory a decision reads is the running spend total, and that is read through
`storage.current_total()` and enforced by `enforce_budget`, not by the model.

---

## 4. If context ever grows (the policy we would adopt)

This is a forward-looking policy, not current behaviour. Today the model sees one sentence
(§3). If a future version needs the model to see prior sentences, the following rule applies.

- **Where compression would sit:** a new module that runs *before* `call_llm.extract`, assembling
  prior context into the user message. It must never live inside `src/policy_core.py`; the
  policy core performs no IO and reads no history.
- **What it may do:** summarise past sentences into a short prefix.
- **What it may not do:** summarise away a rejection, or delete evidence. A rejection stays in
  `logs/review.jsonl` regardless of what any summary says.

The invariant that keeps this safe:

> A summary is an input to extraction, never an input to a decision; every extracted value is still re-validated by policy_core.

**Failure mode:** if compression fails, proceed with **no history** (today's behaviour), not
with a partial summary, and log the degradation. A partial summary is treated as no summary,
because a half-context is harder to reason about than none.

---

## 5. Traceability: how a decision is reconstructed

Every accepted decision is reconstructible from field names alone, following the id chain:

```
session_id → request_id → call_id → records row
```

A rejection is reconstructible as `call_id → review row`, with no record.

### Illustrative example (values chosen to satisfy the schema, not a real logged run)

Take the sentence `"hotpot last night cost 350"`, processed inside one session.

1. **Call line** (`logs/llm_calls.jsonl`) — carries `session_id`, `request_id`, `call_id`, and a
   `tokens` object; a successful call has `request_made: true`, `usage_source: "gateway"`.
2. **Record row** (`data/records.jsonl`) — carries the same `call_id`, plus
   `amount: 350`, `category: "food"`, `total: <updated running total>`, `budget_limit`, and
   `decided_at` (ISO-8601 UTC, seconds).
3. **Joining them:** the same `call_id` appears in the call line and in the record row.

NFR-006 names **two log files** (`logs/llm_calls.jsonl`, `logs/review.jsonl`). The traceability rule
agreed with role C on 2026-11-12 adds a third **evidence record**, the storage row:

`(a)` the call-log line, `(b)` the storage record, `(c)` the rejection line.

For an accepted record, `(a)` and `(b)` match. For a rejection, `(a)` and `(c)` match and `(b)` is
absent. So "three positions" means three evidence records, not three files named in NFR-006.

A rejection leaves **no record, only evidence**. This is intentional: a rejected value never
affects stored data, so there is nothing to persist as state — only the proof that it was
refused, which lives in `logs/review.jsonl`.

---

## 6. Failure modes and degradation

Each failure is mapped to the symbol that enforces it, not to a section of a specification.

| failure | today's behaviour | enforced by |
|---|---|---|
| Call-log write failure | the call's result is not used; an error is raised (fail-closed) | `src/call_llm.py::_append_log` |
| Storage write failure | the write raises and propagates; no fake success | `src/storage.py::append_validated` / `StorageError` |
| Non-JSON model response | logged with `error="not_json"`, then `JSONDecodeError` re-raised | `src/call_llm.py::extract` |
| Missing credentials | logged with `request_made=false`, then `LlmTransportError` raised | `src/call_llm.py::extract` |
| Budget rejection | a review line is written, no record is stored, `PolicyError` re-raised | `src/pipeline.py::process` |

In every row, the degradation keeps the invariant that stored data only ever reflects a record
that passed `policy_core`; failures leave the record log unchanged and surface as evidence.
