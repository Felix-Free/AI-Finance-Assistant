# Phase 2 QA Evidence (owner: role E)

> Purpose: the concrete run record behind the Phase 2 E observations. Every line states what
> was run and what was observed; anything not observed is marked **not verified**.
>
> Implementation: OpenCode with DeepSeek V4 Flash. Verification: separate local QA runs.
> Baseline: `main f73e9b4` + D #18 `eec1724` + C #19 `6808d7e`.
>
> **Baseline note:** some historical scenarios above were verified on `f73e9b4`; the
> integration was refreshed to `main 94b0ec4` with A #12 merged and the D/C inputs unchanged,
> and the full offline suite was rerun on that refresh: 201 passed with network blocked and no
> `logs/`/`data/` produced.

---

## 1. Offline suite (network disabled)

- **Command:** `pytest test/offline -q`
- **Result:** `201 passed`
- **State:** no repository `logs/` or `data/` files were produced by the run.
- **Scope:** local only; this is not a GitHub CI execution.

## 2. Guard-removal negatives (one per invariant)

With each guard disabled individually, the selected corresponding negative test fails:

| Guard disabled | Failed test | Error code |
|---|---|---|
| INV-001 amount | `test_inv001_rejects_negative_amount` | `policy:amount` |
| INV-002 category | `test_inv002_rejects_unknown_category` | `policy:category` |
| INV-003 budget | `test_inv003_rejects_one_cent_over_budget` | `policy:budget` |

Each run executed the selected corresponding test, one case at a time.

## 3. Semantic layer (simulated — not a real run)

- The built-in prompt and a candidate prompt YAML each passed **5** spent/amount/category
  cases.
- A simulated wrong amount produced **4** failures.
- **No real gateway call was made.** This is a simulation of the semantic layer; it is not
  live evidence.

## 4. Gate 1 test-approval (local Git + simulated GitHub reviews)

Run against a real local Git history with simulated GitHub review objects.

| Case | Expected | Observed |
|---|---|---|
| Cross-timezone approval | accept | accepted |
| Docs-only approval | reject | rejected |
| Late approval | reject | rejected |
| Self-approval | reject | rejected |
| Dismissed approval | reject | rejected |
| Non-member approval | reject | rejected |
| Approval on newly modified test | reject | rejected |

This is local logic verification, not an end-to-end GitHub run.

## 5. Schema validation (local)

- The real requirements registry (`docs/req/requirements.yaml`) validates against the
  Draft 2020-12 schema → pass.
- Deleting a required field → validation fails.

## 6. D-reported items (not E measurements)

- **D mypy:** still **4** failures in the fixed integration. Reported here as an observed
  count from the review, not a fix.
- **Original latency and token samples:** missing. No latency/token measurement is recorded.
  D's self-reported latency/token figures, if mentioned, are **D-reported** and are kept
  distinct from any E measurement; they are not treated as a result.

## 7. Open code issues (tracked separately)

These are two different defects and neither resolves the other:

- **Storage partial write:** an interrupted append leaves partial bytes behind (no atomic
  rollback). Not fixed.
- **Log error body:** error text reaches the call log. Not fixed.

## 8. Not verified

- GitHub-hosted CI execution (live run of `ci.yml` / `branch-ci.yml`).
- An end-to-end real test-first review on GitHub.
- A failing PR actually being blocked.
- Any independent online evidence for performance, permissions, or the runtime contract.
