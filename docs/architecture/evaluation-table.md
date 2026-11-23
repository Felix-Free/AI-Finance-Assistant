# Evaluation Table — Architecture Options (owner: role B)

> Purpose: a course deliverable (project directory item `docs/architecture/evaluation-table.md`) that
> shows **how candidate architectures were compared and why one was selected**. It is grounded in the
> existing requirements (`docs/req/requirements.yaml`), the architecture decisions ADR-001 and ADR-002,
> and `option-ledger.md` / `risk-list.md` / `trace-matrix.md`.
>
> **Evidence discipline.** This table separates three things that must not be confused:
> **design judgement** (architectural reasoning), **existing implementation** (what is on `main`), and
> **actual test/measurement evidence** (committed, reproducible). Where reliable numeric evidence does
> not exist, the comparison is **qualitative** and marked `Pending Validation` — no numeric scores are
> invented. This table does **not** claim any design is implemented or verified unless a committed
> artifact supports it.
>
> The course PDF lists `evaluation-table.md` as a deliverable but does **not** prescribe a specific
> scoring scheme; the criteria/structure below are this project's own, not quoted PDF requirements.

---

## 1. Purpose

Select a single, defensible architecture for the AI Finance Assistant — *model parses, deterministic
code decides* — by comparing realistic candidates against quality-attribute criteria, and record the
trade-offs and residual evidence gaps. This document is the rationale companion to ADR-001 (AI layered
context) and ADR-002 (token budget).

## 2. Evaluation Criteria

Each criterion is tied to an existing requirement or decision where possible. Importance is stated
qualitatively (no invented weights).

| Criterion | Why it matters | Linked requirements / decisions |
|---|---|---|
| Reliability | The system must reject illegal data deterministically and never fabricate a record. | FR-002/003/007, AI-REQ-002/003/006, INV-001/002/003; `runtime-policy-catalog.md` |
| Security | Secrets must never leak; the model output is untrusted; prompt text must not enforce safety. | SEC-001..005, AI-REQ-005, INV-003; ADR-001 trust boundary |
| Token Cost | Context is finite and paid for; unbounded history raises cost and dilutes instructions. | NFR-002, PD-007; ADR-002 |
| Maintainability | The model call is one seam; rules live in code; adding features must not touch safety logic. | FR-001/008, AI-REQ-005; `structural-constraints.md` |
| Testability | Every invariant needs an offline, network-free negative test that fails if the guard is removed. | NFR-007; INV-001/002/003; trace-matrix §2.3 |
| Traceability | Each call/rejection outcome must be joinable to its call line; one log line per call. | NFR-006, FR-008, ERR-005; RP-004 |

## 3. Candidate Architectures

Only realistic candidates that the project actually considered are listed (see `option-ledger.md` for
the option-level record). None is invented for this table.

| Candidate | Summary | Where it comes from |
|---|---|---|
| **A. Monolithic LLM-decides** | Model returns both the parsed record *and* the decision (accept/reject). | Rejected in design reasoning (violates AI-REQ-002 "model proposes, code disposes"). |
| **B. Parse-only model + deterministic policy core** | Model parses NL → structured fields; `policy_core` enforces all invariants in code. | **Selected.** This is the current `main` architecture. |
| **C. Layered context + token budget (extension of B)** | B plus a designed five-class context model (ADR-001) and a designed token-budget policy (ADR-002). | **Selected as design direction**; assembly/budget are design-only, not implemented. |

Candidates A and B are compared in §4; candidate C is the forward-looking evolution of B and is
assessed as **design-level** only.

## 4. Comparative Evaluation

### 4.1 Candidate A vs Candidate B (by criterion)

| Criterion | A. LLM-decides | B. Parse + policy core (selected) | Evidence basis |
|---|---|---|---|
| Reliability | Weak: correctness depends on model compliance. | Strong: invariants enforced in code; illegal data rejected deterministically. | Design + `main` code `src/policy_core.py`; INV tests on `main` (trace-matrix §2.3). |
| Security | Weak: prompt text would carry safety; untrusted output could decide acceptance. | Strong: safety in code, not prompt; output untrusted until `validate_record`. | Design; SEC-003 path on `main`; ADR-001 trust boundary. |
| Token Cost | Neutral/unknown. | Neutral at present (only system prompt + sentence sent). | `architecture-blueprint.md` §7–§8. |
| Maintainability | Weak: logic fused into prompt. | Strong: one model seam + isolated guards. | `structural-constraints.md`; `main` module boundaries. |
| Testability | Weak: hard to isolate model "decisions". | Strong: guards are pure functions with offline tests. | NFR-007; `test/offline/test_policy_core_smoke.py` on `main`. |
| Traceability | Weak: mixed responsibility. | Strong: one line per call; rejection evidence separate. | NFR-006; `src/pipeline.py::_append_rejection` on `main`. |

