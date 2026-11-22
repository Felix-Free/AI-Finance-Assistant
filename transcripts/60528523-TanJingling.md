# 60528523 — Tan Jingling

> Annotated transcript of my work with the AI coding agent (OpenCode).
> Every entry records: what I instructed, what the agent produced, what I caught, and
> what I changed. This file is evidence of human authorship and supervision.
>
> Role: **A — Leader.** I own cross-review across the role deliverables, integration of
> the pull requests, and the final decision on whether a contribution is accepted. These
> entries record where I used the agent as a reviewer and where I overruled or blocked
> its input.

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

---

## Session 9 — 2026-11-13 · Managing Scope and Phase Alignment

**Context.** I initially requested Role E to implement all 6 blocking gates immediately for PR #11. Role E rightly pushed back, pointing out that his CI file already contains 4 core steps (albeit in a single job), and that the full 6-gate implementation (with separate jobs and semantic evaluation) is planned for Phase 2.

**Human Intervention & Reflection.** 
I acknowledged that my instruction over-scoped the Phase 1 requirement. I corrected my stance, approved Role E's PR #11 because the CI skeleton was successfully running the schema and offline tests, and clearly documented that the remaining gates would be deferred to Phase 2. 

This taught me a valuable lesson in agile project management: a leader must not let the "ideal final state" block the "necessary current milestone". Recognizing and correcting scope creep in real-time is essential for maintaining team velocity and morale.

---

## Session 10 — 2026-11-13 · Deep Code Audit and Security Boundary Verification (PR #18)

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

---

## Session 11 — 2026-11-13 · README Creation via Web UI (Bypassing VM Network Failure)

**Context.** After successfully merging Role B's requirements and Role E's CI pipeline into `main`, the project foundation was fully established. I needed to generate the final `README.md`. However, my local Ubuntu VM encountered a persistent `GnuTLS recv error (-54)` when trying to `git pull`, blocking the local Git workflow.

**Human Intervention.** 
Instead of wasting time troubleshooting the VM's SSL network configuration, I utilized an agile workaround. I generated the `README.md` content using the AI prompt based on our finalized architecture, and then directly created the file using the GitHub Web UI. I created a new branch (`docs/leader-readme`) directly from the browser and submitted a PR.

**Reflection.** 
This session highlights a critical aspect of human-in-the-loop engineering: adaptability. While AI and local tools are powerful, they can be blocked by environmental issues (like network failures). A human supervisor can seamlessly pivot to alternative platforms (like the GitHub Web interface) to ensure deliverables are met on time, bypassing technical bottlenecks.

---

## Session 12 — 2026-11-16 · Security Audit of Role C Permission Update

**Context.** Reviewed PR #19 (Permission configuration update). I instructed OpenCode to verify if the JSONC syntax was correct and if protected paths were denied.

**Agent Output (excerpt).**

```
Verdict: Changes requested.
Blocking Issue: The doc states runtime-generated files under data/ are excluded from version control, but .gitignore has no entry for data/. This is a commit-safety gap.
```

**What I caught.**
The AI didn't just look at the permissions file; it cross-referenced the documentation with the `.gitignore` file and found a discrepancy. Role C promised data safety in the docs, but the repo was not actually ignoring `data/`.

**Reflection.**
This is why AI-assisted code review is powerful. A human reviewer might just look at the `.jsonc` file and say "looks good." The AI checked the whole repository context and found that a documented guarantee was unenforced. Human intervention was needed to instruct Role C to update the `.gitignore` and resolve the YAML merge conflicts.

---

## Session 13 — 2026-11-16 · Verifying Role D's Fixes and Cross-Role Sequencing

**Context.** Role D updated PR #18 to fix the storage fail-closed bypass and path anchoring debt. I used OpenCode to audit the diff.

