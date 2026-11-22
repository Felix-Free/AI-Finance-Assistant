# ADR: Phase 2 CI verification

- **Status:** Proposed
- **Owner:** role E
- **Baseline:** `main 94b0ec4` + D #18 `df729a9` + C #19 `6808d7e`

---

## Context

Phase 2 reimplemented the GitHub CI and the four test suites on top of the fixed integration
baseline. The safety model is "the model proposes, code disposes", so a merge must not be
able to land a change that bypasses the single model entry point, the deterministic policy
core, or the fail-closed logging — and it must require a real human approval, not merely an
AI-use-log entry. The question this ADR records is how CI should be organised so those
guarantees are checked on every change.

## Decision

Adopt two workflows with independent status:

- **Pull requests** (`ci.yml`): six distinct named jobs — `test-approval-loop`,
  `static-analysis`, `schema-validation`, `semantic-eval`, `offline-regression`,
  `ai-use-log`. Gate 1 verifies a real test-first approval; Gate 4 runs a live semantic
  evaluation in the protected `semantic-eval` environment and runs only when a relevant
  change is detected and Gate 1 passes. The other jobs run independently of Gate 4.
- **Pushes** (`branch-ci.yml`): `branch-static` and `branch-offline` run on every push, run
  independently of each other, and carry statuses distinct from the six PR checks.

Merge-gate logic lives in a single helper, `.github/ci_checks.py`; the workflows own
orchestration (checkout depth, test runs, model-config checks), the helper owns the gate
decisions. A non-zero helper exit fails the GitHub job; the merge is only blocked once the
six checks are configured as required checks on `main`.

A change concentrated in `src/call_llm.py` is designated **semantic**: the live evaluation
cannot be replaced by offline evidence.

## Consequences

- The six PR checks and the two push checks report separately; a failure in one does not
  silently cancel the others.
- Gate 1 depends on GitHub PR review state, so it requires a real human, non-author approval
  tied to a test-first commit; the AI-use log is a separate gate (Gate 6), not a substitute.
- Gate 4 requires the protected environment to be configured and manually approved by the
  team lead; missing config fails the job rather than skipping it.
- The helper is Python 3.9-compatible and uses only the standard library and PyYAML.

## Prerequisites and first introduction (pending team confirmation)

- **Real pre-implementation test approval** is a prerequisite: implementation work is
  expected to descend from a test-first commit that has been approved by a real reviewer.
- **First introduction:** this ADR remains `Proposed`. On 2026-11-16, role A authorized using
  `skip-test-gate` for the first rollout of PR #20 only. This is distinct from test-first
  evidence: PR #20 carrying the label is logged `Waived` by the approval gate, whereas the
  existing test-first check continues to run for all nonmatching PRs and is not relaxed. Gate 4
  still requires the protected `semantic-eval` environment to be configured and the real run to be verified. No
  GitHub run and no course exemption has been verified; GitHub verification remains pending.
- **Branch protection will be checked with a deliberately failing PR:** to confirm the
  gates actually block a bad merge, a PR containing an intended failure will be opened and
  observed to be blocked, before the gates are relied on.
- **This ADR does not claim GitHub has run these workflows.** No live GitHub execution, no
  end-to-end real test-first review, and no observed blocked PR are asserted here; those are
  outstanding verification items.

Security-critical paths: `src/call_llm.py`, `src/policy_core.py`, `src/pipeline.py`,
`src/storage.py`, `.github/ci_checks.py`, the workflows.

Pull requests that change a security-critical path must include an architecture decision
record under `docs/architecture/adr/` and receive the required human review. Gate 2
automatically checks that a matching ADR is present; the real human review is enforced by
Gate 1 together with the repository protection configuration.

## Alternatives considered

- **Single workflow for PRs and pushes.** Rejected: mixing push and PR triggers couples
  unrelated statuses and can cancel one run when another fails.
- **A workflow-level `paths:` filter.** Rejected: it skips the whole workflow for unrelated
  file changes, which would hide the approval gate; Gate 4 decides relevance itself from
  Gate 1's output instead.
- **Relying on the AI-use log as the approval signal.** Rejected: the log records that a
  session happened, not that a human approved; Gate 1 reads PR review state.
- **Offline-only semantic checking.** Rejected: a live round trip against the real gateway
  is the semantic layer and cannot be substituted.

## Re-evaluation triggers

Revisit this ADR if any of the following holds:

- The six PR checks or the two push checks stop reporting independently.
- A real test-first approval or a deliberately failing PR shows the gates do not block.
- The protected environment's variable/secret names change.
- The helper stops being the single home of the gate logic.
- Python 3.9 support (the verified version) is dropped.

---

## Addendum — 2026-11-21: Gate 1 upstream-sync handling (PR #36)

This addendum records a change to Gate 1 (`.github/ci_checks.py`), which is a
security-critical path, scoped to how a previously approved test is preserved across a
target-branch sync. Earlier decisions above remain in force and are not superseded.

- **Preservation on first-parent history.** Gate 1 walks the first-parent chain from the PR
  head back to the approved commit and inspects only commits after it. A two-parent merge
  may change a test path against its first parent **iff** the PR side of that path still
  matches its merge base (unchanged on the feature branch) **and** the merge result equals
  the incoming (target-branch) tree entry exactly — mode, type and content. Upstream edits
  and deletions of an existing file are therefore allowed only when the PR side did not
  touch it and the merge result is exactly the incoming version.
- **Ambiguity fails closed.** Overlapping edits (PR side differs from the merge base),
  altered merge results, multiple merge bases, or a conflict resolution that does not
  reproduce the incoming file are rejected and require review. Dropping a previously
  approved test by matching the incoming file is never silently accepted.
- **Unchanged requirements.** A real, independent, non-author, test-only approval and its
  timing (submitted at or after the approved commit and before the first implementation)
  remain required; earlier candidates that fail are recorded and the gate continues to
  check all effective approvals before failing.
- **Evidence.** Test-first approval for #36 at test SHA `245e18b`; #30 local replay of the
  same first-parent sync rule at `22cdf96` for `89f2f8f`. The local replay is offline
  evidence only.
- **Scope of the claim.** Hosting a green job does not prove branch protection is active;
  that the six checks actually block a bad merge remains an outstanding verification item.
