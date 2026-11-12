# Permission Model (owner: role C)

> Purpose: the authoritative statement of what the AI coding agent may read and write,
> how the permission config (`.opencode/permissions.jsonc`) encodes it, and where the
> boundaries between roles sit. This document and the config must never disagree; if they
> do, the config is wrong and must be corrected.
>
> Status: **Phase 1 · C-Security (transcript 60339160)**; amended in **Phase 2 · C1** for
> measurement permissions (§3.1).

---

## 1. Principles

1. **Default deny.** Anything not explicitly whitelisted is denied.
2. **Deny overrides allow.** A `deny` on a path or command wins over any `allow`,
   regardless of order or specificity. There is no "last match wins".
3. **Secrets are never readable by the agent.** `.env` is denied for read *and* write,
   even if a broader pattern would otherwise match it.
4. **The agent never touches `main`.** No `git push`, `git commit`, destructive git, or
   file deletion. Commits and merges are human actions.
5. **Read-only for other roles' artefacts.** Requirements, transcripts and CI gates are
   human/other-role owned; the agent may read them but not write them.

---

## 2. Permission boundaries by path

| Path | Read | Write (agent) | Owner | Note |
|---|---|---|---|---|
| `src/**` | ✅ | ✅ | D | application code |
| `test/offline/**` | ✅ | ✅ | E | deterministic, no network |
| `test/live/**` | ✅ | ✅ | E | calls the model |
| `docs/architecture/**` | ✅ | ⚠️ | B/C | only when the task explicitly asks |
| `docs/code-governance/**` | ✅ | ⚠️ | C/E | only when the task explicitly asks |
| `docs/req/**` | ✅ | ❌ | B | requirements owned by B |
| `.opencode/**` | ✅ | ❌ | C | agent config is human-only |
| `.agent/**` | ✅ | ❌ | C | project covenant is human-only |
| `.github/workflows/**` | ✅ | ❌ | E | CI gates owned by E |
| `.env` | ❌ | ❌ | — | secrets |
| `logs/**` | ✅ | ❌ | runtime | produced by the application |
| `transcripts/**` | ✅ | ❌ | A | human-authored evidence |
| `data/**` | ✅ | ✅ | C (Phase 2) | measurement inputs; see §3.1 |
| `scripts/**` | ✅ | ✅ | C (Phase 2) | measurement scripts; see §3.1 |
| `docs/measurements/**` | ✅ | ✅ | C (Phase 2) | measurement reports; see §3.1 |
| `main` branch | — | ❌ | — | protected; never push/commit |

⚠️ = allowed only when the current task explicitly asks (see `AGENTS.md §2`).

---

## 3. How the config encodes this

`.opencode/permissions.jsonc` is the machine-readable form of §2. It uses the
**default-deny + explicit-whitelist** design:

- A top-level `"*": "deny"` sets the default for every action.
- Only the entries listed under `read`, `edit` and `bash` change the default.
- `deny` entries are hard stops and cannot be overridden by a broader `allow`.
- Comments (`//`) document each block; the file is JSONC, not strict JSON.

The mapping from §2 to the config is direct: every ✅ write becomes an `allow`, every ❌
becomes a `deny`, and every ⚠️ becomes `ask` (human confirmation per use).

### 3.1 Phase 2 · C1 measurement expansion

Phase 2 measurement work needs the agent to read and write measurement material. C1 adds
exactly three path trees and three command patterns to the config:

| Scope | Kind | Permission |
|---|---|---|
| `data/**` | path | read `allow`, edit `allow` |
| `scripts/**` | path | read `allow`, edit `allow` |
| `docs/measurements/**` | path | read `allow`, edit `allow` |
| `pytest*` | bash | `allow` |
| `python -m py_compile*` | bash | `allow` |
| `python scripts/*` | bash | `allow` |

These permissions exist **only for Phase 2 measurement work**: measurement inputs live in
`data/`, the scripts that consume them live in `scripts/`, and the resulting reports live
in `docs/measurements/`.

Constraints that this expansion does not relax:

- **Runtime-generated files under `data/` must not be committed.** The edit `allow` lets
  the agent write measurement scratch/output there; committing those files is a human
  decision and they are expected to be excluded from version control. The agent may not
  create or commit runtime data.
- The **default-deny** rule (`"*": "deny"`) is unchanged.
- **Deny overrides allow** is unchanged; no earlier `deny` is weakened by the new
  `allow` entries.
- **`.env` protection** (denied for read and write) is unchanged.
- **Protected paths** (`docs/req/**`, `.opencode/**`, `.agent/**`, `.github/**`,
  `transcripts/**`, `logs/**`, `main`) are unchanged.
- Every other `deny`/`ask` rule and default in the config is unchanged.

`.opencode/permissions.jsonc` remains the **machine-readable configuration**; this section
documents the same change so the document and the config stay in agreement.

---

## 4. Exception path

If a task genuinely needs to write a ❌ path, the agent stops, states the path and the
reason, and waits for explicit human approval in the conversation (`AGENTS.md §7`). After
approval the smallest change is made and listed in `CHANGED FILES` with the marker
`(approved exception)`. The agent may never approve its own exception, and may never
re-apply a once-approved exception without asking again.

---

## 5. Relationship to the other documents

| Document | Concern |
|---|---|
| `invariants.md` | business rules that must never be violated |
| `runtime-policy-catalog.md` | how the app degrades when something goes wrong |
| `permission-model.md` (this file) | what the *agent* may do to the repository |
| `.opencode/permissions.jsonc` | machine form of this file |
| `AGENTS.md §2` | the same boundaries stated for the agent at runtime |

The permission model governs the **agent**, not the end user of the finance assistant.
Runtime data safety is the job of the invariants and policies above.
