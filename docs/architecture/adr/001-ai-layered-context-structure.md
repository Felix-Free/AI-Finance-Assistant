# ADR-001 — AI Layered Context Structure

- **Status:** Accepted as a **design-only** decision. **Not yet verified as implemented.**
  Current code sends only a static system prompt + the user sentence; no layered assembly or
  project-file injection exists today.
- **Owner:** Role B (requirements & architecture). Policy content that touches role C is
  recorded here as *pending confirmation* and is **not** approved by this ADR.
- **Date:** Phase 2 (Issue #13).
- **Related:** `architecture-blueprint.md` §7 (AI Context Assembly Pipeline), §9 (Prompt
  Injection Defense); `docs/req/requirements.yaml` (AI-REQ-001/002/003/005/006, NFR-002);
  `docs/architecture/trace-matrix.md` §2.2 / §2.4.

> **Reading this document.** Sections labelled *(source)* restate existing project material.
> Sections labelled *(derived — proposed)* are this ADR's design reasoning and are **not**
> implementation claims, experiment results, or approved decisions. Numbers are never invented
> here; the only quantity discussed (token budget) is explicitly **Pending PD-007**.

---

## 1. Context

### 1.1 What the system does with the model *(source)*
The application turns one natural-language sentence describing a purchase into one validated,
structured spending record. The model **only** parses/understands; deterministic code in
`src/policy_core.py` decides whether the record is accepted (`architecture-blueprint.md` §1, §6;
`requirements.yaml` AI-REQ-001/002). The model's output is untrusted and must pass
`validate_record` before it can affect any stored data (AI-REQ-003; SEC-003).

### 1.2 Current reality *(source)*
Only two things are sent to the model today: a static system prompt
(`call_llm.py::SYSTEM_PROMPT`) and the single user sentence, with
`response_format={"type":"json_object"}`. There is **no** history assembly and **no**
project-file injection (`architecture-blueprint.md` §7, "Current reality"). Any "layered
context structure" is therefore **design intent for later versions**, clearly marked.

### 1.3 The problem this ADR frames *(source + derived — proposed)*
As the system grows (multi-turn use, richer inputs, possible requirement/rule references), a
naive design would "dump everything" into the prompt. That raises cost and — more importantly —
risks letting low-trust text (the user sentence) sit alongside, and possibly blur into, the
trusted output contract. The architecture needs a principled answer to: **what context classes
exist, what is each one's trust level, and what may never happen** even before any assembly code
is written.

---

## 2. Decision

*(derived — proposed; consistent with blueprint §7)*

Adopt a **five-class layered context model with a hard trust boundary**, where context is
selected by relevance and business safety rules are **kept out of the prompt entirely** because
they are enforced in code:

| # | Context class | Source | Priority | Trust | Injected today? |
|---|---|---|---|---|---|
| 1 | Static System Instructions | `call_llm.py::SYSTEM_PROMPT` | highest | trusted (code-owned) | Yes |
| 2 | Approved Project Requirements | `requirements.yaml`, blueprint | high | trusted | No — not sent to model |
| 3 | Relevant Business Rules | `invariants.md` INV-001/002/003 | high | trusted | No — enforced in code, not prompt |
| 4 | User Input | the sentence | lowest | **untrusted** | Yes (as a `user` message) |
| 5 | Structured Output Requirements | system prompt + `response_format` json_object | high | trusted (code-owned) | Yes |

Load-bearing rules of the decision:
- **R1 (selection):** include only context relevant to the current record; never dump the whole
  transcript or repository *(blueprint §7 selection principle)*.
- **R2 (trust boundary):** classes 1/2/3/5 are trusted and code-owned; class 4 is untrusted and
  must remain **subordinate to class 1** *(blueprint §7 trust boundary)*.
- **R3 (safety is not prompt text):** business rules are enforced by `policy_core`, so they do
  not need to be injected and must not be relied on as prompt text *(blueprint §6/§7; AI-REQ-005)*.
- **R4 (output contract is fixed):** class 5 defines the JSON output contract; class 4 must never
  be able to redefine it *(blueprint §9)*.

Status: **Design-only / not yet verified as implemented.** No assembly pipeline, selection
logic, or class-2/3 injection exists in the codebase.

---

## 3. Alternatives

*(derived — proposed; evaluated against the drivers in §4)*

| Alt | Description | Why not chosen (for this system) |
|---|---|---|
| A. Flat prompt (everything concatenated) | Put system prompt, rules, history, user text into one blob. | Blurs the trust boundary; lets untrusted class-4 text touch class-1/5 semantics. High prompt-injection and cost risk. Rejected. |
| B. Inject business rules as prompt text | Send INV-001/002/003 to the model and ask it to apply them. | Violates "model proposes, code disposes" (AI-REQ-002/005; blueprint §6). Safety would depend on model compliance and token budget. Rejected. |
| C. Full conversation history by default | Carry all prior turns/records each call. | Unbounded cost, dilutes instructions (blueprint §8 rationale). Violates relevance selection (R1). Rejected. |
| **D. Layered, relevance-selected, rules-in-code** | Five classes with the trust boundary; rules kept in code; only relevant context included. | **Chosen.** Preserves trust separation and keeps safety independent of prompt/token pressure. |
| E. Trusted-only context (drop class 4 entirely) | Never send the user sentence; infer from side data. | The whole product parses the user sentence; cannot drop it. Rejected. |

---

## 4. Multi-round ADD design process

> **Honesty note.** The project material does **not** record prior ADD rounds or experiment
> results. The rounds below are the **architectural reasoning this ADR documents now**, each
> grounded in the blueprint/requirements lines cited. They are **design reasoning, not run
> experiments**, and carry no approval/measurement claim.

### 4.1 Round 0 — Quality-attribute drivers and constraints
- **QA1 Trust integrity:** untrusted input must not alter the output contract or safety outcome
  *(requires AI-REQ-005; blueprint §9).*
- **QA2 Cost/token pressure:** context is finite and paid for *(blueprint §8 rationale)*; any
  growth must be controllable (ties to NFR-002, **threshold Pending PD-007**).
- **QA3 Determinism/safety:** acceptance is decided by code, not the prompt *(AI-REQ-002/003;
  blueprint §6).*
- **QA4 Evolvability:** the model call is a single seam (`call_llm.extract`), so context assembly
  can be added later without touching safety code *(structural-constraints; trace-matrix FR-001).*
- **Design constraints:** model output is untrusted (SEC-003); every call is logged once
  (FR-008); rules live in code (AI-REQ-005); the category whitelist and budget are code-defined
  (INV-002/003, INV-PENDING-01 — finality confirmed by C on 2026-11-19; previously pending PD-002).

### 4.2 Round 1 — First candidate: flat prompt
Tried the simplest model (Alternative A). It satisfies QA4 trivially but **fails QA1** (trust
boundary absent) and **worsens QA2** (everything always sent). → *iterated*.

### 4.3 Round 2 — Rule-in-prompt variant
To "keep the model honest," tried sending the invariants as prompt text (Alternative B). This
**fails QA3**: it moves safety from `policy_core` into the model, contradicting the core
principle and making safety depend on token budget (QA2). → *iterated*.

### 4.4 Round 3 — Trust-class separation
Separated context into five classes with explicit priority/trust (§2 table). This satisfies QA1
(class 4 subordinate to class 1; class 5 fixed) and keeps QA3 intact by **not** injecting rules
(they stay in code). Open question surfaced: what to do when optional classes (2/3, history) grow
→ deferred to ADR-002 (token budget). **Accepted as the structural decision.**

### 4.5 Round 4 — Verify against current code, mark gaps
Checked the decision against reality: only classes 1/4/5 are injected today; classes 2/3 are
"not sent" / "enforced in code." Therefore the layered structure is **design-only**, and its
selection/injection logic is **unimplemented**. Remaining gaps recorded in §6.

---

## 5. Consequences

### Positive
- **Trust boundary is explicit** and independent of how much context is later added (R2/R4).
- **Safety cannot be relaxed by prompt or token pressure** because rules are in code (R3; QA3).
- **Evolvable:** assembly can be added inside the `call_llm` seam without touching
  `policy_core` (QA4).

### Negative / costs
- Any future assembly must re-prove the trust boundary and selection rule; added complexity
  lives in the model-client seam.
- Classes 2/3 being "not sent" means their value to parsing is currently zero — a deliberate
  safety-over-recall trade-off.
- Token-growth behaviour is **not** decided here; it depends on ADR-002 and **PD-007**.

### Neutral / out of scope
- Concrete selection algorithms, history caps, and at-limit behaviour are **not** decided in
  this ADR (design-only; see ADR-002).
- Category vocabulary finality was **INV-PENDING-01 / PD-002 (owner C)** at the time this ADR was
  written (not decided here); it was later **confirmed by C on 2026-11-19** (final 8-category whitelist).

---

## 6. Open questions and pending confirmations

| Item | Status | Owner |
|---|---|---|
| Whether/when classes 2/3 are ever injected | pending (design intent only) | B |
| Selection algorithm for class 4 vs history | pending | B |
| Token-budget interactions of larger context | pending — **PD-007** | B/C (see ADR-002) |
| Category whitelist finality referenced by class 3 | confirmed by C on 2026-11-19 (final 8-category whitelist; was PD-002) | C |
| Any prompt-injection escaping beyond structural separation (blueprint §9 "Partial") | pending / not implemented | C/B |

> This ADR does **not** approve PD-007/PD-008 and does **not** assert the design is deployed or
> tested. It is **design-only / not yet verified as implemented**.
