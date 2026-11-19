# Phase 2 QA Evidence (owner: role E)

> Purpose: the concrete run record behind the Phase 2 E observations. Every line states what
> was run and what was observed; anything not observed is marked **not verified**.
>
> Implementation: OpenCode with DeepSeek V4 Flash. Verification: separate local QA runs.
> Baseline: `main 94b0ec4` + D #18 `df729a9` + C #19 `6808d7e`.
>
> **Baseline note:** the original baseline was `main f73e9b4` + D #18 `eec1724` + C #19
> `6808d7e`; its historical observations below stay identifiable as such. The integration was
> refreshed (as of 2026-11-16 Beijing time) to `main 94b0ec4` + D #18 `df729a9` + C #19
> `6808d7e`. D fixed the four mypy errors (`eec1724` → `959ac97`, current #18 HEAD
> `df729a9`); E verified mypy 1.8 on Python 3.11: success in eight source files, and a clean
> isolated offline run still passed 201 tests with sockets blocked and no `logs/`/`data/`
> produced.

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

- **D mypy:** the earlier **4** failures on `eec1724` are historical. On `df729a9` (after D's
  `959ac97` fix) E verified mypy 1.8 on Python 3.11: **success in eight source files** (no
  errors). This is an E-observed local run, not a GitHub CI execution.
- **Original latency and token samples:** missing. No latency/token measurement is recorded.
  D's self-reported latency/token figures, if mentioned, are **D-reported** and are kept
  distinct from any E measurement; they are not treated as a result.

## 7. Open code issues (tracked separately)

These are two different defects and neither resolves the other. Both were re-tested on the
refresh (`df729a9`) with the same fault injection and **both remain open**:

- **Storage partial write:** an interrupted append still left **16 bytes** behind on
  `df729a9` (no atomic rollback). Reproduced on the refresh; not fixed.
- **Log error body:** the synthetic HTTP error marker still entered the error field on
  `df729a9`. Reproduced on the refresh; not fixed.

## 8. Not verified

- GitHub-hosted CI execution (live run of `ci.yml` / `branch-ci.yml`).
- An end-to-end real test-first review on GitHub.
- A failing PR actually being blocked.
- Any independent online evidence for performance, permissions, or the runtime contract.
