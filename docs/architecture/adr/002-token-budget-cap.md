# ADR-002 — Token Budget Cap

- **Status:** Accepted as a **design-only** decision on the *shape* of token governance.
  **Not yet verified as implemented.** The budget cap **value is Pending PD-007** and is not set
  by this ADR.
- **Owner:** Role B (requirements & architecture). Behaviour-at-limit that touches policy is
  recorded as *pending confirmation* (owner B with C); this ADR does **not** approve PD-007 or
  PD-008.
- **Date:** Phase 2 (Issue #13).
- **Related:** `architecture-blueprint.md` §8 (Token Compression Strategy); ADR-001 (AI Layered
  Context Structure); `docs/req/requirements.yaml` NFR-002 (Token consumption), NFR-001
  (latency), PD-007; `docs/architecture/trace-matrix.md` §2.2 (NFR-002 row).

> **Reading this document.** Sections labelled *(source)* restate existing material or verified
> code facts. Sections labelled *(derived — proposed)* are design reasoning, not
> implementation/measurement claims. **No numeric token ceiling or budget is chosen here** —
> every number is **Pending PD-007**.

---

## 1. Context

### 1.1 Why token governance is needed *(source)*
Context is finite and paid for; unbounded history increases cost and dilutes the instructions
(`architecture-blueprint.md` §8). The system already captures per-call token usage from the
gateway response on D's **unmerged** branch (`feat/D-phase2-measurement`), summarised by
per-request/per-session statistics with a three-state `usage_source` (gateway/partial/missing)
and `incomplete` marking for sessions with missing usage. That is **statistics only** — it
records where tokens went; it does **not** impose a ceiling. *(Source: `requirements.yaml`
NFR-002; trace-matrix NFR-002 row.)*

### 1.2 What is fixed by the architecture *(source)*
- Business safety rules live in `policy_core`, **not** the prompt, so token pressure **cannot
  relax a safety rule** — the protection is architectural (`architecture-blueprint.md` §8;
  AI-REQ-005).
- The static system prompt **must never be dropped below its full form** because it defines the
  output contract (blueprint §8; ADR-001 R4).
- There is **no** compression/budget code today; at-limit behaviour is a design proposal
  (blueprint §8; ADR-001 §2 status).

### 1.3 The problem this ADR frames *(derived — proposed)*
Given that usage is measurable and that some context (history, future class-2/3 injection) could
grow, the architecture needs a principled answer to: **what is allowed to grow, what must be
preserved, and what the system does when a (future) budget is reached** — decided *now* at the
design level, while leaving the numeric cap to PD-007.

---

## 2. Decision

*(derived — proposed; consistent with blueprint §8)*

Adopt a **"cap optional context, never the output contract"** token-budget policy:

- **B1 (what is capped):** the *token budget* applies to **optional** context — carried history
  and any future project-file/requirement injection (ADR-001 classes 2 + history). The static
  system prompt (class 1) and its output-contract requirements (class 5) are **excluded from
  reduction**.
- **B2 (what is never reduced):** the system prompt is never truncated below its full form;
  safety rules are never in the prompt, so they are never "protected by budget" — they are
  protected by code.
- **B3 (at-limit behaviour — proposed):** when a budget is reached, the safe default is to
  **truncate optional context first** (history, then project files) and never the system
  instructions, then parse as usual. This is a **design proposal, not current behaviour**
  (blueprint §8).
- **B4 (governance of the number):** the actual ceilings —
  **per-request token ceiling**, **per-session token budget**, **max carried history**, and
  **behaviour at limit (truncate/reject/retry)** — are all **Pending PD-007** (owner B; behaviour
  with C). This ADR fixes the *shape*, not the *values*.

Status: **Design-only / not yet verified as implemented.** No cap, compression, or at-limit
logic exists in the codebase; the only related code (D's token statistics) is **unmerged** and
does not enforce any ceiling.

---

## 3. Alternatives

*(derived — proposed; evaluated against the drivers in §4)*

| Alt | Description | Why not chosen (for this system) |
|---|---|---|
| A. No budget at all | Never cap; include whatever context arises. | Unbounded cost/dilution (blueprint §8). Leaves QA2 (cost) unmanaged. Rejected as a *policy*, though it is the current de-facto state. |
| B. Hard-truncate everything on overflow (incl. system prompt) | Trim earliest tokens to fit. | Could cut the output contract → breaks AI-REQ-006/output validity and ADR-001 R4. Rejected. |
| C. Reject the call when over budget | Error out above the cap. | Turns a cost concern into a user-visible failure; availability trade-off (QA) and no agreed semantics. Rejected as default (behaviour-at-limit is Pending PD-007 anyway). |
| D. Retry with a shorter prompt | On overflow, re-call with reduced context. | Extra latency/cost and must preserve contract; semantics not agreed (Pending PD-007). Rejected as default. |
| **E. Cap optional context, preserve output contract, truncate optional first** | Budget bounds history/optional classes; system prompt fixed; truncate optional first. | **Chosen.** Preserves safety and contract regardless of the numeric cap; defers the number to PD-007. |

---

## 4. Multi-round ADD design process

> **Honesty note.** Project material records **no** prior ADD rounds or experiments for token
> budgeting, and **no measured token ceiling**. The rounds below are the design reasoning this
> ADR documents now, grounded in the cited blueprint/requirements lines. They are **reasoning**,
> not experiments, and assert **no** measurement, approval, or deployed behaviour.

### 4.1 Round 0 — Quality-attribute drivers and constraints
- **QA1 Safety independence:** cap must not weaken safety; safety lives in code, not prompt
  *(blueprint §8; AI-REQ-005).*
- **QA2 Cost control:** token growth must be boundable — the reason the ADR exists *(blueprint
  §8)*; the *target* is NFR-002, **threshold Pending PD-007**.
- **QA3 Contract integrity:** output contract (class 5) must survive any reduction *(ADR-001 R4;
  AI-REQ-006).*
- **QA4 Observability:** usage is already measured per call *(NFR-002; D unmerged branch —
  statistics only)*, enabling a future cap to be validated.
- **Constraints:** no compression code today; statistics are `usage_source` three-state, missing
  never zero-filled; latency is NFR-001 (**Pending PD-007**) and retry policy is **PD-008** (C).

### 4.2 Round 1 — Candidate A: manage nothing
Baseline (Alternative A) matches the current de-facto behaviour but **fails QA2** (no cost
bound) and leaves at-limit behaviour undefined. → *iterated*.

### 4.3 Round 2 — Candidate B: truncate everything
Simplest hard cap (Alternative B) satisfies QA2 but **fails QA3** by risking the system prompt /
output contract. Unacceptable for a system whose output must validate. → *iterated*.

### 4.4 Round 3 — Separate "optional" from "contract"
Split context into *optional* (history, future classes 2/files) and *non-reducible* (class 1/5).
This satisfies QA3 (contract preserved) and QA1 (safety stays in code), while allowing QA2 to be
enforced on optional context only. Surfaced the *value* question → deliberately left to PD-007.
**Accepted as the structural decision.**

### 4.5 Round 4 — At-limit semantics and verification hook
For at-limit behaviour, compared truncate-first (E) against reject (C) and retry (D). Chose
**truncate optional first** as the safe default *proposal*, explicitly **not implemented** and
**subject to PD-007** (behaviour with C). Noted that NFR-002's per-call/per-session statistics
(once D merges and E produces committed evidence) are the future verification hook — **no such
committed evidence exists today** *(trace-matrix NFR-002: runtime-evidence-pending)*.

---

## 5. Consequences

### Positive
- Safety and the output contract are **independent of the token cap** (QA1/QA3).
- A future numeric cap (PD-007) can be introduced **without** redesigning safety semantics.
- Usage observability already exists as a measurement basis *(NFR-002, D unmerged)*.

### Negative / costs
- Until PD-007 sets values, there is **no enforced cap** — cost is observable but not bounded.
- Truncate-first is only *proposed*; its correctness (e.g., mid-record truncation) must be
  validated when it is implemented — **not verified now**.
- Adds future complexity at the `call_llm` seam (assembly/selection from ADR-001 + budget).

### Neutral / out of scope
- The numeric ceilings, history cap, and exact at-limit algorithm are **not** decided here.
- Retry-on-overflow interacts with **PD-008 (owner C)** and NFR-001 latency (**PD-007**); not
  decided here.

---

## 6. Open questions and pending confirmations

| Item | Status | Owner |
|---|---|---|
| Per-request token ceiling (value) | **Pending PD-007** | B |
| Per-session token budget (value) | **Pending PD-007** | B |
| Max carried history length | **Pending PD-007** | B |
| Behaviour at limit (truncate/reject/retry) | **Pending PD-007** | B with C |
| Retry-on-overflow policy | **Pending PD-008** | C |
| Independent, committed token-run evidence | runtime-evidence-pending | E (after D merges) |
| `user_request_count` metric (if wanted) | pending, unimplemented | D (on B confirmation) |

> This ADR fixes the *shape* of token governance and **does not** choose any number. It does
> **not** approve PD-007/PD-008 and does **not** assert the design is deployed, measured, or
> tested. **Design-only / not yet verified as implemented.**
