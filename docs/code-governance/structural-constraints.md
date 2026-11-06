# Structural Constraints — Code Governance (draft v0.1, owner: role D)

> Purpose: the conventions every contributor must follow so that our code, tests and
> documents stay consistent. Anything not stated here is decided in `AGENTS.md`
> (for the AI agent) or in `docs/architecture/` (for the design).
>
> Status: **draft for team review.** Owner of this file after review: role C
> (code governance). Author of v0.1: role D.

---

## 1. Repository layout

```
<team-app>/
├── README.md
├── AGENTS.md
├── architecture-blueprint.md
├── Prompt.md
├── Report.md
├── requirements.txt
├── src/                     full source              (D8 · owner D)
├── test/
│   ├── offline/             deterministic, no network (D4/D8 · owner E)
│   └── live/                calls the model           (D4/D8 · owner E)
├── docs/
│   ├── req/                 requirements.yaml, req-schema.json   (D1 · owner B)
│   ├── architecture/        11 artifact types                    (D2 · owners B and C)
│   └── code-governance/     structural-constraints.md, verification-constraints.md,
│                            mcp-tool-manifest.md                 (D3/D4 · owners C and E)
├── .opencode/               permissions.jsonc, rules.md          (D3 · owner C)
├── .agent/                  rules.md                             (D3 · owner C)
├── .github/workflows/ci.yml                                     (D7 · owner E)
├── prompts/                 prompt_v*.yaml
├── transcripts/             <student-id>-<name>.md, one per student (D5 · owner A)
└── logs/                    runtime output, gitignored
```

`test/` is a sibling of `src/`, as the course's project tree specifies and as the
standard Python layout requires. A test directory is never nested inside the source
directory.

Both directories form the single deliverable D8: `src/` is written by D, `test/` is
written by E. In the Phase 3 rotation, D reviews test coverage of core business logic.

---

## 2. Module boundaries (non-negotiable)

| Rule | Why |
|---|---|
| `src/call_llm.py::extract()` is the **only** place that calls the model | one choke point makes logging auditable |
| `src/policy_core.py` is the **only** place that decides an outcome from model output | the probabilistic component must never decide |
| No module may import `requests` except `call_llm.py` | otherwise calls escape the log |
| No module may write to persistent storage before `policy_core` validation passes | prevents contaminated data |
| `logs/` is append-only at runtime; no module deletes from it | auditability |

---

## 2.1 `AGENTS.md` authoring