**Agent Output (excerpt).**
- Storage Fail-closed: RESOLVED (via re-validation approach). Role D chose the stricter option.
- Path Anchoring: RESOLVED.
- Scripts Migration: NOT DONE (still in `src/`).
- Tests: PASS (152 passed, 4 skipped).
Verdict: Not LGTM only because of the missing scripts migration.

**Human Intervention.**
While OpenCode correctly flagged the missing script migration, I recognized this was a cross-role dependency blocked by Role C's permission update (PR #19). Instead of approving prematurely or merging a partial state, I issued an `Approve` on the code logic but explicitly held the merge. I instructed Role D to wait for Role C's PR, perform the migration in one go, and push the final update for immediate merge.

**Reflection.**
AI agents operate linearly (check list -> fail if not done). Human leaders understand project sequencing. I used the AI's strict verdict to ensure quality, but applied human judgment to schedule the PR integrations, preventing fragmented PRs and reducing unnecessary review cycles.

---

## Session 14 — 2026-11-16 · Final QA Audit of PR #20 (Detecting Traceability Gaps)

**Context.** Role E submitted PR #20 for Phase 3, containing the final CI/CD pipeline, exhaustive test suites, and QA documentation. I utilized OpenCode to conduct a strict compliance audit against D2/D4 requirements.

**Agent Output (excerpt).**
- CI Gates: PASS. All 6 blocking gates are correctly configured as independent jobs.
- Test Coverage: PASS. 201 tests passed. Guard-removal property verified empirically.
- QA Documentation: NOT LGTM. Identified a Traceability gap (150 untagged tests not mapped to requirements) and an Evidence gap (bug diary claims "fixed" without linking to tests/commits).
Verdict: CHANGES REQUIRED.

**Human Intervention.**
The AI's audit revealed that while the code and tests were robust, the documentation overclaimed its traceability. I formally rejected the PR on GitHub and instructed Role E to provide concrete mapping tables, link bug fixes to specific tests, and add `--strict-markers` to prevent silent test skips in the future.

**Reflection.**
This session highlighted the value of AI as a ruthless auditor of "engineering honesty." A human might overlook that "every test traces to a requirement" was a false claim. The AI cross-referenced the doc's claims against the actual pytest markers and found the discrepancy. My role was to enforce this rigor, ensuring our final report reflects genuine software engineering practices rather than wishful documentation.

---

## Session 15 — 2026-11-16 · Architecture Completeness & Traceability Audit (PR #21)

**Context.** Role B submitted PR #21 to finalize D2 architecture artifacts. I used OpenCode to verify completeness and cross-check the trace matrix against the codebase.

**Agent Output (excerpt).**

```
D2 Artifacts: Missing docs/architecture/evaluation-table.md.
Trace Matrix Sync: Found incorrect function reference (_append_rejection instead of _append_review), arithmetic error (37 vs 36), and inconsistent table schemas (9 vs 10 columns).
Stale Info: Blueprint still claims CI is not set up.
```

**Human Intervention.**
The AI successfully uncovered multiple inconsistencies that would have cost us points on D2 documentation. I formally requested changes, instructing Role B to use AI to generate the missing `evaluation-table.md` and mathematically reconcile the trace matrix.

**Reflection.**
This perfectly illustrates AI's advantage over human review in large documentation sets. A human would easily miss that the sum of requirements was off by one, or that a function name had a suffix typo. By using AI as a cross-referencer, we enforced absolute rigor in our architecture deliverables.

---

## Session 16 — 2026-11-16 · Re-audit of Role C's Permission Update (PR #19)

**Context.** Role C updated PR #19 to fix the `.gitignore` gap and resolve the `ai-use-log.yaml` merge conflict. I used OpenCode to perform a final security and consistency audit.

**Agent Output (excerpt).**

```
Verdict: LGTM.
Commit-safety gap: RESOLVED. .gitignore includes data/.
Merge conflict resolution: RESOLVED. No conflict markers or duplicate keys in ai-use-log.yaml.
Permission strictness: RESOLVED. Redundant rules removed; .env and .github/ protections remain intact.
```

