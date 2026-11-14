# Verification Constraints (owner: role E)

> Purpose: state how this repository's verification evidence is produced and judged, so
> that a passing report means something specific. This is a governance document; it
> constrains claims, not code.
>
> Status: **Phase 2 (D4 QA).** Baseline: `main f73e9b4` + D #18 `eec1724` + C #19 `6808d7e`.
> It records what verification must demonstrate; results computed under a configuration
> that was not actually observed are never written as passed.

---

## 1. Four dimensions

Verification here is judged along four independent dimensions. A claim is only as strong
as the weakest dimension it relies on; a dimension that was not exercised is reported as
unverified, not as passed.

### 1.1 Test traceability

- Every offline test traces to a requirement id (`INV-###`, `NFR-###`, `RP-###`) or a named
  gap; tests with no traceable target are not treated as coverage.
- Positive and negative cases are both required. A happy-path-only suite cannot claim a
  guard is covered.
- The suite must be deterministic and network-free (`pytest test/offline -q`), and must not
  write to the repository's runtime paths (`logs/`, `data/`). Any test that mutates
  tracked or runtime state is a traceability defect, even if it passes.

### 1.2 The three invariants, as negative cases

- `INV-001` (finite positive amount, ≤ 2 decimals), `INV-002` (category in the code
  whitelist, exact match), `INV-003` (cumulative spend ≤ budget, equality allowed) must
  each have an offline negative test that **fails when its guard is removed**.
- `test/offline/test_invariants.py` isolates one negative per guard
  (`test_inv001_rejects_negative_amount`, `test_inv002_rejects_unknown_category`,
  `test_inv003_rejects_one_cent_over_budget`), so disabling one guard turns exactly that
  test red. A guard-removal run is the evidence, not the existence of the test.
- A negative test that also passes when its guard is disabled is not evidence of that
  guard.

### 1.3 Three-layer structure: structural, regression, semantic

- **Structural** — the freeze checks: single model entry point (`src/call_llm.py`), API
  shape, protected permissions, ADR present for security-critical changes
  (`.github/ci_checks.py::gate_static_analysis`, Gate 2).
- **Regression** — the full offline suite (Gate 5 / `branch-offline`): deterministic
  invariants and evidence-join wiring.
- **Semantic** — the live evaluation against the real gateway (Gate 4): spending inputs map
  to the expected `(amount, category)` and a non-expense sentence yields `not_a_record`.
  Semantic evidence requires the protected environment and a live call; it cannot be
  substituted by offline results.
- Each layer is reported separately. Passing structural and regression layers does not
  imply the semantic layer passed.

### 1.4 Real review

- Approval must be a real human, non-author, member approval on a **test-first** commit
  (implementation commits descend from it), not an AI-use-log entry
  (`.github/ci_checks.py::gate_test_approval`, Gate 1).
- A review is not "real" if it merely records that a session happened; the test-approval
  gate reads PR review state, not the log.
- Whether this gate has actually blocked a non-compliant PR on GitHub is itself a
  verification item (see §2).

---

## 2. Not to be claimed without evidence

The following are **not verified** as of this document and must not be reported as passed:

- GitHub-hosted CI execution (live run of `ci.yml` / `branch-ci.yml`).
- An end-to-end real test-first review on GitHub.
- A failing PR actually being blocked by the gates.
- Independent online evidence for performance, permissions or the runtime contract beyond
  what a local review observed.

Local offline results (deterministic suite, guard-removal runs) are reported only with the
exact command and observed output recorded alongside them.
