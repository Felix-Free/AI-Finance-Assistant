# AI Interaction Transcript

- Student ID: 60357951
- Student Name: QingZhi LU
- Project: AI-Finance-Assistant

> Annotated transcript of my work with the AI coding agent (OpenCode).
> Every entry records what I instructed, what the agent produced, what I caught, and what I
> changed. This file is evidence of human authorship and supervision, not of independent AI work.
>
> Role: **B — Requirements & Architecture.** I own `docs/req/requirements.yaml`, the traceability
> matrix, the ADRs, the risk list and the option ledger. Other roles (A leader, C security,
> D implementation, E verification) own their own files. This transcript records where I
> constrained the agent, where I caught it being wrong or overreaching, and where I decided.

---

## Session 1 — 2026-11-15/16 · Role B Phase 2 (Issue #13): ADR, NFR quantification, traceability, NFR evidence

**Record scope.** This entry is reconstructed from the actual session conversation. Where a
command output is quoted, it is the real output the agent produced during the session. The
conversation covered several distinct work bursts: (a) read-only audits of the repository and
other roles' branches, (b) a backup of the working tree before syncing, (c) authoring the Phase 2
Role B deliverables in three batches, (d) auditing and correcting factual claims, and (e) a CI
runner fix (which I later flagged as outside role B). It is recorded as one session topic because
it is one continuous working thread on Issue #13.

### Conversation Transcript

**Me (initial task):** Open Role B Phase 2 per GitHub Issue #13 ("Phase 2: Architecture Decision
Records (ADR) and NFR Quantification"). This round is a **read-only audit only** — do not create,
modify or delete any file, do not run git add/commit/push/merge. Check git state, the Phase 2 task
files, and compare against Issue #13; report what is implemented, tested, pending-merge,
unconfirmed and not-yet-implemented. Explicitly: do not infer that functionality exists just from
a file name; do not invent NFR thresholds; do not approve policy on behalf of role C; do not
fabricate performance/token data. End with a suggested execution order.

**Agent:** Produced a read-only audit. It reported the branch was `docs/role-b-phase1` (not main),
HEAD `dba35b0`, 4 ahead / 4 behind `origin/main`. It found `docs/architecture/adr/` contained only
`.gitkeep`, `risk-list.md` and `option-ledger.md` did not exist, `Requirements.yaml` still lacked
NFR thresholds, and it flagged that `gh` CLI was **not installed** so it could not verify PR
status. It classified the deliverables and proposed an execution order.

**Me (audit follow-ups, several rounds):** I kept pressing for ground truth rather than the agent's
assumptions:
- "Read-only check of the branch, HEAD, origin/main, working tree; check whether commit `dee59f7`
  was pushed; check whether PR #10 exists, is open/merged, its review and CI status — if you cannot
  reach GitHub, state clearly that it is unverified, do not infer from local git."
- "Investigate `origin/feat/D-phase2-storage` and the D Phase 2 branch; check the *actual code*,
  not file names — does it contain request_id, session_id, call_id, input/output/total tokens,
  usage source, missing-usage handling?"
- "D says measure scripts moved from `src/` to `scripts/` (PR #18, commit `a420987`), and
  `_append_review` may have been renamed. Verify all of this against the actual files and git
  history. Do not just accept D's message."

**Agent (one such audit):** Reported `origin/main` was `94b0ec4`, that the `docs/role-b-phase1`
branch was **0 ahead / 30 behind**, that Role B's Phase 1 docs were already merged into main, and
that the working tree was **not clean** — it contained 10 modified files plus a **broken
`docs/ai-use-log.yaml`** with a leftover conflict marker `=======` at line 255. It also flagged
that the branch `feat/D-phase2-storage` had **no storage code at all** (only two docs changes) and
that `user_request_count` was **not implemented** anywhere.

**Me (catching the broken ai-use-log and the divergence):** "The working tree has a broken YAML in
`docs/ai-use-log.yaml` and the branch has diverged. Before any sync, back up the current working
tree *outside* the repo (`/Users/luuu/semA/cs5351/backups/...`), verify the backup restores with
SHA-256, distinguish `.DS_Store`/`.bak` garbage from real work, and do not commit them. Do not run
any destructive git operation yet; only report the sync plan."

**Agent:** Created the external backup, captured `git diff HEAD` into a patch, copied the untracked
`requirements.yaml.bak`, verified all files with SHA-256 (all OK), and proved the patch re-applied
to a throwaway temp clone reproduced the exact working tree. It confirmed the 3 modified docs had
uncommitted changes and explicitly corrected its earlier wording to **"3 docs are modified, not
clean"**.

