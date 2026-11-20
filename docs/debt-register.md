# Debt Register (owner: role E)

> Purpose: track known Phase 2 debt against the fixed baseline, using the course's **D4
> eight AI-era debt categories**. Each item records owner, status and evidence; a category
> with no reproduced item is marked **monitored** rather than invented as an item.
>
> Baseline (historical): `main f73e9b4` + D #18 `eec1724` + C #19 `6808d7e`.
> **Refreshed 2026-11-16 (Beijing time)** to `main 94b0ec4` + D #18 `df729a9` + C #19
> `6808d7e`; D fixed the mypy errors in `959ac97` and E reran the checks locally.
>
> Phase 3 #25 refresh (2026-11-17) records evidence against PR #20 head `b82ac6d` on
> `review/e-phase2-base`. Baselines and historical rows above are preserved; no unresolved
> item is closed by this refresh.

---

## Categories (D4, AI-era eight)

1. Prompt rot · 2. Hallucinated dependencies · 3. Untouchable code ·
4. Hidden dependencies · 5. Agent-induced bloat · 6. Evaluation debt ·
7. Guardrail debt · 8. Human/cognitive debt.

Category status is **active** when a reproduced item maps to it, **monitored** when no item
is reproduced yet (kept visible, not claimed clean).

---

## Register

| ID | Category | Item | Owner | Status | Evidence |
|---|---|---|---|---|---|
| DEBT-01 | Guardrail debt | Append interruption leaves a 16-byte partial write; no atomicity, so a guard boundary is stated but not enforced by this writer | D | verified on #30; pending main | BUG-03 was fixed on PR 30, branch `571564d` only. |
| DEBT-02 | Guardrail debt | An unredacted synthetic HTTP error body reaches `logs/llm_calls.jsonl`; an error log field must not carry an uncleaned response body that may contain sensitive data | D | verified on #30; pending main | BUG-04 was fixed on PR 30, branch `571564d` only. |
| DEBT-03 | Evaluation debt | Three guard-removal negatives observed only locally, not yet run in GitHub CI | E | open | local runs only; #20 green CI does not run these negatives |
| DEBT-04 | Evaluation debt | Test-first approval and merge blocking | E | partially verified | Human test-first approval is evidenced on GitHub at `22cdf96`; an actual forced merge block was not demonstrated. |
| DEBT-05 | Evaluation debt | Merge-time live execution against the protected environment not yet run | E | pending | On #20 the protected Gate 4 passed 5/5, but actual merge-time live execution remains unverified. |
| DEBT-06 | Evaluation debt | PR #19 permissions / runtime-contract / performance backed only by local review, no independent online evidence | C | pending | local review only |
| DEBT-07 | Untouchable code | mypy reported 4 failures in the fixed integration (PR #18) on `eec1724`; D fixed them in `959ac97` and E's local rerun on `df729a9` (mypy 1.8, Python 3.11) is clean across eight source files, so the affected code is now typed | D | closed | closed on `df729a9` after local rerun; historical: reproduced locally on `eec1724` |

---

## Category coverage

| D4 category | Status | Note |
|---|---|---|
| Prompt rot | active | Production uses `SYSTEM_PROMPT` in `src/call_llm.py`; CI can replay candidate runtime YAML through a test fixture. Confirm runtime loading before adopting versioned prompts. |
| Hallucinated dependencies | monitored | no reproduced item; No invented dependency was identified in the measured set. |
| Untouchable code | monitored | no open reproduced item; DEBT-07 closed on `df729a9` (mypy clean in local rerun). The 4-error state was historical to `eec1724`. |
| Hidden dependencies | monitored | no reproduced item; transport confined to `call_llm.py` (Gate 2) |
| Agent-induced bloat | monitored | no reproduced item |
| Evaluation debt | active | On #20 the protected Gate 4 passed 5/5, but actual merge-time live execution remains unverified. |
| Guardrail debt | active | DEBT-01/02: Verified on #30 head `571564d`; main integration and rerun are still pending. |
| Human/cognitive debt | active | Human test-first approval is evidenced on GitHub at `22cdf96`; an actual forced merge block was not demonstrated. |

---

## Ownership note — protected environment

The protected `semantic-eval` environment (repository variables `LLM_BASE_URL`, optional
`LLM_MODEL`, secret `LLM_API_KEY`, manual approval) is **configured by role A and verified by
role E**. The protected `semantic-eval` job was **exercised** on the real #20 PR path
(job 133284009010, 5 passed in 9.35 s), so the environment is no longer "never exercised".
Manual approval enforcement, merge-time execution and the main-required gate checks remain
unverified (DEBT-04, DEBT-05).

## Outstanding as of 2026-11-20

- On main `35f580d`, all 211 offline tests passed and static analysis passed: [CI run](https://github.com/Felix-Free/AI-Finance-Assistant/actions/runs/44677721024).
- Human test-first approval is evidenced on GitHub at `22cdf96`; an actual forced merge block was not demonstrated.
- #32 merged after Gate 1 failed and Gate 4 was skipped. Proof of enforced six required checks and of a real blocked PR is still pending: [CI run](https://github.com/Felix-Free/AI-Finance-Assistant/actions/runs/44561573231).
- On #20 the protected Gate 4 passed 5/5, but actual merge-time live execution remains unverified.
