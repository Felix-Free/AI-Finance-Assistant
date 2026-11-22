# 60339160 — QiangWanyun

> Record of my C-side security, governance and evaluation work with AI coding agents.
> Session entries document the requirements, decisions and evidence relevant to that work.
>
> Role: **C — security and governance.**

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

---

## Session 3

**Date.** 2026-11-09 · D3 coding-governance files: OpenCode rules, agent covenant, MCP tool manifest

**Context.** This session covers three governance files:
`.opencode/rules.md`, `.agent/rules.md` and `docs/code-governance/mcp-tool-manifest.md`
(D3 · owner C, reserved in `structural-constraints.md`).

**My instruction to the agent.**

```
Plan first, then create only .opencode/rules.md, .agent/rules.md and
docs/code-governance/mcp-tool-manifest.md. Keep rules.md OpenCode-specific,
.agent/rules.md tool-agnostic (reference AGENTS.md, do not copy it), and the
manifest focused on tools/entry points/roles/approval. Do not treat
call_llm.extract, enforce_*, or pytest as MCP tools. State that no MCP server is
configured. Do not touch permissions.jsonc or existing C-Security files.
```

**Agent output (excerpt).**

```
I will create the three files with citations to AGENTS.md, permission-model.md,
invariants.md and runtime-policy-catalog.md. I will keep the broad docs/** and
test/** read rules of permissions.jsonc as intentional, not errors.
```

**What I caught.** My plan corrections were carried through, and one agent slip needed
fixing: the first version of the manifest's change-protocol section ended with a malformed
duplicate clause. I also held the agent to three design points from the revised plan:
(1) the manifest must list **no MCP server** because none exists, and must separate
application entry points (`call_llm.extract`, `policy_core.enforce_*`) and test commands
(`pytest`) from MCP tools; (2) `.opencode/permissions.jsonc` must **not** be edited — the
broad `docs/**` / `test/**` read rules are intentional and equivalent in effect to the
granular paths in `permission-model.md`, so the relationship is documented, not "fixed";
(3) `rules.md` stays OpenCode-specific while `.agent/rules.md` stays tool-agnostic.

**My correction.**

```
Do not invent an MCP server. Say plainly that none is configured. Keep the
manifest's three categories separate: MCP tools, application entry points, test
commands. Do not edit permissions.jsonc — document the broad-vs-granular
equivalence instead of demanding string equality. Clean up the malformed
change-protocol paragraph.
```

**Result (files created this session).**

- `.opencode/rules.md` — OpenCode-specific binding; precedence `AGENTS.md` first, then
  permission enforcement, module boundaries, logging, style, OpenCode-specific
  prohibitions, and a related-documents table.
- `.agent/rules.md` — tool-agnostic covenant; references `AGENTS.md §3` instead of
  copying it, defers boundaries to `permission-model.md §2`, lists prohibited actions.
- `docs/code-governance/mcp-tool-manifest.md` — states **no MCP server is configured**,
  then lists application entry points (EP-001/EP-002) and test commands (TC-001/TC-002)
  separately, with a role matrix and a change protocol.
- `.opencode/permissions.jsonc` was **not** modified. No `src/` or `test/` file changed.

**Validation (what actually ran).** YAML log validation, `git diff --check` and
`git status` are recorded below in the same session; `pytest test/offline -q` reported
**no tests ran** (empty suite), reported as such, not as passing. No OpenCode or MCP
schema validator exists in this repository.

**Open handoffs.** E may add CI verification of these governance files; adding any real
MCP server requires plan + approval and must update both the manifest and
`permissions.jsonc` together.

**Reflection.** The value of the manifest is the honest empty section: recording that
there is no MCP server prevents a later reader from assuming one exists, and keeps
"app entry point", "test command" and "MCP tool" from being conflated.

---

## Session 4

**Date.** 2026-11-09 · required C document edits for policy-review evidence

**My instruction to the agent.**

```
Apply the first three required edits: move invariant rejection evidence to
logs/review.jsonl with the specified review flags, add the rejection-evidence
note at the start of §2, and update only RP-003/RP-005/RP-006 evidence paths.
Do not change RP-001/RP-002/RP-004.
```

**Result.** The two C documents contain only the requested evidence-path changes. The
three invariant Evidence lines now use `logs/review.jsonl`; the review flags are
`false`, `true`, and `true` respectively; and the §2 note records the two-log decision.
RP-001, RP-002 and RP-004 remain unchanged.

