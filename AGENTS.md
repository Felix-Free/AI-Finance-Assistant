# AGENTS.md — v1.0 (owned by role B · security sections by role C)

> This file is the **single entry point** for the AI coding agent.
> Everything not permitted here is forbidden. When two rules disagree, the **stricter** one
> wins, and you must ask a human before proceeding.
>
> Ownership: role **B** owns this document (requirements & architecture). The security and
> permission mechanics are owned by role **C** and are **referenced, not redefined**, here.
> The layered governance is:
>
> | File | Scope | Owner |
> |---|---|---|
> | `AGENTS.md` (this file) | the unified contract: overall behaviour, project context, approval workflow | B (C for the security sections) |
> | `.opencode/rules.md` + `.opencode/permissions.jsonc` | OpenCode-specific rules and machine-enforced permissions | C |
> | `.agent/rules.md` | tool-agnostic covenant for any agent | C |
> | `docs/architecture/invariants.md` | business invariants INV-001/002/003 | C |
> | `docs/architecture/runtime-policy-catalog.md` | RP-001..RP-006 degradation policies | C |
> | `docs/architecture/permission-model.md` | path permission boundaries and rationale | C |
> | `docs/code-governance/structural-constraints.md` | code/test/naming conventions | C (D drafted v0.1) |
> | `Prompt.md` | the per-task static prompt | B |
>
> History: v0.2 was drafted by role D and merged under B/C review. This v1.0 is the B-owned
> consolidation; **all rules from v0.2 are preserved**, and the sections below marked
> "reference" point to C's documents for the authoritative detail.

---

## 0. Project context

- **Project:** AI Finance Assistant — turn one natural-language sentence describing a purchase
  into one validated, structured spending record.
- **Core architecture (one line):** model parses → deterministic `policy_core` validates →
  accept / reject / review. The model proposes; code disposes. See `architecture-blueprint.md`.
- **Document index (read the relevant ones before a task):**
  - Requirements: `docs/req/requirements.yaml` (schema: `docs/req/req-schema.json`).
  - Architecture: `architecture-blueprint.md`.
  - Business invariants: `docs/architecture/invariants.md` (`INV-001/002/003`).
  - Runtime policies: `docs/architecture/runtime-policy-catalog.md` (`RP-001..006`).
  - Permission model: `docs/architecture/permission-model.md`.
  - Code conventions: `docs/code-governance/structural-constraints.md`.
  - Agent rules: `.opencode/rules.md`, `.agent/rules.md`.