**Human Intervention.**
I instructed the agent to specifically run `git check-ignore` and scan for leftover conflict markers—tasks that are tedious for humans but trivial for AI. I then merged the PR, officially unblocking Role D's scripts migration.

**Reflection.**
This successful re-audit proves that AI is perfectly suited for verifying "clean" states—ensuring that a merge conflict hasn't left syntax garbage and that configuration files actually enforce what they claim. This saves human reviewers from painful manual checks and guarantees a clean codebase for the final submission.

---

## Session 17 — 2026-11-16 · Gate 1 blocked my own merge, and the audit behind it (PR #20)

**Context.** Role E submitted PR #20 with the six gates, the expanded test suites and the QA
documentation. I used the AI coding agent twice on it: a strict re-audit of the three blocking
issues I had raised, and then an attempt to merge the result.

**Agent output (excerpt).**

```
Verdict: LGTM.
Traceability: RESOLVED. Independent count verification confirmed 204 tests match the doc claims exactly.
Evidence: RESOLVED. BUG-01/02 linked to regression tests. Guard-removal verification confirmed the tests fail when the defect is reintroduced.
Marker integrity: RESOLVED. --strict-markers is active. 204 tests passed.
```

**What I caught.** I approved the PR and clicked merge; GitHub refused with
`FAIL: no approval on a qualified test-first commit`. My first reading was that this was a CI
synchronisation bug — the approval had clearly been registered after the run. I re-triggered the
jobs and it failed again. Only then did the actual rule land: Gate 1 needs a commit that contains
**only tests**, approved **before** the implementation commit exists. PR #20 had arrived with tests
and fixes in one push, so no commit in it could ever qualify.

**Human intervention.** I did not bypass the gate. I had Role E explain the rule on the record,
and the merge was eventually unblocked through a documented one-time waiver scoped to PR #20 —
recorded in the CI ADR and protected by its own regression test — rather than by an admin merge or
by weakening the check for everyone else.

**Reflection.** This is the session I would show anyone who thinks CI gates are decoration: the
gate blocked the person who wrote the process. The uncomfortable part is that "correct" and
"workable" diverged — a strict test-first rule cannot be satisfied by a PR that arrives with tests
and code together, which is how a five-person team actually works under a deadline. The lesson was
not to soften the gate but to make the escape hatch explicit, narrow, recorded and expiring. Six
months from now the waiver should look like a scar, not like a door.

---

## Session 18 — 2026-11-16 · Re-audit of Role B's Architecture Updates (PR #21)

**Context.** Role B updated PR #21 to fix the missing `evaluation-table.md`, trace matrix arithmetic errors, and stale blueprint info. I used OpenCode to perform a comprehensive re-audit of the D2 deliverables.

**Agent Output (excerpt).**

```
Verdict: LGTM.
Missing D2 Artifact: RESOLVED. evaluation-table.md exists (123 lines) with genuine comparative evaluation (3 candidate architectures) and ties to requirement IDs.
Trace-Matrix Typo: RESOLVED. _append_rejection corrected to _append_review.
Arithmetic & Schema: RESOLVED. Total count perfectly reconciles to 36 across all sections. Tables unified into a uniform 8-column header (0 mismatches).
Stale Blueprint CI Info: RESOLVED. Removed "not yet set up" claims; CI status updated to "configured on main".
Cross-document consistency: Blueprint, evaluation-table, trace-matrix, option-ledger, and risk-list all agree on the 36-requirement total and branch-state.
```

**Human Intervention.**
I instructed the agent to rigorously check the arithmetic sums and the schema consistency in the trace matrix. The AI's cross-document consistency check confirmed that all D2 artifacts were now mathematically sound and factually aligned. I approved and merged the PR, officially freezing the architecture deliverables.

