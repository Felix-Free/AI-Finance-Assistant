# Phase 3 (#24) cleanup and secrets audit (owner: role D)

> Purpose: record the read-only audit behind issue #24 — measurement relocation, code cleanup,
> secrets, storage fail-closed — and state plainly what this PR does and does not change.
> Scope of this PR: documentation only. No `src/`, `scripts/`, `test/` or `.github/` file is
> modified.
>
> Baseline: `main 8533465` (`git rev-parse origin/main`, dated 2026-11-22 Beijing time).
> Every claim below is backed by a command, a file path, or a commit.

---

## 0. Final-state verification (read-only re-audit)

Re-run read-only on `main 8533465` before this document was written, because the product code
changed after #30 (security follow-up #38).

| Check | Command | Result |
|---|---|---|
| HEAD | `git rev-parse HEAD` | `8533465` |
| Working tree | `git status --short` | clean (no tracked changes) |
| Offline suite | `python -m pytest test/offline -q` | `238 passed` |
| Measurement scripts | `ls scripts/measure_latency.py scripts/measure_tokens.py scripts/failure_kind.py` | all present |
| Measurement evidence | `ls docs/measurements/phase2-qa-evidence.md docs/measurements/final-nfr-verification.md` | both present |
| Debug/TODO scan | `git grep -nE "TODO|FIXME|XXX|HACK|breakpoint|pdb" -- src scripts test docs` | no matches |
| `.env` tracked | `git ls-files \| grep -E "(^\|/)\.env$"` | empty |
| Security follow-up | see §5 | present as specified in #38 |

No inconsistency was found; this document was written only after all checks passed.

### Baseline note — NFR measurements vs. this main

The NFR evidence in `docs/measurements/final-nfr-verification.md` was **measured at
`main 06ec2f59`** against a suite that reported **237 passed**. The current `main` is
**`8533465`** and now reports **238 passed**. These are different commits with different test
counts; the `238 passed` figure here is **not** the NFR-measurement commit and is **not** offered
as NFR evidence. The NFR numbers in `final-nfr-verification.md` stand only for `06ec2f59`.

---

## 1. Measurement scripts and documents

Present on `main 8533465`:

- `scripts/measure_latency.py`
- `scripts/measure_tokens.py`
- `scripts/failure_kind.py` — a re-export of `src/failure_kind.py` on current main (the shared
  classifier lives in `src/`; the `scripts/` module re-exports it).
- `docs/measurements/phase2-qa-evidence.md` (E's Phase 2 evidence)
- `docs/measurements/final-nfr-verification.md` (final NFR evidence)

The measurement scripts are already under `scripts/` and both `docs/measurements/` evidence files
exist. **No new measurement data was produced for this task.** No latency, token, or failure
numbers are (re)measured here; the existing evidence stands as previously recorded.

---

## 2. Code cleanup scan

Commands and results on `main 8533465`:

- `git grep -nE "TODO|FIXME|XXX|HACK|breakpoint|pdb" -- src scripts test docs` → **no matches**.
- `git grep -n "print(" -- src scripts` → hits only in:
  - `scripts/measure_latency.py`, `scripts/measure_tokens.py` — CLI output of the measurement
    scripts (progress, summaries, dry-run lines);
  - `src/report_tokens.py` — report table output;
  - `src/call_llm.py` (`__main__` block, lines ~283–287) — demo output when run as a script.

  None of these is debug residue; they are the intended user-facing output of CLI/report/`__main__`
  entry points.
- Contract/probe/demo constants (`git grep -nE "1000\.0|350" -- src scripts`):
  - `src/pipeline.py:40` — `budget_limit: float = 1000.0` (contract default budget; PD-003 still
    pending, so it is not a hard-coded value to delete);
  - `scripts/measure_latency.py:37` and `scripts/measure_tokens.py:35` — the `"hotpot last night
    cost 350"` probe/corpus text;
  - `src/call_llm.py:282` — `"昨晚吃火锅花了 350"` demo text in the `__main__` block;
  - `scripts/measure_latency.py:70` — `* 1000.0` seconds→milliseconds unit conversion.

**Conclusion: no safe code cleanup; no code changes.** There is no debug/dead code to remove.
A `print` removal would break CLI/report/demo output, and the constants are contract, measurement,
or demo values, not magic numbers.

---

## 3. Secrets

- `.env` is **never committed**: `git ls-files | grep -E "(^|/)\.env$"` is empty, and
  `git log --all --oneline -- .env` shows no history.
- `.env.example` is tracked and contains only a placeholder: `LLM_API_KEY=sk-REPLACE_ME`.
- No other key/token/`Bearer`/credential markers in `src/`, `scripts/`, `docs/`
  (`sk-…`, `Bearer …`, `LLM_API_KEY=` scanned; only the placeholder matches).
- `agent.env` is **not tracked** and `.gitignore` does **not** explicitly list it. This is an
  owner decision (AGENTS §3 says "if present"); it is recorded here as a defensive gap, not a
  leak, and is **not changed** in this PR.

**Conclusion: secrets scan is clean.**

---

## 4. Demo

Role D's 3-minute product-comparison segment was prepared per `DEMO_D_SCRIPT.md` (budget boundary
`990 + 10` accepted / `+11` rejected, and the same synthetic HTTP 503 log before/after). The
segment was **sent on 2026-11-22**. This is a delivery record, not a code claim.