**Outcome:** B dominates A on Reliability, Security, Maintainability, Testability, Traceability, and is
not worse on Token Cost → **B selected**. This is a design judgement backed by the `main`
implementation and its offline tests.

### 4.2 Candidate C (layered context + token budget) — design-level only

| Criterion | Expected effect of C | Status |
|---|---|---|
| Reliability | Neutral — safety already lives in code, unaffected by context layering. | Design (ADR-001) |
| Security | Neutral-to-positive — explicit trust boundary; user input stays subordinate to system prompt. | Design (ADR-001) |
| Token Cost | Positive if optional context is capped and the output contract preserved. | **Pending Validation** — no cap value (PD-007); no committed token-run evidence. |
| Maintainability | Slightly negative short-term (more assembly logic), positive long-term (evolvable seam). | Design (ADR-001/002) |
| Testability | Neutral — existing guard tests unchanged. | Design |
| Traceability | Neutral. | Design |

**Outcome:** C is **selected as the forward design direction** (ADR-001, ADR-002) with the numeric token
cap **Pending PD-007**; it is **not implemented** and **not measured**. No numeric scoring is assigned.

## 5. Selected Architecture and Rationale

**Selected: B now, evolving toward C.** The chosen architecture keeps **the model as a pure parser**
and **all business safety in deterministic code** (`src/policy_core.py`), with a single model-call seam
(`src/call_llm.py`) and an ordered pipeline (`src/pipeline.py`). Layered context (ADR-001) and a token
budget (ADR-002) are adopted **as design decisions**, deliberately leaving the numeric cap and assembly
mechanics pending (PD-007) rather than inventing values.

Rationale summary (each tied to a criterion):
- **Reliability/Security/Testability** — rules in code satisfy FR-002/003/007, SEC-003, INV-001/002/003
  and NFR-007 far better than an LLM-decides design (candidate A).
- **Maintainability** — one seam + pure guards keep the safety boundary stable as features grow.
- **Traceability** — one log line per call plus separated rejection evidence (NFR-006, FR-008).
- **Token Cost** — governed by ADR-002's *shape* (cap optional context, never the output contract),
  with the *value* pending (PD-007).

## 6. Evidence and Limitations

- **Implemented & tested on `main`:** FR-001..008 core paths, INV-001/002/003 guards, offline smoke
  tests, `_append_rejection` rejection logging (see `trace-matrix.md` §2 and §4; 36 formal requirements).
- **Design-only (not implemented):** ADR-001 context assembly/injection; ADR-002 compression/budget.
- **Merged into `main` via PR #18 (D):** `src/storage.py`, `src/report_tokens.py`,
  `scripts/measure_latency.py`, token capture, `call_id` threading, and `_append_rejection`.
- **Merged into `main` via PR #20 (E):** `test/offline/test_evidence_join.py` is on `main` and
  currently defines **17 `def test_` functions** (static code count, **not** a run result); the
  source has **no `pytest.skip`/`pytest.mark.skip`** markers, so it is no longer a skipped skeleton.
  `test/offline/test_invariants.py` statically defines **12 `def test_` functions** (also a static
  count). These are statements about the code present on `main`; **test execution / CI pass is not
  asserted here** (no run record was inspected).
- **Branch state:** verified against `origin/main` (`8d0251a`, 2026-11-21); PR #18/#19/#20 are all
  merged (D/C/E tips `df729a9`/`01e3bc7`/`cab1901` are ancestors of `main`). Online PR status was
  not re-verified this pass (no `gh`).
- **`Pending Validation`:** token-cost and latency numbers (measured in `docs/measurements/final-nfr-verification.md`, no approved budget: PD-007);
  `user_request_count` metric (not implemented); NFR-006 numeric coverage threshold (PD-008).
- **Non-claims:** no numeric score, pass rate, benchmark, or CI-run result is asserted here; a skipped
  test is never treated as passing and unmerged code is never described as `main` implementation.

## 7. Related ADRs

- **ADR-001 — AI Layered Context Structure** (`docs/architecture/adr/001-ai-layered-context-structure.md`):
  five-class context model, hard trust boundary, rules-in-code; design-only.
- **ADR-002 — Token Budget Cap** (`docs/architecture/adr/002-token-budget-cap.md`): cap optional
  context, preserve the output contract; numeric values **Pending PD-007**; design-only.
- Supporting records: `option-ledger.md` (OPT-001..007), `risk-list.md` (RISK-001..008),
  `trace-matrix.md` (36 formal requirements), `architecture-blueprint.md` §7–§9.
