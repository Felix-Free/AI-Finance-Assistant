# 60528523 — Tan Jingling

> Annotated transcript of my work with the AI coding agent (OpenCode).
> Every entry records: what I instructed, what the agent produced, what I caught, and
> what I changed. This file is evidence of human authorship and supervision.
>
> Role: **A — Leader.** I own cross-review across the role deliverables, integration of
> the pull requests, and the final decision on whether a contribution is accepted. These
> entries record where I used the agent as a reviewer and where I overruled or blocked
> its input.

---

## Session 1 — 2026-11-09 · Cross-review of PR #8 (C specs) and PR #9 (D code)

**Context.** Two deliverables were waiting on review: PR #8 carried role C's security
specifications (`docs/architecture/invariants.md`, `runtime-policy-catalog.md`,
`permission-model.md`), and PR #9 carried role D's implementation (`src/policy_core.py`,
`src/pipeline.py`, plus the smoke tests). My job as leader was to confirm that the specs
were self-consistent and that the code actually enforced what the specs claimed.

### PR #8 — C's specification documents

**My instruction to the agent.**

```
Review docs/architecture/invariants.md and runtime-policy-catalog.md from role C.
Check, specifically, that every invariant has an "Evidence" field and that the
evidence it names (log file, error code, review flag) matches what the runtime
policy catalog says. Report LGTM only if the three invariants and the RP entries
are mutually consistent.
```

**Agent output (excerpt).**

```
Each of C-INV-001/002/003 has an Evidence field pointing to logs/review.jsonl.
The error codes (policy:amount, policy:category, policy:budget) match the RP
catalog. review=true for category and budget, review=false for amount. LGTM.
```

**What I caught / decided.** The agent reported LGTM on the Evidence fields, and on
re-reading the specs I agreed: the three invariants each carry a machine-checkable
Evidence line, and the `review` flags are consistent between `invariants.md §2` and the
runtime policy catalog. I accepted PR #8 as-is. The one thing I noted for later was that
the rejection line does not carry a call id, so a policy rejection cannot yet be joined
to its model-call line — the document already records this as Phase 2 debt, so it did
not block the merge.

### PR #9 — D's implementation

**My instruction to the agent.**

```
Run the offline boundary tests for src/policy_core.py and confirm the amount guard
is actually strict. In particular I want to see that a boolean is rejected — JSON
true must not be accepted as amount = 1. Show me the test result, do not just
assert it.
```

**Agent output (excerpt).**

```
I ran pytest test/offline. The amount guard rejects the boolean case: in Python
isinstance(True, int) is True, so a naive int check would accept True as 1. The
guard must explicitly reject bool before the numeric check. Boundary tests pass;
True is rejected, 0.01 and integer 350 are accepted.
```

**What I caught.** The boolean trap is exactly the kind of defect that survives a
"happy path" review: `True == 1` is true in Python, so an amount guard that only checks
`isinstance(amount, int)` would silently accept a model that returned `true`. The agent
confirmed the guard rejects `bool` explicitly, which matches C-INV-001's "finite positive
number" intent. That check is what I would have missed by reading the diff alone.

**My correction / action.** PR #9 did not merge cleanly — a YAML merge conflict appeared
in the shared documents. The agent does not resolve conflicts autonomously (and should
not), so I resolved the conflict by hand, keeping the invariant numbering decision from
C's specs and D's enforcement references consistent. After my manual resolution the
branch was mergeable and I accepted PR #9.

**Result.**

- PR #8 merged with the Evidence fields verified.
- PR #9 merged after I manually resolved the YAML conflict and confirmed the `bool`
  rejection test.
- Follow-up recorded: the full boundary suite (`test/offline/test_invariants.py`) is
  still role E's deliverable.

**Reflection.** The two reviews used the agent in different modes: on PR #8 it was a
consistency checker over prose, and on PR #9 it was a boundary-condition tester. It was
useful precisely where I told it *what specific property to prove* (Evidence present,
booleans rejected). A vague "review this" would have returned LGTM on both, which is
why the instruction, not the tool, carries the supervision.