**My correction.**

```
Before committing, I checked that the diff contains only the requested three edits and
that the unrelated .DS_Store file is excluded.
```

---

## Session 5

**Date.** 2026-11-12 · Phase 2: measurement permission configuration

**Context.** Phase 2 introduces measurement work (inputs under `data/`, scripts under
`scripts/`, results under `docs/measurements/`). This session only covers permission changes: widen the
agent's whitelist just enough to read and edit those three paths and to run the
measurement commands, without opening anything else. Storage, `call_id`, token accounting
and NFR-006 belong to D/E and are deliberately out of scope.

**My instruction to the agent.**

```
Complete only the permission change. In .opencode/permissions.jsonc add data/**, scripts/** and
docs/measurements/** to read and to edit as allow, and add the bash allow
patterns pytest*, python -m py_compile* and python scripts/*. Preserve every
existing deny/ask rule, comment and default; broaden nothing else. Then append a
new Phase 2 C session to the transcript and the ai-use-log. Do not touch src/,
test/, docs/architecture/ or docs/code-governance/. Do not generate runtime data.
```

**Agent output (excerpt).**

```
The measurement permission change is complete. The measurement paths were added to the read and edit allowlists,
the three measurement commands were added to the bash allowlist, and the
transcript and ai-use-log were updated. No source, test or runtime data files
were changed.
```

**What I caught.** The permission expansion had to remain limited to the three
measurement path trees and the three requested command patterns. Storage, `call_id`,
token accounting and NFR-006 were deliberately left for D/E.

**My correction.**

```
Keep this change limited to the requested permission entries and evidence records.
```

**Result.**

- `.opencode/permissions.jsonc` — added `data/**`, `scripts/**` and
  `docs/measurements/**` to `read` and to `edit` as `allow`; added `pytest*`,
  `python -m py_compile*` and `python scripts/*` to `bash` as `allow`. All other rules
  (`"*": "deny"`, `"*": "ask"`, `.env`, `git push`/`git commit`, `rm -rf`, the
  architecture/governance `ask` rules and the expandable denominators) are unchanged.
- `transcripts/60339160-QiangWanyun.md` — this entry.
- `docs/ai-use-log.yaml` — matching session 5 entry.

No `src/` or `test/` file changed. No file was written under `data/`.

Validation included generic JSONC parsing, YAML parsing under
`./.venv/bin/python`, and a clean `git diff --check`.

**Open handoffs.** The measurement scripts themselves, the `data/` inputs and the
`docs/measurements/` reports are subsequent Phase 2 steps. The `python scripts/*`
allow is deliberately scoped to the repo's own scripts directory.

**Reflection.** A permission change is the one edit where "it works" is not the goal:
every added line is a new capability for the agent, so the session records both what was
granted and what was explicitly left denied.

---

## Session 6

**Date.** 2026-11-12 · Phase 2 follow-up: synchronize permission model

**Context.** In permission commit `88aab30`, `.opencode/permissions.jsonc` was widened
but `docs/architecture/permission-model.md` still described only the Phase 1 boundaries,
so document and config disagreed. This session synchronizes them without changing the
permission entries themselves.

**Why the permission model was synchronized.** `permission-model.md` is the authoritative
statement and `.opencode/permissions.jsonc` is its machine-readable form; the file's own
preamble says they must never disagree. Adding §3.1 and three rows to the §2 table records
the measurement expansion (data, scripts, measurements as read+edit `allow`; pytest, py_compile and
`python scripts/*` as bash `allow`), states that runtime files under `data/` must not be
committed, and restates that default-deny, deny-overrides-allow, `.env` protection and the
protected paths are unchanged.

**Files changed in this follow-up.**

- `docs/architecture/permission-model.md` — §2 rows and new §3.1 for the measurement expansion.
- `transcripts/60339160-QiangWanyun.md` — this entry.
- `docs/ai-use-log.yaml` — matching Session 6 entry.

`.opencode/permissions.jsonc` was not modified; its measurement entries are preserved.

**My correction.**

```
Synchronize the doc to the config instead of leaving them inconsistent. Do not amend
88aab30; make a follow-up commit.
```

CHANGED FILES:
- docs/architecture/permission-model.md  (modified, approved exception)
- transcripts/60339160-QiangWanyun.md  (modified, approved exception)
- docs/ai-use-log.yaml  (modified, approved exception)