**Reflection.**
Architecture documentation is notoriously prone to arithmetic errors and "documentation drift" (where one doc says one thing and another contradicts it). OpenCode acted as a ruthless fact-checker, proving that our D2 deliverables are not just pretty text, but mathematically consistent and perfectly aligned with the codebase. This marks a flawless closure of Phase 3 architecture tasks.

---

## Session 19 — 2026-11-16 · Resolving the TDD vs. CI Paradox via Exemption Labels (PR #20)

**Context.** Role E's "Gate 1" strictly enforced the Test-First rule, blocking PR #20 because tests and implementation were combined in a single push. Role E pointed out a real-world paradox: if a PR only pushes tests first, the CI will inevitably fail (as implementation is absent), blocking the workflow.

**Human Intervention.**
I recognized that strict theoretical TDD must be adapted to fit the CI pipeline constraints. I instructed Role E to implement a standard "exemption label" mechanism: if a PR carries the `skip-test-gate` label, the `ci_checks.py` script will gracefully output `Passed (Waived)` and exit with 0. I then applied this label to PR #20 to unblock the final merge.

**Reflection.**
This was a profound lesson in CI/CD governance. A blocking gate is useless if it cannot be practically navigated by developers. By introducing the explicit, human-controlled "waiver" label, we preserved the integrity of the Test-First gate (it still blocks unauthorized merges) while providing an auditable escape hatch for edge cases (like deadlines or combined PRs). This perfectly models production-grade DevOps practices.

---

## Session 20 — 2026-11-16 · Configuring Secure Environment Secrets for Gate 4 (PR #20)

**Context.** Role E successfully fixed Gate 1 and added Gate 4 (Semantic Evaluation Gate). However, Gate 4 failed because the CI pipeline lacked the necessary LLM API credentials to run the semantic tests.

**Human Intervention.**
As the repository owner, I recognized that hardcoding the API key into the repository would be a severe security violation (breaching our secret-scanning invariant). I navigated to GitHub's `Settings -> Secrets and variables -> Actions` and securely provisioned `LLM_API_KEY` as a repository Secret, and `LLM_BASE_URL` as a repository Variable. I then instructed Role E to re-run the CI.

**Reflection.**
This session perfectly demonstrated the real-world security boundary of CI/CD. AI agents can write the YAML script, but they cannot (and should not) possess the actual credentials. The human leader must securely inject secrets into the environment. By using GitHub Secrets, we ensured that the API key was never exposed in the codebase or the AI agent's context, proving our adherence to strict DevSecOps principles.

---

## Session 21 — 2026-11-16 · Final Re-audit of Role C's PR (#19)

**Context.** Role C resolved the merge conflicts in `ai-use-log.yaml` after the major updates from PR #20/21. I used OpenCode to verify the conflict resolution and security boundaries.

**Agent Output (excerpt).**
Verdict: LGTM. 37-entry list parsed cleanly, zero duplicate keys. `.gitignore` correctly ignores `data/`. Security boundaries strictly enforced.

**Human Intervention.**
I verified the AI's audit report and merged the PR, officially closing the security and permission track for Phase 3.

**Reflection.**
Manual conflict resolution is a common source of syntax errors. Relying on AI to parse the YAML and check for duplicate keys ensures a clean integration before final submission.

---

---

## Session 22 — 2026-11-16 · Final Audit of the Test-Gate Waiver (PR #20)

**Context.** Role E implemented the `skip-test-gate` waiver to bypass the strict Test-First rule for PR #20. I used OpenCode to verify the fix.

