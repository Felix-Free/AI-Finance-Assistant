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

**Date.** 2026-11-12 · Phase 2 C1: measurement permission configuration

**Context.** Phase 2 introduces measurement work (inputs under `data/`, scripts under
`scripts/`, results under `docs/measurements/`). C1 is the permission step only: widen the
agent's whitelist just enough to read and edit those three paths and to run the
measurement commands, without opening anything else. Storage, `call_id`, token accounting
and NFR-006 belong to D/E and are deliberately out of scope.

**My instruction to the agent.**

```
Complete only C1. In .opencode/permissions.jsonc add data/**, scripts/** and
docs/measurements/** to read and to edit as allow, and add the bash allow
patterns pytest*, python -m py_compile* and python scripts/*. Preserve every
existing deny/ask rule, comment and default; broaden nothing else. Then append a
new Phase 2 C session to the transcript and the ai-use-log. Do not touch src/,
test/, docs/architecture/ or docs/code-governance/. Do not generate runtime data.
```

**Agent output (excerpt).**

```
C1 completed. The measurement paths were added to the read and edit allowlists,
the three measurement commands were added to the bash allowlist, and the
transcript and ai-use-log were updated. No source, test or runtime data files
were changed.
```

**What I caught.** Two things.

1. The permission expansion had to remain limited to the three measurement path
   trees and the three requested command patterns. Storage, `call_id`, token
   accounting and NFR-006 were deliberately left for D/E.

2. The initial pytest statement was not enough evidence because it did not establish
   that pytest had actually run in the project environment. The exact result was
   re-run and corrected in Session 6.

**My correction.**

