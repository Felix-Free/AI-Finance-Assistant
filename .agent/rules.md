# Agent Rules — Portable Covenant for Any AI Coding Agent (owner: role C)

> Scope: **tool-agnostic.** This file applies to every AI coding agent used on this
> repository, regardless of vendor or product. It is the portable summary of the project
> covenant and deliberately **references** `AGENTS.md` rather than copying it.
>
> Status: **Phase 1 · D3 coding governance (transcript 60339160).**

---

## 1. Authority and precedence

1. **`AGENTS.md` is the contract.** This file does not replace it; read `AGENTS.md` first.
2. Where this file and `AGENTS.md` differ, the **stricter** rule wins.
3. `docs/architecture/` is the design authority for behaviour; `AGENTS.md` is the
   authority for how an agent must work.

---

## 2. Non-negotiables (see AGENTS.md §3)

Read these in `AGENTS.md §3`; they are not re-specified here to avoid divergence:

- **Secrets** are never committed, logged, or placed in any committed file.
- **All model calls** go through `src/call_llm.py`; no other module imports `requests`
  for model calls.
- **`src/policy_core.py`** is never bypassed; model output passes deterministic checks
  before it can affect stored data.
- **Rules are enforced in code, not in prompt text.**
- **Every model call is logged** (one line, fields `input` / `raw` / `parsed` / `error`)
  and is **fail-closed** if logging fails.

---

## 3. Boundaries

- The permission boundaries are defined by `docs/architecture/permission-model.md §2` and
  enforced by `.opencode/permissions.jsonc` for OpenCode. Any agent must honour the same
  boundaries even if its own tool has no permission file.
- **Default deny:** a path or action not explicitly allowed is denied.
- **`.env` is unreadable and unwritable.** `main` is protected. `logs/**` and
  `transcripts/**` are read-only; `docs/req/**` is owned by another role.

---

## 4. Human in the loop

Follow `AGENTS.md` for the working protocol: plan first and wait for approval (§1), one
task at a time, end with the `CHANGED FILES` block (§1.6), and use the exception process
for any denied path (§7).

---

## 5. Prohibited actions

- No `git commit`, `git push`, pull request creation, `git reset --hard`, `git clean`, or
  file deletion unless a human explicitly asks.
- No writing outside the repository.
- No sending repository content to any external service other than the configured model
  gateway.

---

## 6. Related documents

| Document | Concern |
|---|---|
| `AGENTS.md` | the contract every agent must follow |
| `docs/architecture/permission-model.md` | path boundaries and rationale |
| `docs/architecture/invariants.md` | `C-INV-###` business invariants |
| `docs/architecture/runtime-policy-catalog.md` | `RP-###` degradation policies |
| `docs/code-governance/mcp-tool-manifest.md` | tools, entry points, roles, approval |
| `.opencode/rules.md` | the OpenCode-specific form of these rules |
