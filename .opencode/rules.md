# OpenCode Rules — Binding for the OpenCode Agent (owner: role C)

> Scope: **OpenCode only.** This file states what the OpenCode coding agent must do on
> this repository. It is subordinate to `AGENTS.md`: where the two differ, the stricter
> rule wins, and this file never overrides `AGENTS.md`.
>
> Status: **Phase 1 · D3 coding governance (transcript 60339160).**

---

## 1. Precedence

1. `AGENTS.md` is the contract. This file restates how OpenCode must follow it.
2. Where this file and `AGENTS.md` differ, the **stricter** rule applies.
3. `.opencode/permissions.jsonc` is the machine-enforced permission form. If it and this
   file disagree, stop and ask a human; do not work around it.

---

## 2. How OpenCode must work

- **Plan first.** Output a plan (files touched, functions added, what will NOT change)
  and wait for approval before editing (`AGENTS.md §1`).
- **One task at a time.** Do not bundle unrelated changes.
- **Report changes.** End every completed task with the `CHANGED FILES` block, verbatim
  (`AGENTS.md §1.6`).

---

## 3. Permission enforcement

- Obey `.opencode/permissions.jsonc`: **default deny**, and `deny` always wins over
  `allow`. The rationale is in `docs/architecture/permission-model.md`.
- Never write `.env`, `logs/**`, `transcripts/**`, `.opencode/**`, `.agent/**`,
  `.github/**` or `docs/req/**`. Architecture and governance docs are `ask` — written
  only when a task explicitly asks.
- Never touch `main`: no `git commit`, `git push`, `git reset --hard`, `git clean`, or
  `rm`. These are human actions.
- If a task needs a denied path, stop and ask (`AGENTS.md §7`).

---

## 4. Module boundaries (non-negotiable)

- **All model calls go through `src/call_llm.py`.** Do not import `requests` anywhere else
  and do not open a network connection to the model gateway outside that module.
- **Never bypass `src/policy_core.py`.** Every model output must pass the deterministic
  checks before it can affect stored data.
- **The model proposes; code disposes.** Do not enforce a rule with prompt text; write
  deterministic code for it (`AGENTS.md §3`).

---

## 5. Logging and secrets

- Every model call appends **exactly one** line to `logs/llm_calls.jsonl` with the fields
  `input`, `raw`, `parsed`, `error`. Do not rename them.
- **Fail-closed:** if a call cannot be logged, its result must not be used
  (`docs/architecture/runtime-policy-catalog.md RP-004`).
- Never read or write `.env`. Never log, print or commit a key, token or password.

---

## 6. Style and definition of done

- Python 3.9-safe: no `match`, no `X | Y` runtime annotations, no `except*`.
- Type hints on public functions; tests live in `test/offline/` and use no network.
- A task is done only when the `AGENTS.md §5` checklist holds: plan approved,
  `pytest test/offline -q` run (and reported for what it actually did), every new guard
  has a test that fails without it, and `CHANGED FILES` matches `git status`.

---

## 7. OpenCode-specific prohibitions

- Do not create or edit `opencode.json*`, register an MCP server, or alter this
  repository's OpenCode configuration; that is human-only (`.opencode/**` is `deny`).
- Do not run arbitrary shell beyond the allowed read-only tooling; the `bash` block in
  `.opencode/permissions.jsonc` denies commit/push/destructive git and asks otherwise.
- Do not send repository content to any service other than the configured model gateway.

---

## 8. Related documents

| Document | Concern |
|---|---|
| `AGENTS.md` | the contract this file is subordinate to |
| `docs/architecture/permission-model.md` | permission boundaries and rationale |
| `docs/architecture/invariants.md` | `C-INV-###` business invariants |
| `docs/architecture/runtime-policy-catalog.md` | `RP-###` degradation policies |
| `docs/code-governance/mcp-tool-manifest.md` | tools, entry points, roles |
| `.opencode/permissions.jsonc` | machine form of the permission model |
