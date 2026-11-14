# Debt Register (owner: role E)

> Purpose: track known Phase 2 debt against the fixed baseline, using the course's **D4
> eight AI-era debt categories**. Each item records owner, status and evidence; a category
> with no reproduced item is marked **monitored** rather than invented as an item.
>
> Baseline: `main f73e9b4` + D #18 `eec1724` + C #19 `6808d7e`.

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
| DEBT-01 | Guardrail debt | Append interruption leaves a 16-byte partial write; no atomicity, so a guard boundary is stated but not enforced by this writer | D | open | BUG-03, reproduced |
| DEBT-02 | Guardrail debt | An unredacted synthetic HTTP error body reaches `logs/llm_calls.jsonl`; an error log field must not carry an uncleaned response body that may contain sensitive data | D | open | BUG-04, reproduced |
| DEBT-03 | Evaluation debt | Three guard-removal negatives observed only locally, not yet run in GitHub CI | E | open | local runs only |
| DEBT-04 | Evaluation debt | Real test-first approval and a failing-PR block not yet demonstrated end-to-end | E | pending | Gate 1 local only |
| DEBT-05 | Evaluation debt | Merge-time live execution against the protected environment not yet run | E | pending | no merge-time evidence |
| DEBT-06 | Evaluation debt | PR #19 permissions / runtime-contract / performance backed only by local review, no independent online evidence | C | pending | local review only |
| DEBT-07 | Untouchable code | mypy reports 4 failures in the fixed integration (PR #18); the affected code is not safely editable until typed | D | open | reproduced locally |

---

## Category coverage

| D4 category | Status | Note |
|---|---|---|
| Prompt rot | active | Production uses `SYSTEM_PROMPT` in `src/call_llm.py`; CI can replay candidate runtime YAML through a test fixture. Confirm runtime loading before adopting versioned prompts. |
| Hallucinated dependencies | monitored | no reproduced item; No invented dependency was identified in the measured set. |
| Untouchable code | active | DEBT-07 |
| Hidden dependencies | monitored | no reproduced item; transport confined to `call_llm.py` (Gate 2) |
| Agent-induced bloat | monitored | no reproduced item |
| Evaluation debt | active | DEBT-03..06 |
| Guardrail debt | active | DEBT-01, DEBT-02 |
| Human/cognitive debt | active | real first approval not yet demonstrated end-to-end (DEBT-04) |

---

## Ownership note — protected environment

The protected `semantic-eval` environment (repository variables `LLM_BASE_URL`, optional
`LLM_MODEL`, secret `LLM_API_KEY`, manual approval) is **configured by role A and verified by
role E**. E's verification of it is outstanding (DEBT-04, DEBT-05).

## Outstanding (explicit)

- **Real first approval** on GitHub — not demonstrated (DEBT-04).
- **Protected environment** exercised — not demonstrated; A configures, E verifies (DEBT-04).
- **Merge-time live execution** — not demonstrated (DEBT-05).

These remain open regardless of any local pass and are the first items required before a
Phase 2 sign-off.