`AGENTS.md` belongs to role **B** (it is listed under B's deliverables).

Role **D authors the working v0.1 draft**, for three reasons:

1. **D is the only role constrained by it every day.** The path whitelist in §2 decides
   what the agent may touch; if it is written by someone who is not driving the agent,
   it is either too tight to work or too loose to govern.
2. **D discovers the boundary empirically.** Whether the agent can be kept out of a
   directory is a fact established by trying it, not by design intent.
3. **The draft is cheap to replace, the observations are not.** B and C can rewrite the
   wording freely; what they cannot reconstruct later is the record of which paths the
   agent actually tried to modify.

Handover: D produces v0.1, B adds architectural constraints, C adds the permission
whitelist, and the merged file is owned by B from v1.0 onwards.

---

## 2.2 Who defines a guard, who implements it

**Settled by the team on 2026-11-06.**

| Step | Owner | Artefact |
|---|---|---|
| Decide **which** rules exist and **what** each threshold is | **C** | `docs/architecture/invariants.md`, `runtime-policy-catalog.md` |
| Decide the **degradation behaviour** when a rule fires | **C** | `runtime-policy-catalog.md` |
| Turn each rule into a guard function plus a negative test | **D**, by directing OpenCode | `src/policy_core.py`, `test/offline/test_invariants.py` |
| Verify that every rule can actually be violated in a test | **E** | `verification-constraints.md` |
| Review that no rule was silently weakened | **D**, Phase 3 architecture-review rotation | review memo |

**Neither C nor D edits a generated file by hand.** C writes the specification; D obtains
the implementation from the agent and reviews the result (§9).

### Guard specification — the handoff format from C to D

C hands over one block per invariant. Nothing is implemented until the block is complete.

```
INV-<###>
Condition   : <if <observable condition> then reject>
Threshold   : <the value, and where it comes from in the case>
Exception   : PolicyError
On failure  : <reject | REVIEW | retry | quarantine>
Boundary    : <the limit ± 1 values that must be tested>
Evidence    : <what is written to logs/ or the decision record>
```

D implements that block as exactly one function `enforce_<subject>` plus at least one test
whose name contains the invariant id and which **fails when the guard is removed**.

---

## 3. Naming conventions

| Kind | Convention | Example |
|---|---|---|
| Functional requirement | `REQ-FR-###` | `REQ-FR-001` |
| Non-functional requirement | `REQ-NFR-###` | `REQ-NFR-002` |
| Invariant | `INV-###` | `INV-001` |
| Guard function | `enforce_<subject>` | `enforce_positive_amount` |
| Test | `test_inv###_<behaviour>` | `test_inv001_rejects_negative_amount` |
| Exception | `<Domain>Error` | `PolicyError`, `LlmTransportError` |
| Module | lower_snake_case | `policy_core.py` |

**One invariant = one guard function = at least one negative test.**
If an invariant cannot be written this way, it is not an invariant yet.

---

## 4. Error conventions

| Rule | Detail |
|---|---|
| All policy violations raise `PolicyError` | defined once in `policy_core.py`; nothing else defines its own rejection type |
| Never swallow an exception silently | log it, then either re-raise or convert to a documented rejection |
| Transport failures raise `LlmTransportError` | network, auth, quota — distinct from policy rejection |
| Validation happens **before** any state change | no "write then check" |

> Rationale: a rejection must be distinguishable from a defect. If both surface as the
> same generic error, tests cannot tell "correctly refused" from "crashed".

---

## 5. Logging contract

**File:** `logs/llm_calls.jsonl` — one JSON object per line, append-only.

| Field | Required | Meaning |
|---|---|---|
| `input` | yes | the exact text sent by the user |
| `raw` | on success | the model's raw string response |
| `parsed` | on success | the parsed object, or `null` if parsing failed |
| `error` | on failure | short code: `not_json`, `http 401`, `transport: ...` |

- Secrets must never be logged.
- A call whose result cannot be logged must not be used (fail-closed).
- Extra fields are allowed but must not rename the four above.

---

## 6. Configuration

| Variable | Meaning |
|---|---|
| `LLM_BASE_URL` | gateway root, including `/v1` if the gateway requires it |
| `LLM_API_KEY` | credential, **never** committed |
| `LLM_MODEL` | deployment name, e.g. `CS5351/DeepSeek-V4-Flash` |

- `.env` is gitignored. `.env.example` lists the keys with placeholder values.
- No credential may appear in code, tests, docs, transcripts, the report or the video.

---

## 7. Environment

- Python **3.9+**. The reference environment is the team venv `SoftEngineering`, which
  runs **3.9.7**, so code must not use 3.10-only syntax: `match`, `X | Y` in runtime
  annotations, `except*`, or parenthesised context managers.
- Use `from __future__ import annotations` when PEP 604 style annotations are wanted.
- Dependencies are declared in `requirements.txt`; no ad-hoc `pip install` without
  updating it.
- The virtual environment lives outside version control (`.venv/` is gitignored).
- A teammate reproduces the environment with:
  `python -m pip install -r requirements.txt`

---

## 8. Git workflow

| Item | Convention |
|---|---|
| Default branch | `main`, protected |
| Work branches | `feat/<name>-<topic>`, `fix/<name>-<topic>` |
| Commit message | `<type>: <imperative summary>` — `feat`, `fix`, `docs`, `test`, `chore` |
| Pull requests | one reviewer minimum; the author never merges their own PR |
| Reviewers | rotate as per the role table; **never review your own artefact** |
| Never commit | `.env`, `logs/`, `__pycache__/`, `.venv/`, API keys |

---

## 9. Change protocol

| Change | Requires |
|---|---|
| A new requirement or a changed invariant | update `docs/req/`, then `trace-matrix.md` |
| A change to a module boundary in §2 | a new ADR under `docs/architecture/adr/` |
| A change to this file | agreement from roles B, C and D; note it in the report |
| A new dependency | stated in the plan, approved by a human, added to `requirements.txt` |

---

## 10. Definition of done (any task)

- [ ] The plan was approved before any code was written
- [ ] `pytest test/offline -q` passes
- [ ] Every new invariant has a test that **fails without the guard**
- [ ] No file outside the permitted paths was modified
- [ ] The corresponding entry exists in `transcripts/`
- [ ] `trace-matrix.md` is updated if a requirement is touched

---

## 11. Settled decisions (team agreement, 2026-11-06)

| Decision | Resolution | Detail |
|---|---|---|
| Deterministic interceptor | **C defines** the rules, thresholds and degradation behaviour; **D implements** them by directing OpenCode; neither edits generated code by hand | §2.2 |
| `AGENTS.md` | Owned by **B**; **D authors the working v0.1**; merged file owned by B from v1.0 | §2.1 |
| `test/` location | Sibling of `src/`, never nested inside it; `src/` is D, `test/` is E, both form deliverable D8 | §1 |
