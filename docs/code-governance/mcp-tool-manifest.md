# MCP Tool Manifest (owner: roles C and E)

> Purpose: record the tools an AI agent may use on this repository, distinguishing
> **actual MCP servers/tools** from **application entry points** and **test commands**,
> and stating which role may approve each. This manifest **does not grant permissions**;
> `.opencode/permissions.jsonc` and `docs/architecture/permission-model.md` remain
> authoritative. Anything not listed here is denied.
>
> Status: **Phase 1 · D3 coding governance (transcript 60339160).**

---

## 1. Actual MCP servers / tools — none configured

**This repository currently configures no MCP server and registers no MCP tool.**

- There is no `opencode.json` / `opencode.jsonc`, and no MCP server registration.
- No MCP client dependency is declared in `requirements.txt` or `.opencode/package.json`.

This section is the complete, truthful inventory: it is empty by design. It will be
populated only when a real MCP server is added, which requires a plan and human approval
(see §6). The entries below are **not** MCP tools; they are documented separately so the
distinction is explicit.

---

## 2. Application entry points (NOT MCP tools)

These are functions the application calls internally. An agent does not invoke them as
MCP tools; it may read or write them under the normal path permissions.

| ID | Entry point | Purpose | Network | Owner |
|---|---|---|---|---|
| EP-001 | `src/call_llm.py::extract` | the only path that calls the model | gateway only | D |
| EP-002 | `src/policy_core.py::enforce_*` | deterministic guard functions (to be built by D) | none | D/E |

- EP-001 must append exactly one `logs/llm_calls.jsonl` line per call and is fail-closed
  (`runtime-policy-catalog.md RP-004`).
- EP-002 is the only place that decides an outcome from model output; it must never be
  bypassed (`AGENTS.md §3`).

---

## 3. Test commands (NOT MCP tools)

These are shell commands run by contributors and CI. They are not MCP tools.

| ID | Command | Purpose | Network | Owner |
|---|---|---|---|---|
| TC-001 | `pytest test/offline -q` | deterministic tests, no network | none | E |
| TC-002 | `pytest test/live -q` | tests that call the model | yes | E (approval) |

---

## 4. Role matrix

Roles: A (evidence/transcripts), B (requirements/AGENTS.md), C (security/governance),
D (development), E (tests/CI). Cells: **A** = allowed, **P** = allowed with human
approval, **D** = denied.

| Item | Kind | A | B | C | D | E |
|---|---|---|---|---|---|---|
| EP-001 `call_llm.extract` | entry point | A | A | A | A | A |
| EP-002 `policy_core.enforce_*` | entry point | A | A | A | A | A |
| TC-001 `pytest test/offline` | test cmd | A | A | A | A | A |
| TC-002 `pytest test/live` | test cmd | D | D | P | P | A |
| Any MCP server | MCP tool | D | D | D | D | D |

"No MCP server is configured" means every MCP row is presently moot; if one is added it
enters at **denied** until this manifest and the permission config are updated.

---

## 5. Guarantees and limits

- No arbitrary shell, no filesystem writes outside the repository, and no external
  network access except the configured model gateway.
- A tool that cannot satisfy the logging contract is not usable (fail-closed).
- A tool listed here is **not** thereby permitted; the permission config still decides.

---

## 6. Change protocol

Adding or removing an MCP server, application entry point, or test command requires:

1. A plan stating the tool, its network access, and the roles it serves.
2. Explicit human approval in the conversation.
3. An update to this manifest **and**, for anything an agent can invoke, to
   `.opencode/permissions.jsonc` under the `AGENTS.md §7` exception process.

This mirrors `docs/code-governance/structural-constraints.md §2.2` and §9.