- **Current code reality (main, after PR #9):** `src/call_llm.py`, `src/policy_core.py` and
  `src/pipeline.py` are all merged on `main`, with `test/offline/test_policy_core_smoke.py`
  and `test/offline/test_pipeline_seam.py`. CI is **not** set up yet (`.github/workflows/`
  holds only `.gitkeep`). Do not describe unimplemented persistence, a budget store, or CI as
  present in the code.

---

## 1. Tool and model policy

1. **AI Coding client:** OpenCode. Do not switch to another client.
2. **Model:** the project specifies **deepseek-v4-flash**. The deployed model id in this repo is
   `CS5351/DeepSeek-V4-Flash` (see `.env.example`, `src/call_llm.py::MODEL`).
   **Known difference:** the requirement says "deepseek-v4-flash"; the configured id is
   `CS5351/DeepSeek-V4-Flash`. Report this difference; do **not** change the model or the
   connection configuration on your own — that is a human decision.
3. **Never change the model** or the gateway/base URL without explicit human approval.
4. **Never place an API key, token or password** in source code, in a commit, in a log, or in
   terminal output. See §7.

---

## 2. How you must work (approval workflow)

For every task, follow these steps **in order**. You may not modify project code without
explicit human approval after Step 3.

1. **Understand the task.** Restate what is being asked; identify ambiguities. If unclear,
   stop and ask — do not guess.
2. **Read relevant requirements.** Open `requirements.yaml`, the architecture blueprint, C's
   invariants/policies, and the code and tests the task touches.
3. **Generate an implementation plan.** State: files to touch, functions to add, and what you
   will NOT change. (See `Prompt.md` for the plan template.)
4. **Wait for human approval.** The AI's own plan is not approval. No approval → no edits.
5. **Execute approved changes.** One task at a time; do not bundle unrelated changes; do not
   expand scope; do not silently refactor (§5).
6. **Run verification.** Run the relevant tests (§6). Do not claim success you did not observe.
7. **Report results.** End with the reporting block (§7).

**Every completed task ends with this block, verbatim:**

```
CHANGED FILES:
- <path>  (<action: created | modified | deleted>)
NOT CHANGED (confirm): <list of files you considered but did not touch>
```

A task without this block is not finished.

---

## 3. File ownership and permission

**Role ownership (who is responsible) is NOT the same as AI write permission.** The role table
says who owns a file; the actual AI read/write capability is governed by
`docs/architecture/permission-model.md §2` and `.opencode/permissions.jsonc`, only within the
scope a human has approved for the current task.

| Path | Role owner | AI read | AI write (per permission model) |
|---|---|---|---|
| `src/**` | D | ✅ | ✅ (within approved task) |
| `test/offline/**` | E | ✅ | ✅ (within approved task) |
| `test/live/**` | E | ✅ | ✅ (within approved task) |
| `docs/architecture/**` | B / C | ✅ | ⚠️ only when the task explicitly asks |
| `docs/code-governance/**` | C / E | ✅ | ⚠️ only when the task explicitly asks |
| `docs/req/**` | B | ✅ | ❌ (owned by B; AI does not write) |
| `AGENTS.md` | B / C | ✅ | requires explicit human approval per task |
| `Prompt.md` | B | ✅ | requires explicit human approval per task |
| `.opencode/**` | C | ✅ | ❌ (human-only) |
| `.agent/**` | C | ✅ | ❌ (human-only) |
| `.github/workflows/**` | E | ✅ | ❌ (owned by E; human-only) |
| `.env` | — | ❌ | ❌ (secrets) |
| `agent.env` (if present) | — | ❌ | ❌ (secrets) |
| `logs/**` | runtime | ✅ | ❌ (produced by the application at runtime) |
| `transcripts/**` | A | ✅ | ❌ (human-authored evidence) |

- The **authoritative** permission table and the machine form are `permission-model.md §2` and
  `permissions.jsonc`. If this table and those disagree, **the stricter rule wins**, and you
  must stop and ask a human. Do not "work around" a denial (§ exception below).
- **Never relax or delete a security restriction just to finish a task.**

**Exception process.** If a task genuinely needs a ❌ path: stop, state the path and reason in
one sentence, wait for explicit human approval, then make the smallest change and mark it
`(approved exception)` in `CHANGED FILES`.

---

## 4. Non-negotiable safety rules (reference C — do not redefine)

These are owned by role C; the authoritative details are in the referenced files. The rules
summarised here must never be weakened.

- **Secrets** are never committed, logged, or placed in any committed file (`§7`; `SEC-001`).
- **All model calls go through `src/call_llm.py`.** No other module imports `requests` or opens
  a network connection to the model gateway. (`AGENTS` §4, `structural-constraints.md §2`, `SEC-002`.)
- **`src/policy_core.py` is never bypassed.** Every model output passes deterministic checks
  before it can affect stored data. (`SEC-003`, `runtime-policy-catalog.md`.)
- **The model proposes; code disposes.** Never enforce a business rule with prompt text; write
  deterministic code for it. (`invariants.md`, `RP-003/005/006`.)
- **Rules are enforced in code, not in prompt text.**
- **Every model call is logged** — exactly one line to `logs/llm_calls.jsonl` with fields
  `input` / `raw` / `parsed` / `error` — and is **fail-closed** if logging fails.
  (`RP-004`, `SEC-005`.)

Business invariants (authoritative in `docs/architecture/invariants.md`):
`INV-001` finite positive amount (≤ 2 decimals), `INV-002` category in the code-defined
closed whitelist, `INV-003` cumulative spend ≤ budget (equality allowed). Do not restate,
weaken, or invent invariant thresholds here — change them only via C.

---

## 5. Coding rules

- **No silent refactoring.** If you think existing code is wrong, ask first.
- **No new dependencies** unless the plan says so and a human approved it; then add it to
  `requirements.txt`.
- **No changing public interfaces** (function names, signatures, return types) without approval.
- **Never bypass deterministic validation** (`src/policy_core.py`).
- **Never replace a business safety rule with AI judgment.**
- **Do not modify unauthorised directories** (see §3 and the permission model).
- **Do not delete or weaken a failing test to make the suite pass.** A failing test is a signal,
  not an obstacle.
- **No `git commit`, `git push`, destructive git, or file deletion** — those are human actions.

---

## 6. Testing rules

- After a change, **run the relevant tests** (offline tests need no network:
  `pytest test/offline -q`).
- Cover **both positive and negative** cases — do not test only the happy path.
- **Verify the safety rules**: each new guard must have at least one test that **fails when the
  guard is removed**.
- **Do not falsely report test success.** Report exactly what ran and what it produced.
- If the environment cannot run the tests, **say why** and do not imply they passed.
- The exhaustive boundary suite (`test/offline/test_invariants.py`) is role **E**'s deliverable;
  do not duplicate or pre-empt it without approval.

---

## 7. Reporting and security

**Every task report must state:** changed files; reason for the change; the relevant
requirement ID(s) (`FR-###`, `INV-###`, `NFR-###`); the test command(s) run; the test
results (truthfully); remaining risks; and anything not yet done.

**Security and secrets:**
- Never upload an API key to GitHub, and never place one in any committed file.
- `.env` is protected; **`agent.env` (if present) is protected** by the same rule. Both are
  unreadable and unwritable by the agent.
- Never print a full key/token in terminal output or logs — mask it.
- Never commit or log real personal financial data.
- Do not read or modify any file explicitly marked off-limits (§3).

---

## 8. Autonomy limits

- You may run: `pytest`, `python -m pip list`, `git status`, `git diff`.
- You may **not** run: `git push`, `git commit`, `git reset --hard`, `git clean`, `rm -rf`,
  anything that installs a system package, or anything that writes outside the repository.
- You may not send repository content to any external service other than the configured model
  gateway.

---

## 9. Style and definition of done

- **Python: minimum 3.9** (no `match`, no `X | Y` runtime annotations, no `except*`, no
  parenthesised context managers). Code must stay 3.9-compatible even though the local venv is
  newer. Versions observed so far: venv `SoftEngineering` = 3.14.4, system `py_compile` = 3.9.7
  (`structural-constraints.md §7`). CI (when built by E) must pin `python-version` explicitly;
  that value is the one the code is verified against (`requirements.yaml` PD-006, owner E/D).
- Type hints on public functions; the docstring names the invariant it serves.
- A task is **done** only when: the plan was approved before coding; the relevant tests were run
  and reported truthfully; every new guard has a failing-without-it test; the `CHANGED FILES`
  block matches `git status`; no file outside the writable paths in §3 was modified; and no
  secret appears in any touched file.

---

## 10. What the human reviewer will check

1. Did the plan match what was implemented?
2. Does the `CHANGED FILES` list match `git status`?
3. Is any read-only path in §3 modified? (instant rejection)
4. Does the new test actually fail when the guard is removed?
5. Is any rule enforced by prompt text rather than by code? (instant rejection)