**Me (green-lighting authoring in batches):** "Confirmed — start Role B Phase 2. Execute in three
batches, one file group at a time, checking diff + YAML + schema after each. Batch 1:
`requirements.yaml` + `trace-matrix.md`. Batch 2: the two ADRs. Batch 3: `risk-list.md` +
`option-ledger.md`. Hard constraints: only touch NFR-001/002/006 descriptive fields; do **not**
change threshold/owner/status; `user_request_count` is recorded only as an unimplemented gap,
do **not** invent a metric; PD-007/PD-008 stay pending; never write D's branch results as
main-implemented; skipped tests are never 'passed'."

**Agent:** Edited NFR-001/002/006 `verification`/`notes` only. Validated with `jsonschema` →
"errors: 0". Rewrote the trace matrix NFR rows to use a **four-state label set**
(`main-implemented` / `D-branch-implemented-unmerged` / `test-pending` /
`runtime-evidence-pending`) and added a Runtime Monitor column (all `—`). It explicitly wrote that
`test_evidence_join.py` was **skipped** on D's branch and is **not** a passing test.

**Me (ADR decisions):** "Approved the batch-2 ADRs. The two files are
`001-ai-layered-context-structure.md` and `002-token-budget-cap.md`. Each must contain Context,
Decision, Alternatives, Consequences and a multi-round ADD design process. Mark both
**Design-only / Not yet verified as implemented**. The token cap numeric value must be marked
**Pending PD-007** — do not fill in a number."

**Agent:** Wrote both ADRs with the required sections and an explicit "Design-only / not yet
verified" banner and "Pending PD-007" on every quantity. It stated the ADD rounds were "design
reasoning, not run experiments".

**Me (batch 3):** "Approved batch 3. Create `risk-list.md` and `option-ledger.md`. Cover the
required risks and options; every risk/option needs ID, Owner, Status, Evidence. Leave Likelihood
and Impact as `TBD` — do not score them. Do not approve PD-007/PD-008 or decide
`user_request_count` on D's behalf."

**Agent:** Created both files with `RISK-001..008` and `OPT-001..007`, all scores `TBD`, statuses
`Open` / `Pending Confirmation`. Markup table integrity verified.

**Me (final pre-commit review):** "Now do a final read-only cross-file consistency review. Check
NFR-001/002/006 wording matches between requirements and trace-matrix; ADR-001 ↔ OPT-007;
ADR-002 ↔ OPT-003/RISK-005; PD-002/007/008 never approved; Runtime Monitor not faked from logs;
D/E branch results labelled with branch + unmerged; and tell me whether the trace-matrix
§3/§4/§5 Phase-1 history is still consistent or stale."

**Agent:** Found that §3/§5 of the trace matrix were **factually stale** — main already had
`ci.yml`/`pytest.ini`/requirements additions, and E's branch actually had 12 INV tests (not "two
INV-001"). It recommended fixing before commit.

**Me (fact-sync authorization):** "Approved fixing trace-matrix §3/§4/§5 and refreshing branch
snapshots. Preserve Phase-1 history and mark it as historical; update the current baseline to the
verified main commit; mark D/E work as unmerged; distinguish local tests vs CI vs skipped; keep the
37-row count unless you can prove otherwise; do not delete history."

**Agent:** Rewrote §3 with a two-column Phase-1-vs-now table, fixed §4 to note D's measurement code
was on an unmerged branch (not main), did not touch the 37-row tally, and refreshed E SHA. Verified
only the 3 authorized files changed.

**Me (later — catching a wrong count):** "The reviewer says several places still say D and C are
UNMERGED although PR #18 (`f2442c2`) and PR #19 (`c71610c`) are on main now. Refresh
`trace-matrix.md` main HEAD, the D and C UNMERGED lines, the NFR-001 row ('implemented on main,
runtime evidence not committed, PD-007'), `evaluation-table.md` (4 test functions skipped, **not**
5), and in `requirements.yaml` lines 233/244/285/239/280/595. Suggested status:
`IMPLEMENTED_ON_MAIN; runtime-evidence-pending`. If you cannot verify a fact from `origin/main`
files or git history, keep the original text and mark it pending — do not guess."

**Agent:** Verified with local git that `f2442c2`/`c71610c` are ancestors of `origin/main`, that
`df729a9`/`01e3bc7` are in main, and `cab1901` (E) is not; that `test_evidence_join.py` on main has
4 test functions all skipped by a module-level `pytestmark`. It then refreshed the statuses. It
reported clearly that `git fetch origin` **failed** (network unreachable) so it used the last
successfully fetched `origin/main = f2442c2` and **did not claim** GitHub main was confirmed live.

