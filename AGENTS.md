# AGENTS.md — v0.2 (draft by role D · to be merged by B/C)

> This file is the **single entry point** for the AI coding agent.
> Everything not permitted here is forbidden. When two rules disagree, the stricter one
> wins, and you must ask a human before proceeding.

## 1. How you must work

1. **Plan first.** For every task, output a plan listing: files you will touch,
   functions you will add, and what you will NOT change. Then **wait for approval**.
2. **One task at a time.** Do not bundle unrelated changes.
3. **No new dependencies** unless the plan says so and a human approved it.
4. **No silent refactoring.** If you think existing code is wrong, ask first.
5. If a requirement is unclear, **stop and ask**. Do not guess.
6. **Report what you changed.** Every completed task ends with this block, verbatim:

   ```
   CHANGED FILES:
   - <path>  (<action: created | modified | deleted>)
   NOT CHANGED (confirm): <list of files you considered but did not touch>
   ```

   A task without this block is not finished.

## 2. Access rights by path

**Read** means you may open and reason about the file. **Write** means you may create,
modify or delete it.

| Path | Read | Write | Note |
|---|---|---|---|
| `src/**` | ✅ | ✅ | application code |
| `test/offline/**` | ✅ | ✅ | deterministic tests, no network |
| `test/live/**` | ✅ | ✅ | tests that call the model |
| `docs/architecture/**` | ✅ | ⚠️ | write only when the task explicitly asks for it |
| `docs/code-governance/**` | ✅ | ⚠️ | same |
| `docs/req/**` | ✅ | ❌ | requirements are owned by role B |
| `.opencode/**` | ✅ | ❌ | agent configuration is human-only |
| `.agent/**` | ✅ | ❌ | project covenant is human-only |
| `.github/workflows/**` | ✅ | ❌ | CI gates are owned by role E |
| `.env` | ❌ | ❌ | secrets — not readable, not writable |
| `logs/**` | ✅ | ❌ | produced at runtime by the application |
| `transcripts/**` | ✅ | ❌ | human-authored evidence |

If a task cannot be completed without writing to a ❌ path, **stop and ask**. Do not work
around it (see §7).

## 3. Non-negotiable rules

- **Never** put an API key, token or password in any file that is committed.
- **All model calls go through `src/call_llm.py`.** No other module may import `requests`
  or open a network connection to the model gateway. This is a module-level rule, not a
  function-level one: new entry points may be added to that module, but never outside it.
- **Never** bypass `src/policy_core.py`. Every model output must pass the deterministic
  checks before it can affect stored data.
- The deterministic checks are **not** the model's job. Do not ask the model to enforce a
  rule; write code for it.
- Every model call appends exactly one line to `logs/llm_calls.jsonl` with the fields
  `input`, `raw`, `parsed`, `error`. These four names must not be renamed.
- If the call cannot be logged, the result must not be used.

## 4. Style

- **Python 3.9+** (the project venv is 3.9; do not use 3.10-only syntax such as
  `match`, `X | Y` in runtime annotations, or `except*`).
- Type hints on public functions; the docstring names the invariant it serves
  (e.g. `"""INV-003: total spend must never exceed the budget."""`).
- One function = one responsibility. Functions longer than ~40 lines are a review flag,
  not a hard rule.
- Tests live in `test/offline/` and must not require network access.

## 5. Definition of done (for any task)

- [ ] Plan was approved before coding
- [ ] `pytest test/offline -q` passes
- [ ] New rule has at least one test that **fails without the guard**
- [ ] `CHANGED FILES` block is present and accurate
- [ ] No file outside the writable paths in §2 was modified
- [ ] No secret appears in any file you touched

## 6. What the human reviewer will check

1. Did the plan match what was implemented?
2. Does the `CHANGED FILES` list match `git status`?
3. Is any read-only path in §2 modified? (instant rejection)
4. Does the new test actually fail when the guard is removed?
5. Is any rule enforced by prompt text rather than by code? (instant rejection)

## 7. Exception process

If a task genuinely requires touching a forbidden path:

1. Stop. State which path and why, in one sentence.
2. Wait for explicit human approval in the conversation.
3. After approval, make the smallest possible change and mention it in
   `CHANGED FILES` with the marker `(approved exception)`.
4. The human records the exception in the pull request description.

You may never approve an exception for yourself, and you may never re-apply an exception
that was approved once without asking again.

## 8. Autonomy limits

- You may run: `pytest`, `python -m pip list`, `git status`, `git diff`.
- You may **not** run: `git push`, `git commit`, anything that deletes files, anything
  that installs a system package, anything that writes outside the repository.
- You may not send repository content to any external service other than the configured
  model gateway.