```
Keep C1 limited to the requested permission entries and evidence records. Do not
describe pytest as having run or passed unless the exact command succeeds; record
the interpreter and exit status when the environment cannot execute the suite.
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
`./.venv/bin/python`, and a clean `git diff --check`. The project venv had no pytest;
the later Session 6 re-run recorded the system `python3 -m pytest` result as zero tests
collected with exit code 5, not as a passing test run.

**Open handoffs.** The measurement scripts themselves, the `data/` inputs and the
`docs/measurements/` reports are subsequent Phase 2 steps. The `python scripts/*`
allow is deliberately scoped to the repo's own scripts directory.

**Reflection.** A permission change is the one edit where "it works" is not the goal:
every added line is a new capability for the agent, so the session records both what was
granted and what was explicitly left denied.

---

## Session 6

**Date.** 2026-11-12 · Phase 2 C1 follow-up: synchronize permission model, correct pytest evidence

**Context.** Two gaps in the C1 commit `88aab30`. First, `.opencode/permissions.jsonc` was
widened but `docs/architecture/permission-model.md` still described only the Phase 1
boundaries, so document and config disagreed — the very thing §"Status" of that file warns
against. Second, Session 5 recorded the pytest result as "no tests ran (empty suite)"
without establishing that the command could run; the project venv has no pytest installed,
so that claim was not honest. This session fixes both; it does not change the C1 permission
entries themselves.

**Why the permission model was synchronized.** `permission-model.md` is the authoritative
statement and `.opencode/permissions.jsonc` is its machine-readable form; the file's own
preamble says they must never disagree. Adding §3.1 and three rows to the §2 table records
the C1 expansion (data, scripts, measurements as read+edit `allow`; pytest, py_compile and
`python scripts/*` as bash `allow`), states that runtime files under `data/` must not be
committed, and restates that default-deny, deny-overrides-allow, `.env` protection and the
protected paths are unchanged.

**Corrected pytest result (what actually ran in this environment).**

```
$ pytest test/offline -q
zsh: command not found: pytest              # exit 127 — pytest CLI not on PATH

$ ./.venv/bin/python -m pytest test/offline -q
.../​.venv/bin/python: No module named pytest   # exit 1 — venv has no pytest

$ python3 -m pytest test/offline -q          # system Python 3.9.6, pytest 8.4.2
no tests ran in 0.00s                        # exit 5 — collected nothing
```

So the honest record is: **tests were not exercised in the project venv** (no pytest there);
the only interpreter with pytest collected zero tests and exited 5. This is **not** a pass,
and it is not evidence that the suite is empty in the sense of "green" — no test ran.

**Files changed in this follow-up.**

- `docs/architecture/permission-model.md` — §2 rows and new §3.1 for the C1 expansion.
- `transcripts/60339160-QiangWanyun.md` — Session 5 pytest claim corrected; this entry.
- `docs/ai-use-log.yaml` — matching Session 6 entry.

`.opencode/permissions.jsonc` was not modified; its C1 entries are preserved.

**My correction.**

```
Synchronize the doc to the config instead of leaving them inconsistent, re-run the
validation for real, and record what actually happened rather than copying a plausible
sounding result. Do not amend 88aab30; make a follow-up commit.
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

**Date.** 2026-11-12 · Phase 2 C-side: policy contracts (C2/C3/C4/C6) and evaluation logbook

**Context.** Phase 2 agreed the `call_id` contract (C2), the `llm_calls` logging contract
(C3), the storage-failure rule (C4) and the NFR-006 evidence-join rule (C6). None of it was
written down on the C side. This session records those contracts in the runtime policy
catalog, creates the evaluation logbook the NFRs are measured in, and leaves D/E code
untouched. Specs and documentation only.

**My instruction to the agent.**

```
Document the agreed Phase 2 contracts without changing Phase 1 policy ids. Record C2
call_id (uuid4().hex[:12], returned via __call_id__, removed before policy_core), C3
llm_calls extra fields (call_id, tokens; tokens only from the gateway, never fabricated),
C4 StorageError independent of policy:*, no partial state, and C6 NFR-006 conditional
evidence (accepted → llm_calls + storage; rejected → llm_calls + review; rejected
decisions create no storage record; "three relevant records carry the same call_id").
Also record the approved D decisions: call_id format, and _append_review preserving the
original rejection code. Create docs/architecture/evaluation-logbook.md with pending,
not invented, results. Do not touch src/ or test/. Only update the MCP manifest if a real
new tool exists.
```

**Agent output (excerpt).**

```
I will add a §5 Phase 2 addendum to runtime-policy-catalog.md covering C2/C3/C4/C6 and
the approved D decisions, create docs/architecture/evaluation-logbook.md with NFR-001,
NFR-002 and NFR-006 as pending/blocked (no fabricated results), and leave
mcp-tool-manifest.md unchanged because no new MCP tool or entry point exists.
```

**What I caught.** Three things.

1. **The `call_id` had to stay at `uuid4().hex[:12]`.** It is tempting to let a caller
   pass or shorten its own id, but C2 fixes both the format and the location of generation
   inside `call_llm`. I kept the spec to that one format and one producer, and required
   `__call_id__` to be removed before `policy_core` so the guard never sees a private key.

2. **`tokens` must not be invented.** Token accounting is easy to guess at, so I required
   the field to be recorded only when the gateway supplies usage data, and to be absent or
   `null` otherwise. `policy:*` also stays reserved for rule rejection, so a storage
   failure (`StorageError`) is never dressed up as a policy outcome.

3. **The NFRs must not claim results.** I required NFR-001, NFR-002 and NFR-006 to be
   recorded as `pending`/`blocked` with no observed value, and the manifest left untouched
   because there is no new MCP tool — an application entry point is not an MCP tool.

**My correction.**

```
Keep the call_id format and generation site fixed; do not let callers synthesize ids.
tokens only when the gateway reports them. StorageError is independent of policy:*.
NFR-006 evidence is conditional: accepted → llm_calls + storage, rejected → llm_calls +
review, and a rejected decision creates no storage record. Leave every NFR result
pending or blocked; do not invent a measurement. Do not add an MCP tool entry.
```

**Result.**

- `docs/architecture/runtime-policy-catalog.md` — status line extended for Phase 2, and a
  new §5 addendum: §5.1 C2 `call_id`, §5.2 C3 `llm_calls` contract, §5.3 C4 storage
  failure, §5.4 C6 NFR-006 conditional evidence, §5.5 approved D decisions. RP-001..RP-006
  keep their ids and meaning.
- `docs/architecture/evaluation-logbook.md` — new; NFR-001, NFR-002 and NFR-006 with
  metric, threshold, input, procedure, expected evidence, owner and status. All results are
  `pending` or `blocked`; NFR-006 is blocked on the `call_id` pipeline.
- `docs/code-governance/mcp-tool-manifest.md` — **not** modified; no new MCP tool or entry
  point exists.
- Validation (this session): `docs/ai-use-log.yaml` parses; `.opencode/permissions.jsonc`
  parses under generic JSONC; `git diff --check` clean; `git status` shows only the
  intended files plus the pre-existing untracked `.DS_Store` files.
- No test was run for this session (documentation only) and no measurement was claimed.
  `src/` and `test/` are unchanged.

**Open handoffs.** D implements C2/C3/C4 in the pipeline (`call_id` generation, `tokens`
from gateway usage only, `StorageError`); E runs NFR-001/NFR-002 and, once the `call_id`
pipeline exists, NFR-006, recording real results in the logbook. Thresholds for NFR-001 and
NFR-002 come from the requirements source and are recorded, not invented, when confirmed.

**Reflection.** The discipline here is the same as in Phase 1: a contract that is not
written down is not a contract, and a logbook whose entries are all "green" before anything
ran is worse than an empty one. Pending is a truthful state.

---

## Session 8

**Date.** 2026-11-12 · Phase 2 C: tighten the NFR-006 threshold and fix logbook table format

**Context.** Session 7 wrote the NFR-006 contract two ways in one breath: the strict
three-record threshold and the conditional evidence shape were mixed together, and the
threshold was weaker than agreed ("where applicable", "whatever records happen to exist").
In `evaluation-logbook.md` the NFR-006 `Observed result` row had also fallen outside the
table. This session is a documentation-only correction: it separates the threshold from the
conditional shape and repairs the table. No source, test or runtime file is touched.

**My instruction to the agent.**

```
The agreed NFR-006 threshold is strict: three relevant call_id locations/evidence records
for the same decision must carry the same call_id. Remove the "where applicable" wording
and the "whatever records exist" fallback. Keep the conditional evidence shape as a
separate rule (accepted -> llm_calls + storage; rejected -> llm_calls + review; rejected
creates no storage record). If the exact names of the three locations are not in the repo,
keep the agreed wording and mark the precise measurement mapping pending. Also move the
NFR-006 Observed result row into its table. Do not change RP-001..RP-006 or NFR-001/002.
```

**Agent output (excerpt).**

```
I will rewrite §5.4 so the threshold and the conditional evidence shape are separate, with
identical threshold wording in the runtime policy catalog and the evaluation logbook. The
exact three call_id locations are not named in the repo, so I keep the agreed wording and
mark the mapping pending. I will move the Observed result row into the NFR-006 table and
leave the explanatory blockquote after it.
```

**What I caught.** Three things.

1. **The threshold had to stand alone.** Session 7 blended "every decision joins" with the
   conditional shape and hedged with "where applicable" and "otherwise the join is evaluated
   over the records that exist". That turns a strict rule into a discretionary one. I
   required the strict sentence — three relevant `call_id` locations/evidence records for
   the same decision must carry the same `call_id` — to be stated in full and in both files.

2. **The conditional shape is a different rule.** Accepted → llm_calls + storage; rejected →
   llm_calls + review; a rejected decision creates no normal storage record. That describes
   *which* records a decision has, not *how many must share the id*. I required the two to be
   visibly separate so neither is read as a substitute for the other.

3. **The three locations are not named in this repository.** Rather than invent names or
   weaken the rule to a two-record join, I kept the agreed wording and marked the precise
   measurement mapping **pending clarification**.

**My correction.**

```
State the strict threshold verbatim; drop "where applicable" and any "whatever records
exist" fallback. Keep the conditional evidence shape as its own rule. Do not invent the
three location names — mark the mapping pending. Move the NFR-006 Observed result row into
its table. Do not touch RP-001..RP-006 or NFR-001/002.
```

**Result.**

- `docs/architecture/runtime-policy-catalog.md` — §5.4 retitled and split into a strict
  threshold (with a pending-clarification note) and a separate conditional evidence shape.
  RP-001..RP-006 unchanged.
- `docs/architecture/evaluation-logbook.md` — NFR-006 rows split into Threshold, Threshold
  mapping (pending), Conditional evidence shape, and the `Observed result` row moved inside
  the table; the blockquote remains after the table. NFR-001 and NFR-002 unchanged.
- Validation (this session): `docs/ai-use-log.yaml` parses; `git diff --check` clean.
- No tests or measurements were run or claimed; this is a documentation-only correction.

**Open handoffs.** The pipeline/spec owners (D/B) supply the exact names of the three
required `call_id` locations so the pending measurement mapping can be fixed; until then the
threshold stays as written and NFR-006 stays `blocked`.

**Reflection.** A threshold and a shape are not the same promise. Writing "three records
share an id" next to "a decision has these records" invited the weaker reading; separating
them keeps the rule strict and leaves the unknown — the location names — honestly marked
pending instead of papered over.

---

## Session 9

**Date.** 2026-11-12 · Phase 2 C: document the four approved logging metadata fields

**Context.** Phase 2 logging needs more than `call_id` and `tokens` to answer the questions
role B asks about the system: how a user session behaved, how one user request fanned out
into several API calls, whether a call actually hit the network, and where the token numbers
came from. Four additional fields were approved — `session_id`, `request_id`,
`usage_source` and `request_made`. This session is documentation-only: it extends the C3
contract and the NFR-002 evidence in the logbook. No source, test, log, permission or MCP
file is touched.

**My instruction to the agent.**

```
The user approved four more llm_calls fields: session_id, request_id, usage_source
(enum: gateway, partial, missing), request_made (boolean; true only when an HTTP request
was actually sent). Extend the C3 section with their exact meaning and keep every existing
C3 requirement intact. Do not define request_made from error text. If the local-failure
lifecycle is undefined, mark it pending rather than inventing a rule. Update NFR-002 to
cover per-session and per-request aggregation, request_made counts, usage-source counts,
missing-usage counts and usage_source/tokens consistency. Do not invent thresholds. Keep
NFR-006 exactly as it is.
```

**Agent output (excerpt).**

```
I will add a §5.2.1 subsection to the C3 contract defining session_id, request_id,
usage_source (gateway/partial/missing) and request_made (HTTP-only true), preserving
input/raw/parsed/error, call_id uniqueness, gateway-only tokens, no fabricated or zero
token counts, policy:* reservation and one-line-per-call. I will mark the pre-HTTP local
failure lifecycle pending. I will extend NFR-002's procedure with the aggregation and
consistency checks and leave NFR-006 unchanged.
```

**What I caught.** Three things.

1. **The four fields answer different questions and must not collapse into one.** `call_id`
   identifies one actual API call; `request_id` groups the calls one user request triggers
   (one request may make several); `session_id` groups a whole session. I required the
   contract to say plainly that neither new id replaces `call_id`.

2. **`request_made` had to stay a structured boolean.** Deriving it from `error` text would
   make it unparseable and fragile. I required `true` only when an HTTP request was actually
   sent and `false` for local/configuration/preflight failures, independent of message
   wording — and left the exact pre-HTTP lifecycle pending rather than inventing it.

3. **The logbook must not smuggle in thresholds.** I required NFR-002's new aggregation and
   consistency checks (per-session, per-request, `request_made` counts, usage-source and
   missing-usage counts, `usage_source`↔`tokens`) to be documented as procedure, with their
   numeric thresholds **pending clarification**, and to state that gateway usage is never
   treated as zero when usage is missing.

**My correction.**

```
Keep call_id, request_id and session_id distinct; state that the new ids group calls but
do not identify one. request_made is a structured boolean, not derived from error text;
pre-HTTP local failure lifecycle is pending. Do not invent thresholds for the NFR-002
aggregates. Leave NFR-006's strict three-call_id threshold and conditional evidence shape
exactly as they are.
```

**Result.**

- `docs/architecture/runtime-policy-catalog.md` — §5.2 C3 extended with §5.2.1 defining
  `session_id`, `request_id`, `usage_source` (`gateway`/`partial`/`missing`) and
  `request_made`, plus a pending-clarification note for the pre-HTTP local failure. All
  earlier C3 requirements preserved.
- `docs/architecture/evaluation-logbook.md` — NFR-002 entry extended with per-session and
  per-request aggregation, `request_made` request count, usage-source and missing-usage
  counts, and `usage_source`↔`tokens` consistency; thresholds marked pending. Summary row
  and change protocol updated. NFR-006 unchanged in meaning.
- Validation (this session): `docs/ai-use-log.yaml` parses; `git diff --check` clean.
- No tests or measurements were run or claimed; documentation-only.

**Open handoffs.** D implements the four fields in `call_llm` (including the structured
`request_made` boolean and `usage_source` derivation), and must fix the pre-HTTP local
failure record shape once clarified. E tests the fields and runs the NFR-002 aggregation and
consistency checks, recording real results and confirming no fabricated or zeroed tokens.

**Reflection.** More metadata is only useful if each field has one job. Separating the call
id from the request and session ids, and keeping `request_made` a real boolean instead of a
guess from message text, is what makes the logbook's counts trustworthy rather than
plausible.
