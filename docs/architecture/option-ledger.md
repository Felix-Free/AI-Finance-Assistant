# Option Ledger (owner: role B)

> Records the design options considered across Phase 2 (Issue #13), the option selected (if any),
> and its status. Sources are **current `main`** (`8d0251a`), where the Phase 2 D/C/E branches have
> since been **merged**: D via PR #18 (`f2442c2`), C via PR #19 (`c71610c`), E via PR #20 (`064acc5`).
> **Branch state verified as of 2026-11-21**; the SHAs are review-time identifiers, not a claim of
> being permanently current.
>
> **Status vocabulary** (each OPT uses exactly one):
> - **Selected** — chosen and recorded (design level; may still be unmerged/unverified in code).
> - **Proposed** — a recommended option not yet decided/approved.
> - **Pending Confirmation** — depends on a named owning role/decision (PD-xxx).
> - **Deferred** — intentionally postponed.
>
> This ledger does **not** approve PD-007/PD-008, does **not** decide whether `user_request_count`
> is added (that is B with D), and does **not** claim unmerged code is on `main`.

---

## Ledger

| Option ID | Decision Area | Alternatives | Selected Option (if any) | Rationale | Status | Decision Owner | Evidence / Source |
|---|---|---|---|---|---|---|---|
| OPT-001 | Retry Policy (transport/HTTP failure) | (a) fail fast, no retry; (b) bounded retry; (c) retry with backoff | (a) fail fast — current behaviour: at most one attempt, `LlmTransportError` surfaced after logging | Keep the failure deterministic; no retry code exists. Bounded-vs-none is a policy choice not yet approved. | Pending Confirmation (PD-008) | C | `requirements.yaml` NFR-003 (PD-008); `src/call_llm.py::_post` single attempt; ADR-002 §3 (retry-on-overflow deferred). |
| OPT-002 | Token Usage Aggregation | (a) none; (b) per-session only; (c) per-request + per-session + counters + usage-source distribution + missing count; (d) add `user_request_count` now | (c) as implemented on `main` (merged via PR #18): per-request (request_id), per-session (session_id), `api_call_count` (`request_made=true`), `usage_source` three-state (gateway/partial/missing), missing-usage count, `incomplete` sessions; missing never zero-filled | Descriptive statistics only; source is the gateway `usage` object (`prompt/completion/total_tokens`). `user_request_count` (d) deliberately not added. | Selected (design) — code on `main`; `user_request_count` Pending Confirmation | B (metric) / D (impl) | `requirements.yaml` NFR-002; `src/report_tokens.py`, `src/call_llm.py` (on `main`). |
| OPT-003 | Token Budget Cap (numeric) | (a) no cap; (b) cap-all incl. system prompt; (c) reject on overflow; (d) retry-shorter; (e) cap optional context, preserve output contract, truncate optional first | (e) as design shape in ADR-002; **no numeric value chosen** | Safety/output-contract must survive any cap; the value is not yet approved. | Pending Confirmation (PD-007) | B (value) / B+C (at-limit behaviour) | ADR-002 §2/§6; `requirements.yaml` NFR-002 (PD-007); `architecture-blueprint.md` §8. |
| OPT-004 | JSONL Evidence Logging | (a) single combined log; (b) separate `llm_calls.jsonl` (one line per call) + `review.jsonl` (one line per rejection) + `records.jsonl` (accepted) | (b) separate files; `llm_calls` one line/call (RP-004), `review` one line/rejection, `records` accepted only | Keeps the audit trail for calls and rejections distinct and fail-closed; rejected records never enter storage. | Selected (design); implemented on `main` (call/review/records; join tests on `main`) | C (contract) / D (impl) | `requirements.yaml` FR-008, NFR-006; `runtime-policy-catalog.md` RP-004; `src/pipeline.py`, `src/storage.py` (on `main`); `test/offline/test_evidence_join.py` (on `main`). |
| OPT-005 | Storage Fields (accepted record schema) | (a) minimal {amount, category, total}; (b) add budget/decision metadata; (c) also persist token/usage fields | (b) six fields: `call_id`, `amount`, `category`, `total`, `budget_limit`, `decided_at` — on `main` (merged via PR #18) | Enough to re-check INV-003 (`budget_limit`, `total`), trace via `call_id`, and timestamp the decision; token stats are kept in logs, not storage (c). | Selected (design) — on `main` | D | `src/storage.py` `REQUIRED_FIELDS`; OPT-002 (token stats live in logs); trace-matrix FR-008/NFR-006. |
| OPT-006 | call_id Evidence Association | (a) no correlation id; (b) `call_id` shared across logs/records; (c) add `request_id`/`session_id` too | (b)+(c) on `main` (merged via PR #18): `call_id` joins accepted (`llm_calls↔records`) and rejected (`llm_calls↔review`); `request_id`/`session_id` added for token aggregation | Lets each outcome be traced to its call; rejected rows never enter storage. Join tests are now on `main` (`test/offline/test_evidence_join.py`, 10 offline tests, 0 skipped; merged via PR #20). | Selected (design) — on `main`; verified by tests | D / E | `requirements.yaml` NFR-006; `src/call_llm.py`, `src/pipeline.py`, `src/storage.py`; `test/offline/test_evidence_join.py` (on `main`). |
| OPT-007 | AI Layered Context Structure | (a) flat prompt; (b) inject rules as prompt text; (c) full history by default; (d) five-class layered, rules-in-code, relevance-selected; (e) trusted-only (drop user input) | (d) five context classes with a hard trust boundary; business rules kept in code, not prompt | Preserves trust separation and keeps safety independent of prompt/token pressure; matches "model proposes, code disposes". Design-only; assembly not implemented. | Selected (design, ADR-001) — not yet verified as implemented | B | ADR-001 §2/§4; `architecture-blueprint.md` §7/§9; AI-REQ-002/005; trace-matrix §2.4. |

---

## Reconsideration Triggers

Each trigger states what concrete, observable change would make the team **re-examine** the option
(not an automatic change of architecture — a human still re-analyses and decides). Triggers are tied
to the current option, its status, and the real code/requirements; they do **not** assert a future
decision has been made.

- **OPT-001 (Retry / fail-fast, Pending PD-008)** — Reconsider when PD-008 is confirmed by C; **or**
  committed evidence shows transient transport failures cause user-visible failures that fail an
  approved reliability requirement; **or** a reliability requirement is added that a single attempt
  cannot meet. Any retry proposal must also be weighed against duplicate-call / cost side effects
  (`src/call_llm.py::_post` currently makes one attempt, no retry loop).
- **OPT-002 (Token aggregation, Selected; `user_request_count` Pending)** — Reconsider when
  `user_request_count` (distinct `request_id`) becomes a requirement or is implemented (a
  `git grep user_request_count` hit under `src/`/`test/`); **or** an approved reporting/analysis
  requirement cannot be satisfied by the current per-request/per-session/`usage_source` grouping;
  **or** the usage-source mapping (gateway/partial/missing) changes.
- **OPT-003 (Token budget cap shape, Pending PD-007)** — Reconsider when PD-007 is confirmed (a
  numeric cap/threshold is approved in `requirements.yaml`); **or** committed token measurements show
  the “cap optional context / truncate-first” shape cannot meet an approved budget; **or** a new
  cost/token-limit requirement appears. No numeric threshold exists today (NFR-002 `threshold: null`).
- **OPT-004 (JSONL file strategy, Selected)** — Reconsider when a requirement needs capabilities the
  current append-only files cannot provide (transactional multi-file guarantees, indexed queries, or
  concurrent multi-writer semantics beyond the current lock+atomic-append in `src/storage.py`
  / ADR-003); **or** measured data volume/usage makes the file strategy unsuitable.
- **OPT-005 (Storage schema = six fields, Selected)** — Reconsider when an approved change adds/removes
  a persisted field (schema evolution), **or** a new integrity/compat requirement exceeds what
  `append_validated`/`validate_record` currently check (current fields: `call_id, amount, category,
  total, budget_limit, decided_at`).
- **OPT-006 (call_id correlation, Selected; verified by tests)** — Reconsider when call/request
  correlation fails in real tests or data analysis; **or** a new traceability requirement changes the
  `call_id`/`request_id`/`session_id` scope or cross-log joining needs; **or** the current join
  (`llm_calls↔records`, `llm_calls↔review`) no longer satisfies analysis needs.
- **OPT-007 (Layered context structure, Selected design-only)** — Reconsider when committed
  measurements show the layered/“rules-in-code” context cannot meet an approved token budget (PD-007);
  **or** a new reliability/security/traceability/maintainability requirement changes the context
  priority or assembly strategy; **or** ADR-001’s five-class trust boundary is shown insufficient by
  concrete evidence. (ADR-001 is design-only; assembly is not implemented.)

---

## Notes and non-claims

- **Status distinction:** `Selected` means a design choice is recorded, **not** that the code is
  approved or verified. The Phase 2 D/C/E work referenced above is now merged on `main`; residual
  verification gaps (runtime measurement evidence; PD-007/PD-008 decisions) remain as noted.
- `user_request_count` (OPT-002 alt d) is **not** decided here; adding it requires B's metric
  decision plus D's implementation.
- **PD-007** (OPT-003 values, token budgets) and **PD-008** (OPT-001 retry) remain
  `pending_confirmation` — this ledger records options, not approvals.
- Related: `risk-list.md` RISK-001…008; ADR-001, ADR-002; `requirements.yaml` NFR-001/002/003/006;
  `trace-matrix.md` §1.3 status labels.
