# Risk List (owner: role B)

> Living register of integration and evidence risks for Phase 2 (Issue #13), written by role B.
> Sources are the **current `main`** and the **verified** unmerged branches
> `origin/feat/D-phase2-measurement` (`df729a9`), `origin/feat/e-phase2-verification` (`cab1901`),
> `origin/feat/c-phase2-policy-60339160` (`01e3bc7`). **Branch state verified as of 2026-11-16**;
> the SHAs are review-time identifiers, not a claim of being permanently current. Nothing here claims
> unmerged code is on `main`, that skipped tests passed, or that uncommitted measurements are verified.
>
> **Scoring policy.** Likelihood and Impact are left **`TBD`** unless the project material
> supports a value. This register does **not** invent scores. It also does **not** approve any
> pending decision (PD-002, PD-007, PD-008).

---

## Risk register

| Risk ID | Description | Likelihood | Impact | Mitigation | Owner | Status | Evidence / Source |
|---|---|---|---|---|---|---|---|
| RISK-001 | D's Phase 2 implementation (storage, token capture, measurement scripts, call_id threading) exists only on `feat/D-phase2-measurement` and is **not on `main`**; describing it as "implemented in the product" would be false. | TBD | TBD | Track merge status per PR; keep branch-qualified wording ("…on `feat/D-phase2-measurement`, unmerged") until merged; re-verify after merge. | D / A | Open | `origin/feat/D-phase2-measurement` `df729a9`, 24 ahead / 0 behind `main` (verified 2026-11-16); not an ancestor of `main` (`git merge-base --is-ancestor` = false). |
| RISK-002 | Latency (NFR-001) and Token (NFR-002) measurements have **no committed runtime evidence**; `logs/`/`data/` are runtime artifacts, and D-reported figures are self-reported, not independent verification. | TBD | TBD | E to run and commit evidence (or a `docs/measurements/` report); B to cite only committed evidence; never treat D-reported numbers as acceptance data. | E (runs) / B (records) | Open | `trace-matrix.md` NFR-001/002 rows = `runtime-evidence-pending`; `docs/measurements/phase2-qa-evidence.md` (E, unmerged) states original latency/token samples missing. |
| RISK-003 | `test/offline/test_evidence_join.py` is in **different states across roles**: **5 skips** on D's branch, **0 skips** on E's branch, **absent on `main`**. A skipped test must not be read as passing; the join is unverified on `main`. | TBD | TBD | Only count the join as verified once it is un-skipped, run, and on `main`; keep "skipped ≠ passed" in docs; E to complete assertions and land via PR. | E / D | Open | D branch (`df729a9`) skip count = 5; E branch (`cab1901`) skip count = 0; `main` has no such file. |
| RISK-004 | `user_request_count` (distinct `request_id`) is **not implemented**; whether to add it is a **B-owned metric decision** still to be confirmed with D. Adding it silently would inflate/alter the metric set. | TBD | TBD | Record as a pending gap; B decides whether the metric is added; D implements only after confirmation; do not report it as existing. | B / D | Open | `requirements.yaml` NFR-002 (states NOT implemented); D branch `git grep user_request_count` = 0. |
| RISK-005 | **PD-007 not approved**: NFR-001/NFR-002 numeric thresholds and all token-ceiling/history/at-limit values are `pending_confirmation`. Using any number as if approved would fabricate a decision. | TBD | TBD | Keep `threshold: null`; keep status `pending_confirmation`; ADR-002 and API text mark every value "Pending PD-007". | B | Open | `requirements.yaml` NFR-001/002 (`threshold: null`, PD-007); ADR-002 §2/§6. |
| RISK-006 | **PD-008 not approved**: NFR-003/NFR-006 thresholds and the retry/at-limit policy are `pending_confirmation` under owner C. | TBD | TBD | Keep NFR-003/006 `threshold: null`; do not encode a retry policy; leave retry decisions to C. | C | Open | `requirements.yaml` NFR-003/006 (PD-008); no retry implemented (`src/call_llm.py` makes at most one attempt). |
| RISK-007 | **No confirmed Runtime Monitor** exists. Log files (`llm_calls.jsonl`, `review.jsonl`, `records.jsonl`) are outputs, not continuous monitoring. Implying they are a monitor would be misleading. | TBD | TBD | In the Architecture Component field of `trace-matrix.md`, use `—` when no genuine Runtime Monitor component exists. | B | Open | `trace-matrix.md` Architecture Component field (Runtime Monitor) all `—` (§1.3 definition); no monitor component in `src/`. |
| RISK-008 | **Cross-branch integration / doc-sync risk**: C branch (`01e3bc7`, 19 ahead / 17 behind), D branch (`df729a9`), and E branch (`cab1901`) are all unmerged and C's branch is behind `main`, so merging may conflict and shared docs (e.g. `evaluation-logbook.md`, `permissions`, `invariants.md`, `runtime-policy-catalog.md`) can diverge between branches and `main`. | TBD | TBD | Merge in a coordinated order; keep role-owned docs edited only by their owners; re-verify shared docs after each merge; B must not edit C/E/A files. | A / C / D / E | Open | Branch relation vs `main` (verified 2026-11-16): C 17 behind / 19 ahead, D 24 ahead, E 47 ahead; C branch modifies shared C-owned docs. |

---

## Notes and non-claims

- **No scores are assigned.** Likelihood/Impact remain `TBD` pending team input; the RAG/scoring of
  these risks is not decided here.
- **Status `Open`** means "present and unresolved", not "accepted". No risk is marked closed.
- **Nothing here approves** PD-002, PD-007, or PD-008, and nothing asserts unmerged code is on
  `main`, that skipped tests passed, or that measurements are verified.
- Related design context: ADR-001 (context structure) and ADR-002 (token budget); requirement
  rows: `requirements.yaml` NFR-001/002/006/007; status labels: `trace-matrix.md` §1.3.