---

## Session 2 — 2026-11-10 · Review of PR #10 (B requirements and blueprint)

**Context.** Role B submitted the machine-readable requirements (`docs/req/requirements.yaml`,
`req-schema.json`) and the architecture blueprint (`architecture-blueprint.md`). As leader
I treat these as the source of truth that the other roles build against, so a defect here
propagates to everyone. I asked the agent to audit them against the three checks I set.

**My instruction to the agent.**

```
Review the current branch (PR #10). Check three things:
1. requirements.yaml: are INV-001/002/003 from role C present, and are the NFRs
   expressed as metric + threshold + verification?
2. architecture-blueprint.md: does it clearly separate the AI (advisory) component
   from the deterministic safety boundary (authoritative)?
3. does docs/architecture/trace-matrix.md correctly map requirements to components?
Output a short report; say LGTM only if all three pass, otherwise list the issues.
```

**Agent output (excerpt).**

```
Not LGTM.
- INV-001/002/003 present and consistent with invariants.md. NFRs are structured but
  6 of 7 have threshold: null (pending_confirmation); only NFR-004 is quantified.
- Blueprint separates AI (advisory) and deterministic boundary correctly (§6 MAY /
  MUST NOT, trust-coloured diagram).
- docs/architecture/trace-matrix.md does not exist. Only inline trace tables in
  requirements.yaml and blueprint Appendix A are provided.
Additionally: requirements.yaml header and PD-005 say policy_core/pipeline are "not
yet merged", which contradicts the blueprint's "merged on main as of PR #9".
```

**What I caught.** Two things, both material.

1. **The requested deliverable was missing.** The task asked for a traceability matrix
   mapping requirements to components. The file `docs/architecture/trace-matrix.md` does
   not exist; B supplied inline tables instead and deferred the formal matrix to Phase 3.
   That is a scope gap I had to decide on, not paper over.

2. **B contradicted itself.** The requirements header and pending-decision PD-005 say the
   policy-core code is "not yet merged", while the blueprint says it is merged via PR #9.
   The agent also flagged that local and `origin/main` were still at PR #6, so the
   "merged on main" claim itself needed confirmation against the real remote.

**My decision.** I rejected PR #10 and requested changes. The specific requests:
create the trace matrix (or get explicit sign-off that inline tables substitute for it in
Phase 1), and make the requirements header and PD-005 agree with the blueprint and the
actual branch history. I did not merge a requirements document that contradicts itself,
because that inconsistency would have been inherited by every later phase.

**Result.**

- PR #10 rejected; change request issued to role B.
- The three checks recorded: (1) invariants present — pass; (2) AI/deterministic
  separation — pass; (3) traceability matrix — fail (missing), plus the internal
  contradiction.

**Reflection.** The agent was most valuable as a checklist enforcer: because I fixed the
three checks in advance, it could not drift into a generic "looks good" summary. Its
finding that a *requested file did not exist* is the kind of thing a human skim of prose
misses. But the acceptance decision was still mine — the agent reported the gap, I chose
to block the merge rather than accept inline tables as a substitute.

---

## Session 3 — 2026-11-10 · Review of PR #11 (E CI/CD Pipeline)

**Context.** Role E submitted the CI/CD pipeline (`.github/workflows/ci.yml`) and offline tests. The project mandates exactly 6 blocking gates. Because CI is the enforcement mechanism for our entire safety boundary, any omission here means unvalidated code could reach `main`. I asked the agent to act as a strict QA auditor.

**My instruction to the agent.**