---

## 5. Storage fail-closed and the #38 security follow-up

Storage fail-closed and the audit-redaction security work are delivered on `main` by earlier PRs;
this audit **does not re-implement** them.

- **#30 (storage fail-closed):** single temporary file + file lock + `os.replace` with commit-point
  semantics; covered by `test/offline/test_phase3_concurrency.py` and
  `test/offline/test_phase3_hardening.py`.
- **#38 (security follow-up):** confirmed present in the current code:
  - **A′ redaction:** `src/call_llm.py::_redact` turns `input`/`raw` into `redacted:len=<n>` and
    `parsed` is written as `None`; the `policy:*` review line forces `amount/category/spent/total`
    to `None` and keeps the safe `error` code and `review` flag (`src/pipeline.py`).
  - **Locked budget:** the pipeline uses the locked persisted total as the authoritative budget
    input; it calls
    `storage.append_validated(record, expected_spent=persisted, origin=storage._PIPELINE_ORIGIN)`
    (`src/pipeline.py:109-111`). The public `append_validated` keeps direct semantics:
    `expected_spent < persisted` → `StorageError` (`src/storage.py:263-305`). An over-budget
    rejection raises `PolicyError(policy:budget, review=True)` and writes exactly one redacted
    review line, no ledger row.
  - **Safe errors:** `StorageError` (`src/storage.py:57`) messages carry no paths, raw `OSError`
    text, URLs, bodies, or business values.
  - **ADR:** `docs/architecture/adr/004-pipeline-budget-and-audit-redaction.md` records the
    decision.

---

## 6. Known limitations and unresolved debt

Recorded here, **not fixed** in this PR.

### 6.1 From the #38 security follow-up (`PR38_KNOWN_LIMITATIONS.md`)

1. `logs/review.jsonl` is still **append-mode, not atomic**: a failed open is fail-closed and
   tested, but a mid-write partial line is theoretically possible and untested.
2. `_PIPELINE_ORIGIN` is a **controlled internal marker, not a hard security boundary**; code that
   can import `storage` can still reach `_append_from_pipeline`.
3. **Private storage API coupling:** `pipeline.process` depends on the private
   `storage._append_from_pipeline` via the sentinel.
4. `raw` **length for HTTP/protocol failures** is the truncated `resp.text[:500]` length, not the
   full body length when the body exceeded 500 characters.
5. `spent` passed to `pipeline.process` is now **advisory**; the persisted total is authoritative,
   so callers must seed storage instead of relying on `spent`.
6. The **security-boundary claim is not fully verified**: a green hosted job does not prove branch
   protection is active or that the six checks block a bad merge.

### 6.2 From `docs/debt-register.md` (unresolved as of this PR)

- **DEBT-01 / DEBT-02** (guardrail debt): the register still reads "verified on #30; pending main"
  even though #30 is now merged into `main`. This is a **stale debt-register status**: it is
  recorded here for the register's owner (role E) to update. This PR does **not** mark DEBT-01/02
  resolved and does **not** edit `docs/debt-register.md`.
- **DEBT-03** (evaluation debt): the three guard-removal negatives are observed only locally, not
  in GitHub CI — **open**.
- **DEBT-04** (evaluation debt): test-first evidence on #30 is **partially verified**; enforcement
  tracked under DEBT-08.
- **DEBT-05** (evaluation debt): merge-time live execution against the protected environment is
  **pending**.
- **DEBT-06** (evaluation debt): PR #19 permissions / runtime-contract / performance are backed
  only by local review — **pending**.
- **DEBT-08** (evaluation debt): required-check enforcement of the six PR gates is **open**; a real
  blocked-PR proof is still pending.
- **DEBT-07** was closed on `df729a9` (mypy clean after the historical `eec1724` failures) and is
  not open.

---

## 7. Pending decisions (must be re-checked at PR time)

- **PD-002** — category whitelist final vocabulary — is `status: pending_confirmation` (owner C)
  in `docs/req/requirements.yaml`. **Pending; not confirmed.**
- **INV-PENDING-01** — exact category whitelist membership final — is `NOT_VERIFIED`
  ("finality unconfirmed", owner C) in `docs/architecture/trace-matrix.md`. **Pending; not
  confirmed.**

This document does not claim either is confirmed. If the owners later confirm them in
`invariants.md` / the trace matrix, the status is re-checked at PR time.

---

## 8. Result for #24

| #24 item | Result |
|---|---|
| Measurement scripts / `docs/measurements` | Already on `main`; no new measurement produced |
| Code cleanup | Scanned; no safe cleanup; no code changes |
| Secrets | Clean; `agent.env` gitignore gap is an owner decision, unchanged |
| Storage fail-closed | Delivered by #30 and #38; not re-implemented |
| Demo | D segment prepared and sent 2026-11-22 |
| Pending decisions | PD-002 / INV-PENDING-01 still pending |

Issue #24's repository change is therefore this audit document plus one AI-use-log entry; no
product code is changed.
