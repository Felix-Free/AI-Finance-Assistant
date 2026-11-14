# Bug Diary (owner: role E)

> Purpose: a symptom → reproduction → root cause → fix → rule-gap record for defects found
> during Phase 2 QA. A bug with no fix says so; it is not closed by being described.
>
> Baseline: `main f73e9b4` + D #18 `eec1724` + C #19 `6808d7e`.

---

## BUG-01 — Gate 1 wrongly accepted a docs-only approval

- **Symptom.** The test-approval gate returned success for an approval whose commit only
  changed documentation.
- **Reproduction.** Run the gate logic against that approval/commit pair; it accepts.
- **Root cause.** Test-only change detection did not exclude docs-only commits from the
  qualified test-first commit set.
- **Fix.** Fixed in this Phase 2 QA pass (gate logic tightened).
- **Rule gap.** Gate 1 must treat a docs-only commit as not satisfying test-first; recorded
  as the rule the fix now enforces.
- **Status.** Fixed; verified by the regression added for it.

## BUG-02 — Offline budget test wrote to the repository logs

- **Symptom.** An offline budget test wrote into the repository `logs/` directory, so a
  deterministic test mutated runtime state.
- **Reproduction.** Run the offline suite and observe `logs/` gaining a line.
- **Root cause.** The test used the default log path instead of an isolated temporary path.
- **Fix.** Fixed in this Phase 2 QA pass (log path redirected to a temporary location).
- **Rule gap.** Offline tests must never write to `logs/` or `data/`; recorded here as the
  rule the fix now enforces.
- **Status.** Fixed; verified by running the suite and confirming `logs/` stays unchanged.

## BUG-03 — Append interruption leaves a partial 16-byte write

- **Symptom.** An interrupted append leaves 16 bytes behind instead of failing atomically.
- **Reproduction.** Interrupt the append path; a partial write of 16 bytes remains.
- **Root cause.** Append-mode writing has no demonstrated rollback of bytes written before
  the error.
- **Fix.** **Not fixed.**
- **Rule gap.** The "no partial state" requirement (RP-007) is stated but not satisfied in
  this writer.
- **Status.** Open.

## BUG-04 — Uncleaned HTTP error body (with a synthetic sensitive marker) leaks into the call log

- **Symptom.** The HTTP error body written into `logs/llm_calls.jsonl` included an uncleaned
  response body carrying a **synthetic sensitive marker**.
- **Reproduction.** Trigger the HTTP-failure path with a body containing the marker and
  inspect the call log.
- **Root cause.** The error log field records an uncleaned response body instead of a
  sanitised/whitelisted value.
- **Fix.** **Not fixed.**
- **Rule gap.** The persistent rule is general: **an error log field must never record an
  uncleaned response body that may contain sensitive information** — this applies to any
  real response, not only to simulation. The marker merely made the violation visible.
- **Status.** Open.