```
You are the Lead QA Auditor. Please review the current branch (PR #11).
This PR contains the CI/CD pipeline configuration and offline tests created by Role E.
Our project strictly requires 6 blocking gates (especially the Schema Gate for requirements.yaml, and the Regression Gate for all tests). Please perform the following checks:

Read .github/workflows/ci.yml. Does it trigger on pull_request events?

Does the pipeline include a step to validate docs/req/requirements.yaml against docs/req/req-schema.json (Schema Gate)?

Does the pipeline run the offline tests (pytest test/offline)?

Are there any logical flaws in the CI YAML? For example, if a test fails, will the workflow correctly fail and block the PR merge?

Read any files in test/offline/. Do they correctly test the security invariants?
Output a structured review report. Say LGTM only if compliant.
```

**Agent output (excerpt).**

```
Not LGTM.

Schema Gate: ❌ MISSING. No step validates requirements.yaml. docs/req/ only has .gitkeep.

Logical flaws: ⚠️ Several. 1) Only ONE of the 6 required gates exists. 2) -m offline could silently skip unmarked tests (run still exits 0). 3) jsonschema not in requirements.txt.

Offline tests: ✅ Yes. They run and test security invariants strongly (e.g., rejecting -0.01, bad categories).
Verdict: ❌ CHANGES REQUESTED. The CI pipeline is missing the Schema Gate and 4 of the 6 required gates.
```

**What I caught.** Three critical issues, plus a coordination problem.

1. **Missing gates and dependencies.** The agent caught that the pipeline only implemented 1 of the 6 required blocking gates and lacked `jsonschema` in `requirements.txt`. 
2. **The silent test-skip vulnerability.** The agent noted that using `-m offline` might exit with 0 even if tests are skipped because of missing markers. This is a subtle CI logic flaw that human review often misses.
3. **Cross-role coordination.** I realized the missing Schema Gate wasn't just E's fault; E's CI was trying to check `requirements.yaml`, but Role B's PR #10 was still pending and not yet merged into `main`.

**My decision.** I rejected PR #11 and issued a detailed change request to Role E (including fixing the `-m offline` skip risk and adding `jsonschema`). Simultaneously, I intervened in the group chat to coordinate the cross-role dependency, asking Role B to fix and merge PR #10 first so Role E could complete the Schema Gate.

**Result.**

- PR #11 rejected; change request issued to role E.
- Role B notified in chat to prioritize merging their requirements file to unblock the CI.
- The CI compliance remains a tracked blocking issue.

