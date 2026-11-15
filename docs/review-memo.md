# Review Memo (owner: role E — QA review of D #18 and C #19)

> Purpose: a short, PR-by-PR record of the Phase 2 QA review findings against the fixed
> integration baseline. Written from local review and observed runs only.
>
> Baseline (historical): `main f73e9b4` + D #18 `eec1724` + C #19 `6808d7e`.
> **Refreshed 2026-11-16 (Beijing time)** to `main 94b0ec4` + D #18 `df729a9` + C #19
> `6808d7e`; D fixed the mypy errors in `959ac97`. E reran mypy 1.8 on Python 3.11 (success in
> eight source files) and the isolated offline suite (201 passed, sockets blocked). This is a
> local recheck; **no new GitHub review was posted.** Each PR is reviewed on its own; a green
> local suite is not a substitute for GitHub CI, which is not verified here.
>
> **Result labels (read carefully).** Two different numbers exist and must not be conflated:
> **#18 = 191 is the old local integration result**; **the current 201 is the new OpenCode
> integration result**. Neither is a D-only run and neither is a GitHub live run.

---

## PR #18 — `eec1724` (role D: storage / spend defence)

**Added.** A direct-write defence and a low-reported-`spend` defence, so a caller cannot
bypass the invariants with a small caller-supplied `spend` and a direct `append_validated`
call is no longer free to write policy-invalid values.

**Findings.**

1. **mypy: 4 failures on `eec1724`→ fixed on `df729a9`.** The four errors reproduced on
   `eec1724`; D fixed them in `959ac97`. E's local recheck on `df729a9` (mypy 1.8, Python
   3.11) reports success in eight source files. Status: **closed in local recheck** (not a
   GitHub CI run).
2. **Append interruption leaves 16 bytes.** Still reproduced on the refresh (`df729a9`) with
   the same fault injection: an interrupted append leaves a partial 16-byte write behind.
   This contradicts the "no partial state" boundary the policy catalog requires; status:
   **reproduced, not fixed**.
3. **Uncleaned HTTP error body leaks into the call log.** Still reproduced on the refresh
   (`df729a9`): the synthetic HTTP error marker still entered the error field. The real issue
   is not the marker but that an uncleaned response body is logged at all; status:
   **reproduced, not fixed**.

The storage/spend defences are present, but findings 2 and 3 remain open, so PR #18 cannot be
certified as clean on this baseline. **Result: CHANGES REQUIRED.**

---

## PR #19 — `6808d7e` (role C: policy / contract alignment)

**Scope.** Must be reconciled with the D results above. Permissions, the runtime contract
and performance are asserted **only as observed** in a **local review**; there is **no
independent online evidence** for any of them.

**Conclusion (explicit).**

- PR #19 is a **local review** only: the C-side documents are reviewed locally and are
  internally consistent with the D findings that were actually reproduced.
- The permissions claims, the runtime-contract claims and any performance claims are
  **local-review only**. None is backed by independent online evidence, and none is
  reported here as met.
- Where PR #19's wording depends on D #18 being clean, it must be read together with the
  #18 findings (partial append, log error body — the mypy errors are now closed on `df729a9`)
  and not as a final pass.

**Conclusion:** PR #19's non-local claims remain pending until reconciled with D and backed
by independent evidence. **Result: CHANGES REQUIRED.**