NOT CHANGED (confirm): src/**, test/**, .opencode/permissions.jsonc,
docs/architecture/invariants.md, docs/architecture/runtime-policy-catalog.md,
docs/code-governance/**, logs/**, .env, .DS_Store, docs/.DS_Store

---

## Session 7

**Date.** 2026-11-12 · Phase 2: policy contracts and evaluation logbook

**Scope.** Record the C-side `call_id`, model-call logging, storage-failure and evidence
contracts without changing Phase 1 policy IDs or D/E source and tests.

**Contract.** `call_llm` generates a 32-character `uuid4().hex` `call_id` for each
`extract` attempt and returns it through `__call_id__`; the private key is removed
before deterministic policy validation. The call log retains `input`, `raw`, `parsed`
and `error` and includes the Phase 2 metadata. Missing recorded usage is represented
by `tokens: null`, never an invented count. `StorageError` is independent of
`policy:*`; the no-partial-state boundary remains to be verified.

**Evidence.** Main defines NFR-001 as model API response time, NFR-002 as token
consumption and NFR-006 as log traceability. Their observed measurements remain
pending. Phase 2 adds a `call_id` join between `llm_calls` and storage for an accepted
decision, or between `llm_calls` and review for a rejected decision. A rejected record
is not persisted. The rejection writer is `_append_rejection`, which retains the
original `PolicyError.code`.

**Result.** The runtime policy catalog records the contracts; the evaluation logbook
records the metrics, evidence procedures and pending results. The MCP manifest
separates application and measurement entry points from MCP tools.

---

## Session 8

**Date.** 2026-11-12 · Phase 2: NFR-006 evidence shape

**Requirement.** NFR-006 measures log-line coverage for model calls and policy
rejections. Main gives it no numeric coverage threshold. The Phase 2 `call_id` join is
an additional structural traceability check: an accepted decision has `llm_calls` +
storage evidence; a rejected decision has `llm_calls` + review evidence and no normal
storage record. Each applicable pair carries the same `call_id`. No decision needs all
three locations.

**Evidence status.** The logbook keeps the observed result pending until a measurement
is run. The evidence-join tests in `test/offline/test_evidence_join.py` are skipped, so
they do not establish a verified result.

---

## Session 9

**Date.** 2026-11-12 · Phase 2 C: document the four approved logging metadata fields

**Context.** Phase 2 logging needs more than `call_id` and `tokens` to answer the questions
role B asks about the system: how one process run behaved, how one user request fanned out
into several API calls, whether an HTTP attempt was made, and where the token numbers
came from. Four additional fields were approved — `session_id`, `request_id`,
`usage_source` and `request_made`. This session is documentation-only: it extends the logging
contract and the NFR-002 evidence in the logbook. No source, test, log, permission or MCP
file is touched.

**My instruction to the agent.**

```
The user approved four more llm_calls fields: session_id, request_id, usage_source
(enum: gateway, partial, missing), request_made (boolean; true when HTTP was attempted).
Extend the logging section with their exact meaning and keep every existing
logging requirement intact. Do not define request_made from error text. A pre-HTTP
failure writes a call-log line with request_made=false and tokens=null. Update NFR-002 to
cover per-session and per-request aggregation, request_made counts, usage-source counts,
missing-usage counts and usage_source/tokens consistency. Do not invent thresholds.
Treat call-id joins as an additional NFR-006 traceability check.
```

**Agent output (excerpt).**

```
I will add a metadata subsection to the logging contract defining session_id, request_id,
usage_source (gateway/partial/missing) and request_made (HTTP-attempt true), preserving
input/raw/parsed/error, call_id uniqueness, gateway-only tokens, no fabricated or zero
token counts, policy:* reservation and one-line-per-extract-attempt. A pre-HTTP local
failure has request_made=false and tokens=null. I will extend NFR-002's procedure with
the aggregation and consistency checks.
```

**What I caught.** Three things.

1. **The four fields answer different questions and must not collapse into one.** `call_id`
   identifies one `extract` attempt; `request_id` groups the calls one user request triggers
   (one request may make several); `session_id` groups calls in a process run. I required the
   contract to say plainly that neither new id replaces `call_id`.

2. **`request_made` had to stay a structured boolean.** Deriving it from `error` text would
   make it unparseable and fragile. I required `true` when HTTP was attempted and `false`
   for local/configuration/preflight failures, independent of message wording. The latter
   path still produces one call-log line.

3. **The logbook must not smuggle in thresholds.** I required NFR-002's new aggregation and
   consistency checks (per-session, per-request, `request_made` counts, usage-source and
   missing-usage counts, `usage_source`↔`tokens`) to be documented as procedure, with their
   numeric thresholds **pending clarification**, and to state that gateway usage is never
   treated as zero when usage is missing.

**My correction.**

```
Keep call_id, request_id and session_id distinct; session_id groups a process run.
request_made is a structured boolean, not derived from error text; pre-HTTP failure
logs one line with request_made=false and tokens=null. Do not invent a numeric threshold
for the NFR-002 aggregates. Preserve NFR-006 log coverage and its path-specific Phase 2
call-id joins.
```

**Result.**

- `docs/architecture/runtime-policy-catalog.md` — the LLM call logging section extended with
  a metadata subsection defining
  `session_id`, `request_id`, `usage_source` (`gateway`/`partial`/`missing`) and
  `request_made`, including the pre-HTTP local-failure record. All
  earlier logging requirements preserved.
- `docs/architecture/evaluation-logbook.md` — NFR-002 entry extended with per-session and
  per-request aggregation, attempted HTTP-call count from `request_made=true` rows,
  usage-source and missing-usage counts, and `usage_source`↔`tokens` consistency;
  numeric token budget remains unset.
- Validation (this session): `docs/ai-use-log.yaml` parses; `git diff --check` clean.
- No tests or measurements were run or claimed; documentation-only.

**Open handoffs.** E tests the four fields (including the structured `request_made`
boolean and `usage_source` derivation) and runs the NFR-002 aggregation and
consistency checks, recording real results and confirming no fabricated or zeroed tokens.

**Reflection.** More metadata is only useful if each field has one job. Separating the call
id from the request and session ids, and keeping `request_made` a real boolean instead of a
guess from message text, is what makes the logbook's counts trustworthy rather than
plausible.

---

## Session 10

**Date.** 2026-11-12 · Phase 2: rejection evidence and RP-007

**Contract.** A deterministic rejection writes a `review.jsonl` line carrying the same
`call_id` as its `llm_calls` line and preserves the original `PolicyError.code`.
RP-003/RP-005/RP-006 cover amount, budget and category rejections. Rejected records
are not persisted, and review evidence does not duplicate the full input text.

**Storage failure.** RP-007 covers storage read, validation and write failures through
an independent `StorageError`; these failures do not become `policy:*` rejections and
do not produce a policy review line. A rejection-evidence write failure also surfaces
as `StorageError`. The no-partial-state boundary is required but unverified for D's
append-mode writer. The storage-failure evidence format remains pending.

**Evidence.** These paths supplement main's NFR-006 log-coverage requirement with a
path-specific `call_id` join. E has not yet recorded a measured result.

---

## Session 11

**Date.** 2026-11-13 · Phase 2: align C's contracts with the confirmed D implementation

**Context.** The latest D clarification resolved several items that were still written as
open in C's documents. The requirements image also states that the NFR-002 token-usage
aggregates are for reporting only and must not be treated as pass/fail thresholds. The group
discussion separately approved an optional numeric `expected_spent` input for the validated
storage boundary. This session updates the contracts to match those decisions and leaves the
test-count discrepancy in D's document alone because it is not used by C's deliverable.

**My instruction to the agent.**

```
Use D's current implementation facts. Keep actual request count as api_call_count, meaning
rows with request_made=true; do not add a user_request_count requirement. Record NFR-002
token aggregates as statistics only, with no pass/fail threshold. Report D's four operational
categories gateway/partial/missing/not_called, but keep usage_source's stored enum at the
three values gateway/partial/missing and derive not_called from request_made=false.
For NFR-006 log traceability, check the Phase 2 path-specific joins: accepted is
llm_calls↔storage and rejected is llm_calls↔review; a decision does not create all three
records. Record the approved but unimplemented append_validated(record,
expected_spent=None) design:
total == expected_spent + amount and expected_spent must not be below persisted cumulative
spend. Use the 32-hex-character call_id format. Do not change source,
tests, measurements, or D's unrelated test-count record.
```

**What I changed.** The evaluation logbook now uses `api_call_count`, describes the four
reporting categories without making `not_called` a fourth enum value, and records the image's
"statistics only" rule for token aggregates. NFR-006 measures log-line coverage; Phase 2
additionally checks the applicable evidence pair for each decision. Its measured result
remains `pending`. The runtime-policy catalog records the 32-hex
`call_id`, the path-specific evidence joins, the derived `not_called` category, and the
approved but unimplemented numeric `expected_spent` storage validation design. D's
current signature is `append_validated(record)`. No source code or test files were changed.

**Validation.** YAML parsing and `git diff --check` are run after this session. No tests or
measurements are run or claimed; D's 122-versus-124 test-count discrepancy is outside C's
deliverable.

**Reflection.** A reporting category does not have to become a stored enum value. Keeping
`not_called` derived from `request_made` preserves the compact log contract while still
matching D's four-way report. NFR-006 covers log traceability, with the applicable
evidence-pair join as a Phase 2 structural check.

---

## Session 12

**Date.** 2026-11-13 · Phase 2 C: match the confirmed D logging/token and storage clarifications

**Context.** D's latest clarification fixed the last open questions in C's Phase 2 contracts:
the pre-HTTP local-failure path writes a normal `llm_calls` record with
`request_made=false` and `tokens: null`; processed usage is an object with `input`,
`output` and `total` counts, including `null` for missing counts; and the `not_called`
reporting category is derived, not a
fourth enum. Session 11 had already moved the docs toward D, but the pre-HTTP lifecycle was
still marked pending, the token rules were incomplete, and RP-004 lacked an explicit
appended-fields statement. This session closes those gaps. Documentation only.

**My instruction to the agent.**

```
Match the confirmed D behavior. Record that a pre-HTTP local failure still writes exactly one
llm_calls line with all ten keys, 32-char uuid4().hex ids, usage_source
missing, tokens=null, raw/parsed null, request_made
false — the only request_made=false path. Document token classification (three ints →
gateway; some int some null → partial; all null → missing; non-int → null) and that zero is
never substituted. Keep storing only gateway/partial/missing; derive not_called from
request_made=false and exclude those rows from the usage distribution and missing-usage
count. Keep api_call_count = rows with request_made=true. Add the RP-004 appended-fields
statement. Document the approved but unimplemented
append_validated(record, expected_spent=None) design; D currently implements
append_validated(record).
```

**Agent output (excerpt).**

```
I will replace the pending pre-HTTP block in runtime-policy-catalog.md with the confirmed
one-line lifecycle, extend the token semantics with the gateway/partial/missing
classification and null handling, add the RP-004 appended-fields note, tighten the
append_validated boundary text, and adjust the NFR-002 procedure so not_called rows are
excluded from missing-usage statistics.
```

**What I caught.** Three things.

1. **A pre-HTTP failure is still a logged call.** It is tempting to treat "no HTTP request"
   as "no log line", but D confirmed the opposite: exactly one `llm_calls` line, with all ten
   keys present; `tokens` is explicitly `null`. The `request_made=false` record is the one
   and only failure-before-request path.

2. **Token semantics are a classification, not just a value.** "Record only when the gateway
   supplies it" was too loose: a processed usage object can be all-integer, mixed, or all-null, and
   that determines `usage_source`. Non-integer values (strings, booleans) must normalize to
   `null`, and zero is never a substitute. I required the exact mapping.

3. **`not_called` must not pollute the usage statistics.** It is an operational category
   derived from `request_made=false`, not a fourth stored enum. Rows with `request_made=false`
   are counted separately and excluded from the usage-source distribution and the
   missing-usage count; `api_call_count` stays the count of `request_made=true` rows.

**My correction.**

```
Pre-HTTP failure writes one llm_calls line, ten keys including tokens=null, request_made=false,
the only such path. Token classification exactly as D defined; zero never substituted.
not_called derived from request_made=false, excluded from usage distribution and
missing-usage count; no user_request_count metric. Add RP-004 appended-fields statement and
record the unimplemented append_validated(record, expected_spent=None) design separately
from D's append_validated(record) implementation.
```

**Result.**

- `docs/architecture/runtime-policy-catalog.md` — pre-HTTP lifecycle (§5.2.2) now confirmed
  and no longer pending; token semantics and the `Never fabricate` rule rewritten to the
  gateway/partial/missing classification with object/null handling; RP-004 gains an explicit
  appended-fields note; the unimplemented `append_validated(record, expected_spent=None)` design states
  `total == expected_spent + amount` and `expected_spent >= persisted cumulative spend`, with
  `expected_spent` a validation parameter, not a persisted field. D currently has
  `append_validated(record)`; NFR-006 log coverage has a Phase 2 path-specific join check.
- `docs/architecture/evaluation-logbook.md` — NFR-002 procedure now excludes
  `request_made=false` rows (not_called_calls) from the usage distribution and missing-usage
  count, keeps `api_call_count` as `request_made=true` rows, and states the token
  classification.
- Validation (this session): `docs/ai-use-log.yaml` parses; `git diff --check` clean.
- No source code, tests or measurements were changed.

**Open handoffs.** D's current implementation writes the pre-HTTP call log and classifies
token usage; the `expected_spent` storage design is not implemented. E runs NFR-002 and
NFR-006 measurements and records results. The RP-007 storage-failure evidence format
remains pending.

**Reflection.** The remaining gaps were all cases of "a null is still a value". A skipped
HTTP call still logs; a missing token is still a key set to `null`; a `not_called` row still
exists but must not be counted as a usage failure. Writing the nulls explicitly is what keeps
the statistics honest.

---

## Session 13

**Date.** 2026-11-16 · Phase 2 C: refresh D implementation status and reconcile Phase 2 records

**Context.** D's `df729a9` branch implemented `expected_spent` validation and `request_id`
aggregation, but those changes had not yet merged into `main`.

**My instruction to the agent.**

```text
Refresh the Phase 2 C documentation against D's df729a9 implementation report. Record
expected_spent validation and request_id aggregation as present on D's branch, but keep
them explicitly unmerged and do not describe them as mainline behavior. Update the runtime
policy catalog, evaluation logbook and C handoff so their implementation/evidence status
does not overstate what this checkout contains. Preserve the existing ai-use-log.yaml
history and append this C session; do not rewrite earlier entries. Keep the pass
documentation-only and report the actual validation performed.
```

**Agent output (summary).**

```text
Updated runtime-policy-catalog.md, evaluation-logbook.md and phase2-c-handoff.md to
describe D's expected_spent validation and request_id aggregation as branch-reported,
unmerged Phase 2 work. Kept current-main and D-branch evidence distinct, then appended
the session record to docs/ai-use-log.yaml without replacing earlier entries. The work
was documentation-only; YAML parsing and git diff --check passed, and runtime tests were
not run.
```

**What I caught.** Branch implementation status must not be presented as mainline status.

**My correction.** Keep D's branch status distinct from the current `main` evidence.

**Result.** Updated `runtime-policy-catalog.md`, `evaluation-logbook.md` and
`phase2-c-handoff.md`; appended the C session to `docs/ai-use-log.yaml`. No files were
created.

**Validation.** YAML parsing and `git diff --check` passed. Tests were not run; this was a
documentation-only session with no runtime behavior change.

---

## Session 14

**Date.** 2026-11-19 · Phase 3 C first pass: documentation, static security audit and evidence

**Context.** D had not started or replied with the Phase 3 implementation, so D-dependent
items remained pending.

**My instruction to the agent.**

```text
Make a documentation-only Phase 3 C first pass using origin/main (not a stale local main)
as the code comparison baseline. First establish which implementation and tests actually
exist on this branch. Restructure RP-001 through RP-007 using the required fields—Trigger,
Action, Execution order, State-change guarantee, Evidence and logging, Implementation seam,
and Test-evidence status—and label each claim by provenance (current-code evidence,
historical/unmerged documentation, or pending D). Add an evidence table and explicit gaps
to evaluation-logbook.md. Record that the call-log paths do not all satisfy the four-field
schema and that review-write OSError handling is misclassified; do not present either as
fixed. Keep storage, call_id joins and other D-dependent work pending. Create/update the
C-to-D confirmation document as a development handoff, including its untracked status.
Do not modify src/, test/, .opencode/permissions.jsonc or B-owned requirements. Preserve
the distinction between a smoke test and proof of the security properties.
```

**Agent output (summary).**

```text
Compared the branch with origin/main@6997cef and recorded that src/ and test/ were
byte-identical; this snapshot had no src/storage.py or call_id/request_id/session_id and
no tokens/usage_source/request_made fields. Restructured RP-001–RP-007 into the seven
required fields with provenance labels. Added the §5 evidence table, historical baseline,
static path findings and evidence gaps to evaluation-logbook.md, and created the
development-before-confirmation handoff. Static inspection found call_llm.py was the only
requests importer and identified incomplete call-log fields plus review-write error
misclassification. No source, test or permissions file changed. The recorded offline
smoke run was 41 passed with one urllib3 NotOpenSSLWarning under Python 3.9.6; the report
explicitly did not treat that run as proof of storage, joins, fail-closed behavior or
no-bypass.
```

**What I caught.** At baseline `6997cef`, the C branch's `src/` and `test/` matched
`origin/main`; storage and Phase 2 correlation fields were absent. The call-log schema and
review-write classification were gaps, not satisfied invariants.

**My correction.** Do not claim a permission mismatch when the comparison finds none, and
do not treat the 41-test smoke run as proof of fail-closed logging, evidence joins, storage
atomicity or no-bypass behavior.

**Result.** Restructured RP-001–RP-007 in `runtime-policy-catalog.md` into seven
fields—Trigger, Action, Execution order, State-change guarantee, Evidence and logging,
Implementation seam, and Test-evidence status—with provenance labels distinguishing
code-confirmed facts, unmerged documentation and D-dependent items. Added an evidence table
and explicit gaps to `evaluation-logbook.md`. Rewrote the D confirmation document as a
development-before-confirmation handoff.

**Validation.** The recorded offline run was
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test/offline -q` → 41 passed, 1
`NotOpenSSLWarning` under Python 3.9.6. The log explicitly limits what this smoke run proves.
Static path inspection, YAML parsing and the permission-document comparison were also
recorded as passed; no implementation or tests were changed.

**Open handoffs.** Storage, Phase 2 evidence joins, complete logging-schema coverage,
review-write error classification and a dedicated secret scan remained pending or
unverified.

---

## Session 15

**Date.** 2026-11-19 · Phase 3 C coordination: record D's confirmed design

**Context.** D replied with the confirmed Phase 3 target design; implementation and evidence
were still pending.

**My instruction to the agent.**

```text
Use D's written reply as the source for the confirmed design decisions. Update the C-to-D
confirmation, runtime policy catalog and evaluation logbook, but distinguish design
confirmation from implementation and test evidence. Record D's branch, commit and log
references as D-reported and not independently verified. Keep the current C-branch
snapshot intact; do not label D behavior code-confirmed, promote any NFR to measured, or
use D-branch results as current-branch evidence. Record the agreed PolicyError/StorageError
boundary, persisted-budget authority and expected_spent rules, review-write failure
behavior, no-retry rule, call_id lifecycle, and atomic-write/locking target. Keep privacy
redaction and final whitelist membership pending. This pass is documentation-only; do not
change implementation, tests, permissions or B-owned requirements.
```

**Agent output (summary).**

```text
Marked D as having replied and recorded the reply as a design confirmation, not final
audit evidence. Filled the confirmation document's design answers, including pipeline as
the sole business entry; policy_core as deterministic authority; storage defense-in-depth;
persisted spend as budget authority; equality accepted and over-budget requests routed to
PolicyError(policy:budget, review=True); independent StorageError handling; no automatic
retry; and system-generated call_id removal before policy validation. Recorded D-reported
branch/commit/log references without independent verification. Added a design-confirmed,
implementation-unmerged section to the runtime policy catalog and a coordination-evidence
subsection to the logbook; kept the earlier branch-evidence section unchanged. Privacy
redaction and whitelist finality remained pending. No source, test or permission files
changed, no NFR was promoted, and no runtime tests were run.
```

**What I caught.** A design confirmation does not establish that the design has been
implemented or verified on the current branch.

**My correction.** Keep privacy and whitelist finality pending, and separate the confirmed
design from implementation status.

**Result.** Updated `phase3-c-confirmation-to-d.md` and the policy catalog to record
D's confirmed target design while keeping implementation and evidence pending. D's branch,
commit and log references were labelled as reported by D and not independently verified.
The catalog recorded the agreed `PolicyError`/`StorageError` boundary, persisted-spend
authority, `expected_spent` semantics, review-write failure handling, and the unique-temp-file
plus file-lock atomicity target. The logbook coordinated the historical snapshot and design
confirmation without presenting D's branch as current code evidence. Privacy and whitelist
finality remained pending.

**Validation.** `git diff --check` and YAML parsing passed. No runtime tests were run, and
the recorded source, test and permission paths were unchanged.

**Open handoffs.** D implementation and evidence, privacy finalization and whitelist
confirmation remained pending.

---

## Session 16

**Date.** 2026-11-22 · Phase 3 C post-merge security audit and architecture evidence

**Context.** PR #38 had merged as `main@06ec2f5`; the C-side final audit and evidence update
followed.

**My instruction to the agent.**

```text
Continue the final C security audit against the implementation merged by PR #38 as
main@06ec2f5. Review the model-call, pipeline, policy_core and storage paths for policy
authority, A′ redaction, budget concurrency, direct-storage behavior, fail-closed error
handling and atomic ledger writes; record the associated E tests and evidence in the
architecture docs. Reconcile earlier pre-merge/pending wording with the merged state,
while preserving historical context. Check permission-model.md against
.opencode/permissions.jsonc and the ledger path. After I explicitly authorize it, add only
the read/edit deny for data/records.jsonl* while preserving the broader data/** measurement
allow. Do not change source, tests, B-owned requirements or unrelated permissions. Report
PR/CI/test results as remote evidence and do not say they were rerun locally.
```

**Agent output (summary).**

```text
Reviewed the merged call_llm, pipeline, policy_core and storage paths and updated the
runtime policy catalog, evaluation logbook, confirmation handoff, invariants, permission
model and structural constraints. Recorded the redacted call logs, persisted-budget
authority under lock, direct-storage semantics, fail-closed behavior, atomic ledger append
and E regression coverage. The initial permission comparison found that data/** read/edit
also covered the runtime ledger; after explicit authorization, added read/edit denies for
data/records.jsonl* and documented the exception. The PR report's 237 offline tests and
eight merge checks were recorded as remote results, not local reruns. No source or test
files changed.
```

**What I caught.** The broad `data/**` read/edit permission also covered the runtime ledger.
The audit separately recorded its verification scope for review-log behavior, the private
marker, branch protection, secret scanning, NFR measurements and direct-storage error
messages. These notes describe what was reviewed and the scope of the conclusions; they do
not classify each item as a defect.

**My correction.** Clarified the scope of the safe-error requirement: public `StorageError`
messages and persisted evidence must remain safe; exception chaining may remain for internal
diagnostics. The audit described direct-storage shape-validation behavior separately from
the normal pipeline path. I explicitly authorized the minimal ledger permission exception.

**Result.** Audited the merged implementation at `main@06ec2f5` (PR #38) and recorded
the A′ log redaction, locked persisted-budget authority, direct-storage semantics, fail-closed
errors, atomic ledger append and E regression evidence in the architecture catalog and
logbook. Marked pre-merge statements as historical, clarified that raw-output audit logging
precedes policy validation while normal business data does not, and reconciled the relevant
invariant and governance wording. After explicit human authorization, added read/edit deny
exceptions for `data/records.jsonl*` and documented them. The audit cited the PR's reported
237 offline tests and eight merge checks as remote evidence, not as locally rerun results.

**Validation.** The PR report recorded `python -m pytest test/offline -q` → 237 passed and
eight GitHub checks passed on `06ec2f5`; neither was claimed as rerun in this C checkout.
Documentation checks and verification of the read/edit deny entries were recorded as passed.

**Open handoffs.** The audit recorded its verification boundaries; this session did not
open a new D/E implementation request.

---

## Session 17

**Date.** 2026-11-22 · Phase 3 C: refresh audit after permission correction

**Context.** The current audit needed to reflect the explicit ledger permission correction
without removing the earlier mismatch from the audit history.

**My instruction to the agent.**

```text
Refresh the current evaluation-logbook audit after the ledger-specific permission rule has
been added. State the current read/edit deny for data/records.jsonl* and its alignment with
permission-model.md, but retain the initial broad data/** finding as part of the audit
chronology. Keep this pass documentation-only: do not edit .opencode/permissions.jsonc,
source, tests or B-owned requirements. Report only the checks actually run.
```

**Agent output (summary).**

```text
Updated evaluation-logbook.md so the current audit reflects read/edit denial for
data/records.jsonl* and alignment between the permission model and machine configuration,
while preserving the earlier mismatch as chronology. The session changed no source,
tests or permission configuration. git diff --check and YAML parsing passed; runtime tests
were not run because the change was documentation-only.
```

**What I caught.** The initial mismatch is historical; the current configuration denies
read and edit access to `data/records.jsonl*`.

**My correction.** Keep the permission configuration unchanged in this pass and do not imply
that OpenCode's runtime matcher was independently tested.

**Result.** Updated the current audit section to show that read and edit access to
`data/records.jsonl*` is denied and aligned with the permission model, while retaining the
initial mismatch as audit chronology. Recorded that OpenCode's runtime matcher had not been
independently exercised. No implementation, tests or permission configuration were changed.

**Validation.** `git diff --check` and YAML parsing passed; source tests were not run for this
documentation-only update.

**Open handoffs.** Independent verification of OpenCode's runtime permission matcher remained
unverified.