**Reflection.** The agent was incredibly effective at parsing the CI YAML logic and spotting the `-m offline` silent-skip edge case. As a human, I would have likely just focused on whether the pipeline triggered and tests passed, missing the nuance of skipped markers. However, the agent does not understand cross-role dependencies (that it didn't see `requirements.yaml` because of a pending PR). My role was to connect the agent's code-level findings with the team's workflow, orchestrating the merge order to fix the CI.

---

## Session 4 — 2026-11-11 · Audit of PR #11 (Role E CI Update)

**Context.** Role E claimed to have pushed updates to the CI pipeline (PR #11) after my previous change request. I needed to verify if the functional changes (Schema Gate, dependencies) were actually implemented or just documentation updates.

**My instruction to the agent.**

```
Run git diff HEAD~1 HEAD to see exactly what files were modified in the latest push. Check if the previous blocking issues (missing Schema Gate, jsonschema dependency, silent-skip risk) were resolved. Output a status report.
```

**Agent output (excerpt).**

```
Audit Report - PR #11 re-review:

What changed: The latest push ONLY modified docs/ai-use-log.yaml (editorial changes). .github/workflows/ci.yml is unchanged.

Issue resolution status: Schema Gate (Still missing), jsonschema (Still missing), silent-skip risk (Still present).

Verdict: NOT LGTM. Zero of the four required fixes were addressed.
```

**What I caught.** The author misunderstood the review feedback and only updated the documentation log, leaving the core CI code untouched. 

**My decision.** I rejected the PR on GitHub and explicitly instructed Role E to modify `ci.yml` and `requirements.txt` to resolve the functional gates.

**Reflection.** The AI's diff-checking capability is crucial here. A human might assume "new commit = fixed issues", but the AI accurately pinpointed that only the log file was touched, preventing a false merge.

---

## Session 5 — 2026-11-11 · Resolving Cross-Role Dependency Blocker

**Context.** After Role E pushed his CI workflow again, the GitHub Actions failed with `exit code 1`.

**My instruction to the agent.**

```
Role E's CI is failing. Check the logs and identify the root cause.
```

**Agent output (excerpt).**

```
The offline-tests job failed. The log shows: FAIL: required file(s) missing: docs/req/requirements.yaml, docs/req/req-schema.json. The pipeline cannot run the Schema Gate because Role B's requirements are not merged yet.
```

**What I caught.** The failure was not a syntax error in Role E's CI, but a cross-role dependency blocker. Role E's branch was based on an outdated `main` that lacked Role B's PR #10.

**My decision.** I did not ask Role E to rewrite his CI. Instead, I intervened in the group chat to orchestrate the merge order: instructing Role B to merge PR #10 first, and then telling Role E to click "Update branch" to sync the latest code.

**Reflection.** AI agents operate within their isolated local branches. They cannot solve team workflow bottlenecks. My human intervention successfully decoupled the dependency and unblocked the pipeline.

---

## Session 6 — 2026-11-12 · Review of PR #10 (Role B NFR & Schema Fix)

**Context.** Role B updated PR #10 to fix the `NFR-007` threshold and the `C-INV` naming inconsistencies flagged by Role E and me.

**My instruction to the agent.**

```
Check docs/req/requirements.yaml. Verify if the threshold for NFR-007 is a numeric 1.0 (to pass the schema) and if all C-INV references have been standardized to INV.
```

**Agent output (excerpt).**

```
LGTM. NFR-007 threshold is set to 1.0. However, I found a few remaining C-INV references in architecture-blueprint.md.
```

**What I caught.** Role B fixed the schema error but missed a few occurrences of `C-INV` in the architecture blueprint. 

**My decision.** Instead of blocking the PR again, I used the GitHub web editor to manually fix the remaining `C-INV` prefixes on her branch. I then formally approved and merged PR #10.

**Reflection.** Human agility is key. Since the remaining fixes were purely mechanical naming conventions, I directly intervened to fix them, saving another round-trip of PR reviews.

---

## Session 7 — 2026-11-13 · Review of PR #18 (Role D Phase 2)

**Context.** Role D submitted PR #18 for Phase 2, implementing the storage layer, resolving technical debts, and generating NFR measurement data.

**My instruction to the agent.**

```
Review PR #18. Check if src/storage.py strictly enforces validation through policy_core.py before writing. Verify the technical debt fixes (accurate error codes, traceability in logs).
```

**Agent output (excerpt).**

```
LGTM on the implementation. The storage layer correctly enforces policy_core validation. Technical debt fixes look solid. Note: Measurement scripts are currently in src/, but should be relocated to scripts/ per architecture.
```

**What I caught.** I noticed a cross-role permission blocker: Role D couldn't move the scripts to `scripts/` and `docs/measurements/` because Role C hadn't updated `.opencode/permissions.jsonc`.

**My decision.** I approved the logic but withheld the merge. I intervened in the group chat to task Role C with updating the permissions file, and instructed Role D to relocate the scripts once C's PR was merged.

**Reflection.** The AI validated the code logic perfectly, but organizational dependencies (like file permission profiles) require human coordination. My role was to orchestrate the unblocking between Role C and Role D.

---

## Session 8 — 2026-11-13 · Guard-Removal Validation and Sandbox Interception

**Context.** Still reviewing PR #18, I asked the agent to verify if the `-0.01` boundary technical debt was resolved.

**Agent output (excerpt).**

```
The agent autonomously decided to run a **guard-removal experiment**. It backed up `policy_core.py` to `/tmp`, dynamically removed the `if amount <= 0:` safety guard, and attempted to run `pytest` to see if the test suite would fail.
*(Include Screenshot of the `/tmp` permission prompt)*
```

**What I caught.** The agent's security testing methodology was brilliant—it tried to prove the negative tests were effective by breaking the guard. However, it was blocked by our strict `.opencode/permissions.jsonc` because it attempted to access the `/tmp` directory.

**My decision.** I intervened and explicitly clicked "Allow once" to let the agent complete its guard-removal experiment. 

**Reflection.** This was a profound interaction. The AI autonomously designed a sophisticated security test, but our deterministic safety boundary (the permission sandbox) successfully intercepted it. Human authorization was required to proceed. This proves that our governance model works: the AI can audit and test, but it cannot bypass the boundaries without explicit human approval.

## Session 9: 2026-11-13 - Managing Scope and Phase Alignment

**Context.** I initially requested Role E to implement all 6 blocking gates immediately for PR #11. Role E rightly pushed back, pointing out that his CI file already contains 4 core steps (albeit in a single job), and that the full 6-gate implementation (with separate jobs and semantic evaluation) is planned for Phase 2.

**Human Intervention & Reflection.** 
I acknowledged that my instruction over-scoped the Phase 1 requirement. I corrected my stance, approved Role E's PR #11 because the CI skeleton was successfully running the schema and offline tests, and clearly documented that the remaining gates would be deferred to Phase 2. 

This taught me a valuable lesson in agile project management: a leader must not let the "ideal final state" block the "necessary current milestone". Recognizing and correcting scope creep in real-time is essential for maintaining team velocity and morale.

## Session 10: 2026-11-13 - Deep Code Audit and Security Boundary Verification (PR #18)

**Context.** I used OpenCode to review PR #18. Instead of just reading the code, I instructed the agent to actively test the boundary conditions of the storage layer.

**Agent Output (excerpt).**

```
Verdict: Not LGTM.
Blocking Issue 1: src/storage.py is not a policy gate. I reproduced this by calling append_validated directly with an invalid record (amount=999999, budget=1.0) and it was accepted and written to disk.
Blocking Issue 2: report_tokens.LOG_PATH is still cwd-relative, and the test suite omits checking it.
```

**What I caught.** 
The AI agent successfully breached the storage layer by bypassing the `pipeline` and calling `storage` directly. It proved that the "fail-closed" claim in the storage layer's docstring was only a shape check, not a true invariant check.

**My decision.** 
I formally rejected PR #18 and requested changes. I instructed Role D to either enforce `policy_core` validation directly in `storage.py` or update the architectural contract to clarify that the `pipeline` is the sole gatekeeper.

**Reflection.** 
This is a classic "defense in depth" scenario. Humans might assume that because the main pipeline works, the system is safe. However, the AI agent actively tried to bypass the main route and found a vulnerability in the public API of the storage layer. This demonstrates that AI can act as a ruthless adversary to test our security boundaries, proving the necessity of AI-assisted architectural audits.

## Overall Reflection — Role A (Leader)

Across both sessions the same pattern held: the agent's usefulness was proportional to how
precisely I scoped the review. When I named the exact property to prove — "Evidence field
present", "boolean amount rejected", "trace-matrix exists" — it produced a concrete,
falsifiable answer. When a task was broad, it tended toward LGTM, which is exactly the
outcome a reviewer must not accept uncritically.

The three concrete interventions I own as leader:

1. **Verifying evidence (PR #8):** I confirmed C's Evidence fields and review flags are
   consistent, and accepted the specs.
2. **Testing boundaries and resolving integration (PR #9):** I had the agent prove the
   `bool`-as-amount trap was rejected, and I personally resolved the YAML merge conflict
   the agent must not touch.
3. **Blocking a self-contradictory deliverable (PR #10):** I used the agent's audit to
   reject the requirements PR for a missing traceability matrix and for contradicting
   the branch history, and I issued a change request.

The recurring lesson: the AI is a reviewer, never the approver. It caught real defects
(the boolean trap, the missing file, the internal contradiction), but every merge or block
decision was made by me, on evidence the agent was told to show rather than assert.
