# 60339160 — QiangWanyun

> Annotated transcript of my work with the AI coding agent (OpenCode).
> Every entry records: what I instructed, what the agent produced, what I caught, and
> what I changed. This file is evidence of human authorship and supervision.
>
> Role: **C — security and governance.** Append a new entry after every working
> session; do not rewrite earlier entries.

---

## Session 1

**Date.** 2026-11-09 · Phase 1 C-Security: invariants, runtime policies, permission model

**Context.** Establish the deterministic safety boundary for the finance assistant and
the permission boundary for the coding agent. Specs only — D implements the guards, E
writes the tests (`docs/code-governance/structural-constraints.md §2.2`).

**My instruction to the agent.**

```
PLAN FIRST. Do not write code yet. Give me a plan with: files you will touch,
functions you will add, and what you will NOT change. Wait for my approval.
Task: three business invariants (positive amount, closed category whitelist,
cumulative budget), a runtime policy catalog, a permission model and a
default-deny permissions.jsonc. Specs only — do not modify src/ or test/.
```

**Agent output (excerpt).**

```
I will create docs/architecture/invariants.md, runtime-policy-catalog.md and
permission-model.md, plus .opencode/permissions.jsonc. I will also update the
transcript and ai-use-log. I will not touch src/, test/ or create policy_core.py.
```

**What I caught.** Two things.

1. **The first draft proposed to replace the budget invariant with a
   "logging-integrity" invariant.** The budget limit is a core requirement of the
   project; downgrading it loses the one rule a personal finance assistant exists to
   protect. I rejected the substitution. Logging integrity is a real requirement, but it
   protects the audit trail, not a spend outcome, so it belongs in the **runtime policy
   catalog** as `RP-004`, not in the invariant set.

2. **The first draft numbered the invariants `INV-001..003`, colliding with the existing
   reservation.** The other role's transcript (`60915652-LiuWanyang.md`) already reserved
   `INV-002` for the closed category list. Redefining a global id that another role owns
   is exactly the kind of silent collision the governance docs warn about. I required
   **role-scoped ids** (`C-INV-001/002/003`) and an explicit mapping table to the global
   ids, so that the merge in Phase 3 is a recorded translation, not a redefinition.

**My correction.**

```
Specs only. Keep the three business invariants: finite positive amount, closed
category whitelist, cumulative budget. Do not replace the budget invariant.
Document logging integrity as a runtime policy (RP-004) instead.
Do not duplicate INV-002 — use C-INV-### and state the numbering decision in
invariants.md with a mapping table to the global ids.
```

**Result.**

- `docs/architecture/invariants.md` — three guard-spec blocks (`C-INV-001..003`) in the
  §2.2 handoff format, with an explicit numbering decision and the `C-INV → INV` map.
- `docs/architecture/runtime-policy-catalog.md` — RP-001..006, including logging
  integrity as `RP-004` (fail-closed), and a precedence order.
- `docs/architecture/permission-model.md` — permission boundaries by path, the
  default-deny design, and the exception path.
- `.opencode/permissions.jsonc` — default deny (`"*": "deny"`) plus an explicit
  whitelist; `.env`, `main` mutations and destructive git are hard-denied.
- Validation (this session): the JSONC parses after stripping comments; `git status`
  shows only the intended files. `pytest test/offline -q` reported **no tests ran** (the suite is
  empty), not "green" — it is not treated as evidence of correctness.
- No key appears in any file. No `src/` or `test/` file was modified.

**Open handoffs.** D implements `enforce_<subject>` for each `C-INV` plus a negative test;
E verifies each test fails when its guard is removed; the config's ⚠️ paths (`ask`) need
the §7 approval flow the first time they are used.

**Reflection.** Both catches were the same instinct: do not let a convenient shortcut
redefine a settled property. The budget is not negotiable, and a global id belongs to
whoever reserved it first.

---

## Session 2

**Date.** 2026-11-09 · Final validation of the C-Security artefacts

**Context.** Re-validate the session-1 artefacts using PyYAML in the project virtual
environment (`.venv`). No new design work; verification only.

**My instruction to the agent.**

```
Run the final validation with ./.venv/bin/python. Validate ai-use-log.yaml with
PyYAML, inspect the transcript and the log, validate permissions.jsonc against the
OpenCode format if a validator exists (otherwise report the limitation), run
git diff --check, git status, and pytest test/offline -q, and confirm .venv/ is
not part of the intended changes. Make only minimal corrections.
```

**Agent output (excerpt).**

```
PyYAML check: YAML OK. Found that the session-1 transcript claimed ai-use-log.yaml
"parses" and that pytest was "green", which overstated what session 1 verified.
Proposed a minimal correction and to add a session number.
```

**What I caught.** The agent's own summary of session 2 initially described the JSONC
check as "validated against the OpenCode permission format". No project-specific OpenCode
validator exists in this repository, so only generic JSONC parsing was performed. I
required the agent to state that limitation explicitly rather than imply a stronger check.

**My correction.**

```
Do not imply the OpenCode permission format was validated by a real validator.
Say plainly that only generic JSONC parsing is possible here. Keep the session-1
corrections minimal: state what actually passed and what was blocked.

I also required the agent to add explicit read permissions for `.opencode/**`,
`.agent/**`, `.github/workflows/**`, and `transcripts/**` so that
`permissions.jsonc` matches `permission-model.md`. The corresponding edit
permissions remain denied.
```

**Result.**

- `docs/ai-use-log.yaml` parses under `./.venv/bin/python` (`YAML OK`).
- `.opencode/permissions.jsonc` parses after stripping `//` comments — **generic JSONC
  only**; no OpenCode-specific validator is available in this repo, so schema-level
  conformance is **not** verified. Its read whitelist now matches the documented
  boundaries for `.opencode/**`, `.agent/**`, `.github/workflows/**`, and `transcripts/**`.
- `git diff --check` clean; `git status` shows only the intended files.
- `pytest test/offline -q` still reports **no tests ran** (empty suite); this is reported,
  not claimed as passing.
- `.venv/` is listed in `.gitignore` and is not part of the intended changes.
- Session-1 transcript text corrected: the overstated YAML/"green" claims now state what
  actually happened.

**Open handoffs.** Unchanged from session 1. A real OpenCode permission-schema
validation remains to be done by E if one is introduced.

**Reflection.** A validation step is only evidence of what it actually exercised. Generic
JSON parsing is not schema validation, and "no tests ran" is not "tests passed"; both
must be written as what they are.