**Agent Output (excerpt).**
Verdict: Not quite LGTM.
- Live test assertions: FIXED (using alias set).
- Gate Waiver: FIXED (triple-scoped to repo + PR #20 + label).
- Concern: The Waiver mechanism lacks an automated test, violating our own `AGENTS.md §6` rule ("every guard needs a test").

**Human Intervention.**
I acknowledged the AI's finding. To balance the strict rules of our own constitution (`AGENTS.md`) with the submission deadline, I instructed Role E to add a minimal mock test for the waiver OR explicitly documented my human override on the PR as an authorized exception.

**Reflection.**
This highlighted the tension between strict governance and pragmatic delivery. AI acts as a pure guardian of the rules. Human leadership requires the wisdom to know when to enforce, when to patch, and when to explicitly waive a rule with a documented rationale.

---

## Session 23 — 2026-11-17 · Prompt Evolution and Sandbox Exception Handling

**Context.** Following Role D's discovery that the LLM hallucinated categories due to a missing whitelist, I tasked OpenCode with creating `prompts/prompt_v1.1.yaml` to document the prompt evolution (v1.0 to v1.1) and the associated token optimization.

**Agent Output (excerpt).**
- Created `prompts/prompt_v1.1.yaml`. YAML parses successfully, matching the `policy_core.py` whitelist.
- The v1.0 entry documents the `HALLUCINATED_CATEGORY` issue: the model invented labels (e.g., "transportation", "groceries"), which caused `policy_core.py` to reject them (violating INV-002), wasting a model round-trip.
- **Crucial Note:** The agent explicitly flagged that `prompts/` is NOT listed in the `AGENTS.md` permission table and treated this write as an "approved exception" based on my explicit human instruction.

**Human Intervention.**
I reviewed the YAML structure and confirmed the v1.1 prompt now strictly constrains the LLM to the whitelist. I acknowledged the agent's adherence to our permission boundaries (requiring human authorization to write outside the whitelisted paths) and approved the PR.

**Reflection.**
This session was a dual victory. First, it documented the evolution of our AI prompts, proving token efficiency improvements by preventing hallucinated categories. Second, it demonstrated that our Coding Governance (D3) works flawlessly—the AI didn't blindly write files, it recognized a path outside `AGENTS.md` and required explicit human override. This is precisely the human-in-the-loop governance required by the course.

---

## Session 24 — 2026-11-19 · CI Infrastructure Blocker (Ubuntu 26.04 drops Python 3.9)

**Context.** Role B detected that GitHub Actions' `ubuntu-latest` label now resolves to Ubuntu 26.04, which has no prebuilt Python 3.9 in `actions/setup-python`. Merging PR #20 as-is would break CI on `main` and block all subsequent PRs.

**Human Intervention.**
I verified the technical claim and decided to prioritize PR #20's runner fix before merging, rather than merging first and patching later. I instructed Role E to change all `runs-on: ubuntu-latest` entries to `runs-on: ubuntu-22.04` across both workflow files.

**Reflection.**
This is a classic infrastructure drift issue. The AI agents (B and E) were focused on their respective PRs, but only human oversight connected the dots: "merging this PR will break the pipeline for everyone." The Leader's role was to enforce the correct merge order and prevent a CI outage.

---

## Session 25 — 2026-11-19 · Managing Concurrency Bugs and CI/CD Policy Conflicts

**Context.** Role B discovered a critical race condition in `storage.py` where concurrent requests shared the same `.jsonl.tmp` file, causing data loss and false errors. Role E pointed out a policy conflict: fixing this requires code first, which violates Gate 1 (Test-First). B proposed rewriting Git history (reset) to satisfy the gate.

**Human Intervention.**
As the Leader, I made a crucial project management decision: **Never rewrite Git history near the deadline.** I overrode the strict Gate 1 enforcement by classifying this as a critical "Bug Fix" and authorized the use of exemption labels/waivers. I directed Role B to draft ADR-003 for the file-locking mechanism, and instructed Role E to write the concurrent test using B's proven Event-driven reproduction strategy without resetting the branch.

**Reflection.**
This was a masterclass in balancing engineering rigor with project pragmatism. AI tools enforce rigid rules (like strict Test-First gates), but they cannot evaluate the risk of Git history rewrites or deadline pressures. Human leadership is required to know when to explicitly override a process to protect the integrity of the codebase and the delivery timeline.

---

## Session 26 — 2026-11-19 · Architecture Documentation Sync Audit (PR #31)

**Context.** After merging Role D's PR #18, several architectural documents and requirements became stale. Role B submitted a follow-up PR to synchronize script paths, function names (`_append_rejection`), and NFR statuses. I used OpenCode to verify the sync and check for any remaining drift.

**Agent Output (excerpt).**
Verdict: LGTM (with minor notes).
- **Scope Integrity:** Verified only 3 doc files changed (no `src/`, `test/` touched).
- **Function Name Sync:** Successfully updated `_append_review` to `_append_rejection` across evaluation table, trace matrix, and requirements.
- **NFR Status Alignment:** NFR-001 correctly marked as merged (distinguishing "code merged" from "evidence pending"). NFR-006 accurately corrected to "4 test functions are skipped".
- **Out-of-PR finding:** OpenCode flagged that other docs (`runtime-policy-catalog.md`, `evaluation-logbook.md`) still reference `src/measure_*`. These are out of scope for this PR but remain inconsistent with the code.
- **Caveat:** AI noted it couldn't run `pytest` due to a missing `google.protobuf` in its sandbox, so the "4 skipped tests" was verified statically via source code.

**Human Intervention.**
I reviewed the AI's audit report. I approved and merged the PR, acknowledging that the primary drift was fixed. I noted the AI's "out-of-scope" findings and created a follow-up task in the group chat for Role B to clean up those remaining docs in a separate PR.

**Reflection.**
This demonstrates how AI can act as a systemic auditor, not just a PR reviewer. It didn't just validate the current diff; it scanned the whole repository and found *hidden* technical debt. As a human Leader, my role was to triage this debt: merging the current fix and scheduling the remaining cleanup, ensuring we don't overburden a single PR while keeping the codebase perfectly consistent.

---

## Session 27 — 2026-11-19 · Merging CI Runner Fixes and Managing Integration Risks

**Context.** Role B flagged that the critical runner fix (`ubuntu-latest` to `ubuntu-22.04`) was included in Role E's PR #20. Role D was simultaneously rewriting Git history on a separate branch for her concurrency fix.

**Human Intervention.**
I immediately applied the `skip-test-gate` waiver to PR #20 and merged it to stabilize the global CI pipeline. Recognizing the integration risk, I proactively warned Role D that merging #20 into `main` would update `ci.yml` and likely cause conflicts with her rewritten history. I authorized her to abandon the history rewrite and fallback to a standard branch sync + waiver merge if conflicts arose.

**Reflection.**
This highlights the "domino effect" of infrastructure updates. Merging the runner fix was essential to unblock the team, but as a Leader, I had to foresee how this change would affect parallel workflows (Role D's branch). Proactive risk communication and providing a fallback plan are key to preventing integration deadlocks.

---

## Session 28 — 2026-11-20 · Detecting Test-Implementation Integration Conflicts

**Context.** During a complex local merge of PR #30 (atomic storage fixes) into `main`, I ran the full offline test suite and detected one failure:
`test_accept_append_open_failure_raises_and_keeps_old_bytes` failed because `StorageError` was not raised.

**Human Intervention.**
I immediately halted the `git push` to prevent a broken build on `main`. I diagnosed the issue as an integration conflict between Role D's new file-locking implementation and Role E's pre-existing error-handling tests. I reverted the local merge commit and instructed D and E to synchronize their code and test expectations.

**Reflection.**
This validates the purpose of local pre-push verification. AI tools reviewed D's code in isolation (LGTM) and E's tests in isolation, but merging them exposed a friction point. Human oversight was required to catch this integration failure before it polluted the main branch, demonstrating why automated tests must run after the merge, not just on individual branches.

---

## Session 29 — 2026-11-20 · Manually Bridging the Integration Gap (Test vs. Implementation)

**Context.** After attempting to merge PR #30 into `main`, one test failed due to a mocking incompatibility with the new file-locking mechanism. Role D advised applying a test patch from Role E directly to `main` before merging #30 to avoid Gate 1 history rewrites.

**Human Intervention.**
I acted as the integration bridge. I requested the patch from Role E, applied it manually to the `test_evidence_join.py` file, and created a test-only commit on `main`. I then merged PR #30, resolved the YAML conflict using Role D's 54-entry union, verified that all 218 offline tests passed locally, and pushed both commits to `main` simultaneously.

**Reflection.**
This was a surgical Git operation. By taking the "test fix" out of the PR and applying it directly to `main`, we avoided polluting PR #30's history and preserved Role E's Gate 1 approval. It demonstrated that human Leaders must sometimes step in as the ultimate integrator when independent AI/dev workflows collide.

---

## Session 30 — 2026-11-20 · Designing the Demo Video Script for Blocking Gates

**Context.** Role E (QA) was concerned about the demo video requirement to show a "CI blocking a bad PR." The only recent example was PR #32, which was merged by the Admin despite a red Gate 1.

**Human Intervention.**
I designed a specific demonstration script for the video. Instead of using a real (and messy) PR history, I instructed Role E to intentionally create a "Dummy PR" that breaks an invariant (e.g., deleting the guard in `policy_core.py`). This will trigger a genuine CI failure and visibly disable the GitHub merge button. I also suggested framing the PR #32 case as a documented "controlled waiver" for infrastructure emergencies.

**Reflection.**
This highlights the difference between a real-world repo and a demonstration. To clearly prove the existence of blocking gates, the best approach is to intentionally inject a defect. This provides undeniable visual evidence of the CI pipeline locking down the repository.

---

## Session 31 — 2026-11-21 · Progress audit against the brief and the D6 report framework

**Context.** The submission deadline was close and nobody had written `Report.md`. I asked the agent to read the two CS5351 PDFs and the whole repository, then tell me where the team actually stood against D1–D9, and to draft a report framework that five people could fill without colliding.

**My instruction to the agent.**

```
Read the project brief (PDF) and the whole repository at main. Do not summarise the README.
For each deliverable D1-D9, tell me: done / partial / missing, and cite the file or PR that
proves it. Then draft Report.md as a framework, not prose: every section must name its owner,
a word budget, and the artefacts it has to cite. Do not write claims we cannot prove.
```

**Agent output (excerpt).**

```
main 08e9171 · 166 commits · 33 merges · 74 tracked files
D1 done · D2 done (11 artefacts) · D3 done · D4 partial (review memo covers #18/#19 only)
D5 3/5 transcripts (A, C, D; B in unmerged #33; E missing; role B has 0 ai-use-log rows)
D6 stub (1 line) · D7 six gates implemented, required-check enforcement unverified (DEBT-08),
#32 merged with Gate 1 red · D8 done · D9 Prompt.md only; prompts/ is empty on main
```

**What I caught.** The first draft was a good audit and a weak framework: it listed sections but no owner and no evidence contract, and it was ready to describe branch protection as "enabled" and NFR-001/002 as satisfied. I rejected those two sentences specifically — `DEBT-08` is in our own repository and says the enforcement is unverified, so the report would have contradicted our own evidence. I also split the ownership so that B keeps requirements and traceability, and E keeps the gate evidence.

**Human decision.** Power-of-five split (A: 1–2, 5.1/5.3, 7, 10; B: 3, 4.4, 8; C: 4.1–4.3, 9; D: 5.2, 6.3; E: 6.1–6.2, 6.4), a 9,650-word budget under the 10,000 cap, and a rule that every claim cites a file, a PR or a run link. The framework went into PR #28.

**Reflection.** The agent's audit was accurate and useful, but it defaulted to writing the report we wished we had. The value I added was refusing two sentences that our own `debt-register.md` contradicts. On this project the hard part of supervision is not finding work the agent missed — it is stopping it from turning "we intended this" into "we did this".

---

## Session 32 — 2026-11-21 · PR #28 red: the gate was right, the YAML was wrong

**Context.** PR #28 (prompt v1.1 + report framework) showed 4/6 checks. Gate 6 was explainable — we changed `prompts/` without appending an AI-use-log session — but Gate 4 (semantic-eval) failed in 0 seconds, which does not look like a model-quality failure.

**My instruction to the agent.**

```
Gate 4 failed but the job finished instantly, so it never called the model. Read the live test
and the prompt file and tell me what the fixture actually reads. Do not touch src/policy_core.py
and do not relax any expectation to make it pass.
```

**Agent output (excerpt).**

```
test/live/test_live_model.py:87   prompt = document.get("system_prompt")
prompts/prompt_v1.1.yaml         top-level keys: schema_version, file, purpose, model, prompts, comparison
=> document.get("system_prompt") is None => pytest.fail("prompt file has no non-empty system_prompt")
```

**What I caught.** I had assumed the failure meant the model answered "transportation"/"groceries" again. It was structural: the v1.1 text existed only inside the `prompts:` history list, so the evaluator had nothing to replay. The fix was 37 lines — expose the current prompt at top level and keep it byte-identical to the history entry — not a prompt rewrite. I also noticed that no test reads `prompts/*.yaml` at all, which is why a wrongly shaped file could sit in a PR for days.

**Human decision.** Fix the shape, add the missing AI-use-log session, and deliberately **not** put `prompt_v1.0.yaml` under `prompts/` yet: Gate 4 replays every YAML in that directory, and v1.0 has no `not_a_record` rule, so it would fail the non-expense case and turn the gate red again. The archived v1.0 goes to `docs/architecture/prompt-history/` tonight; teaching Gate 4 to skip superseded prompts is tomorrow's work.

**Evidence.** Head `9fca8cb`: all eight checks green, Gate 4 ran a real evaluation in 27 s.

**Reflection.** Two failures of the same kind: I trusted the symptom instead of the log, and the repository had no test covering the artefact the gate depends on. The agent found the cause in one step because I asked it to read the code path rather than to explain the failure. "Explain the failure" invites a plausible story; "read the code that produced it" does not.

---

## Session 33 — 2026-11-22 · Repairing a whole-file conflict nobody could merge

**Context.** Role B's transcript PR (#33) had been unmergeable for a day: `docs/ai-use-log.yaml` is a single append-only file that five people write to, so every branch conflicts at the tail. We had already hit this three times; one earlier commit is literally called "union the ai-use-log with main".

**My instruction to the agent.**

```
The conflict is in docs/ai-use-log.yaml only. Do not hand-edit conflict markers. Rebuild the file
from current main and re-append B's session verbatim, then tell me what a reviewer should check.
```

**Agent output (excerpt).**

```
merge-base old base -> 37 added lines in the PR
rebuild: git checkout origin/main -- docs/ai-use-log.yaml, then append those 37 lines
result: +387 lines vs the old base (main's newer rows + B's one session), zero duplicate keys
```

**What I caught.** The naive resolution — keep both sides — produces a file that parses but may reorder or duplicate sessions, and Gate 6 compares rows by `(student_id, phase, session)`. Rebuilding from `main` guarantees "every old row byte-identical, exactly one new row", which is precisely what Gate 6 checks. I also refused to let the agent touch B's transcript: the repair is a merge-mechanics commit, not an edit of her evidence.

**Human decision.** Push the repair onto her own branch (it lives in our repository, not a fork), tell her what changed in a comment, and let the normal protocol run: our review is done with OpenCode in a VM, reviewed with comments on the PR, and merged only after that. The agent prepares the patch; it never merges.

**Reflection.** The recurring conflict was a design smell, not an accident: one append-only file with five writers has no merge semantics. The correct long-term fix is a documented procedure ("always rebuild from main, then append") or one file per member with a merge step. We are writing that into the process section of the report — a conflict that cost us three rounds is exactly the kind of evidence the course asks for.

---

---

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