**Me (deleting a stale label):** "There's still a `D-branch-implemented-unmerged` label definition.
If no row actually uses it, delete the definition; if used, judge each. Keep E's real unmerged
state. Also correct your report: 3 docs are modified — do not call the tracked tree clean."

**Agent:** Grepped → no requirement row used the label → removed the definition and the prose
mention, and corrected `main-implemented` to cite `f2442c2`. It re-stated the true
`git status --short` (3 modified docs + 5 untracked).

**Me (CI question):** "Fix the GitHub Actions `offline-tests` Python 3.9 failure
(`The version '3.9' with architecture 'x64' was not found for Ubuntu 26.04.`). Inspect first.
If the project needs 3.9, change the `offline-tests` runner from `ubuntu-latest` to `ubuntu-24.04`,
keep `python-version: 3.9`, do not upgrade the project and do not touch other jobs."

**Agent:** Inspected `ci.yml` (single job `offline-tests`), confirmed Python 3.9 is the documented
baseline, and changed `runs-on: ubuntu-latest` → `ubuntu-24.04` (1 line), keeping `python-version:
"3.9"`. Ran local `pytest test/offline -q` → "158 passed, 4 skipped", and explicitly said local
results are **not** GitHub Actions results.

**Me (boundary catch):** "Which role owns this document?" — I challenged whether the CI change was
within role B's authority.

**Agent:** Confirmed `.github/workflows/**` is **role E's** ownership and, per AGENTS.md, a
human-only path — i.e., the CI edit was outside role B's authorization. It offered to revert it.

### 【人类批注】

1. **干预目的**：The agent kept drifting toward *claiming* things (that data was merged, that
   tests passed, that the branch was clean) and toward overreach (editing CI, inventing numbers).
   My job was to hold it to verifiable, file- and git-based facts and to the role-B file boundary.

2. **发现的问题**：
   - The agent's earlier "audit" missed the real (unmerged) D measurement branch and initially
     treated the working tree as clean when a `docs/ai-use-log.yaml` was actually broken
     (`=======` at line 255).
   - It carried stale Phase-1 facts in the trace matrix (CI "not on main", E "only two INV-001")
     that were contradicted by the actual repo.
   - It reported a "5 skipped" figure where the real number of skipped test functions is 4.
   - It overreached into CI (`ci.yml`), which is role E's and a human-only path.
   - Agent output repeatedly tried to state unverified GitHub/PR status as fact.

3. **具体干预**：
   - Required read-only audits first and forbade writes until I approved each batch.
   - Required an **external backup with SHA-256 restore proof** before any sync.
   - Constrained the edit scope to specific role-B files and named fields (no threshold/owner/
     status changes; `user_request_count` only as a gap).
   - Mandated `Design-only / PD-007 pending` labelling on ADRs.
   - Demanded `origin/main`/git-history evidence for every "merged/unmerged" claim and that the
     agent state when network was unavailable rather than infer.
   - Told it skipped ≠ passed, implementation merged ≠ evidence complete, CI file exists ≠ CI run
     passed.
   - Challenged the CI edit and had the agent admit it belonged to role E.

4. **干预效果**：The agent switched to grep/git-verified claims, corrected the broken-YAML and
   clean-tree misstatements, removed the stale `D-branch-implemented-unmerged` label, fixed the
   4-vs-5 skipped count, added explicit "network unavailable / not live-verified" caveats, and
   flagged its own out-of-scope CI edit.

5. **人工判断**：
   - **Human decided**: the identity/scope of each batch, that ADRs are design-only, that
     PD-002/007/008 stay pending, that D/C are merged while E is not, the 36-vs-37 counting basis,
     and that CI is not role B's to change.
   - **Agent executed**: the mechanical edits, greps, schema validation, backups, and diff checks.
   - **Still needs confirmation**: the live GitHub state (network was down; `gh` unavailable),
     whether to revert the out-of-scope CI edit, and leader (@Felix-Free) review/merge.

### Human-in-the-Loop Stage

- **Requirements** — I constrained NFR-001/002/006 to descriptive fields, forbade inventing
  thresholds/metrics, and kept PD-007/PD-008 pending.
- **Architecture** — I required ADR-001/002 to contain Context/Decision/Alternatives/Consequences
  and a real ADD process, marked design-only, and required the agent to justify rather than assert.
- **Planning** — I ordered the work into three batches, set per-batch file boundaries, and
  forbade writes/commits until each batch was verified.
- **Construction** — I directed the exact files and fields to edit and had the agent track
  untracked files and never commit `.DS_Store`/`.bak`.
- **Verification** — I demanded SHA-256 backup proof, `jsonschema` validation, `git diff --check`,
  and insisted on distinguishing local tests vs CI vs skipped, and on evidence for every
  "merged/unmerged" claim.
