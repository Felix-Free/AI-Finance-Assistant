# 60915652 — Liu Wanyang

> Annotated transcript of my work with the AI coding agent (OpenCode).
> Every entry records: what I instructed, what the agent produced, what I caught, and
> what I changed. This file is evidence of human authorship and supervision.
>
> Role: **D — development and integration.** Append a new entry after every working
> session; do not rewrite earlier entries.

---

## 2026-11-06 · Environment bring-up and first model call (Phase 1)

**Context.** Get one repeatable way for our own code to call the model, with a log we
can audit later. This is the Phase 1 deliverable for role D ("调通 DeepSeek API").

**My instruction to the agent.**

```
PLAN FIRST. Do not write code yet. Give me a plan with: files you will touch,
functions you will add, and what you will NOT change. Wait for my approval.
Task: a single entry point that calls the chat completions endpoint, parses JSON,
appends one line per call to logs/llm_calls.jsonl, and does not swallow parse errors.
Also add a system prompt that forces a JSON object with amount and category.
```

**Agent output (excerpt).**

```
I will create src/call_llm.py with extract() and _append_log(). I will also add
logs/ to .gitignore. On a parse failure I will return {} so the caller can continue.
```

**What I caught.** Two things.

1. **The plan silently swallowed failures.** `return {}` on a JSON parse error means a
   broken model response looks like an empty record, and the caller cannot tell the
   difference between "the sentence had no amount" and "the model returned prose".
   That contradicts our intention that every model output is validated before use.

2. **After the first successful call, the output was not what we need.** The model
   returned `{"amount": 350, "category": "food"}` — the display name for a category is
   in English and is free text. Nothing in the system constrains the vocabulary, so
   the same sentence in a different run could produce `"Food"`, `"餐饮"` or
   `"meal"`. Downstream code and tests cannot depend on that.

**My correction.**

```
Do not swallow the JSONDecodeError. Log the raw text with an error field, then re-raise,
so the caller decides whether the record is rejected.
Category must be one of a closed list defined in code, not whatever the model chooses.
We will enforce that in src/policy_core.py, not in the prompt.
```

**Result.**

- `src/call_llm.py` raises on non-JSON, and every call (success or failure) appends
  exactly one JSONL line with `input / raw / parsed / error`.
- Smoke test output: `[parsed] {'amount': 350, 'category': 'food'}` and one line in
  `logs/llm_calls.jsonl`.
- `.env` holds the credentials; `logs/` and `.env` are gitignored. No key appears in
  any committed file.
- Follow-up recorded: `INV-002` (category must be in a closed list) is to be enforced
  in `policy_core.py` with a negative test.

**Reflection.** The agent optimises for "the happy path runs". Both defects were the
same underlying mistake: letting a probabilistic component decide something that
deterministic code must decide. The rules "never swallow an error" and "the model
proposes, code disposes" therefore belong in `AGENTS.md`, not in my head.

---

## 2026-11-08 · Boundary decisions before coding (requirement and architecture inputs)

> Requirements and architecture are owned by roles B and C. This entry records only the points
> where implementation work forced a decision, and what I did with it: **propose, then escalate —
> never decide unilaterally.**

**Requirement boundary — the category vocabulary must be a closed set.**
The model answered `category: "food"` for a Chinese sentence, and nothing in the system
constrained the vocabulary: a second run could have returned `"Food"`, `"餐饮"` or `"meal"`.
I treated this as a requirement-level question ("what may the record contain?"), not as a code
detail, and proposed that the vocabulary be a closed set enforced by code — which became
`INV-002`. Role C owns the specification; my contribution was the trigger and the evidence that
the free-text answer was unstable.

**Architecture boundary — where validation lives.**
Three candidate placements for validating model output:

| Candidate | Verdict |
|---|---|
| (a) inside `call_llm.extract()` | rejected — mixes transport with policy, and a guard inside a transport call cannot be tested in isolation |
| (b) a separate `policy_core` module | **chosen** — one module decides, so it can be tested without network |
| (c) the storage layer | rejected — a single writer can bypass it, and then "the model proposes, code disposes" is only a slogan |

I proposed (b) plus the rule "nothing may write before validation", and wrote the rule into
`docs/code-governance/structural-constraints.md` §2. Role B owns the architecture blueprint;
this was an input to it, not a replacement for it.

**Specification boundary — evidence for a rejection.**
While checking the implementation against `invariants.md` I found that its Evidence column and
RP-004 ("exactly one line per call") could not both hold. I did not choose a resolution: I put
three options to the specification owner and implemented the one she selected (see the entry of
2026-11-09).

**Reflection.** An implementer sees requirement and architecture gaps that their owners cannot
see, because the gaps only appear once the code is written. The useful behaviour is neither to
fill them silently nor to stay quiet about them, but to surface them with evidence and hand the
decision back to the owner. Two of the three decisions above came back changed after the owner
looked at them, which is exactly why they had to go to the owner.

---

## 2026-11-09 · policy_core and the transport seam, written by OpenCode (Phase 1)

**Context.** Role C had finished the three invariant specifications
(`docs/architecture/invariants.md`: `C-INV-001/002/003`, mapped to global `INV-001/002/003`).
My job was to turn them into deterministic guards plus a replaceable transport seam, so that
role E can test the pipeline without network access.

**My instruction to the agent.** I did not type free-form instructions. I wrote a task sheet in
a fixed nine-section format (`OPENCODE_TASK_02.md`) and pasted it whole. The parts that mattered:

```
## 2. Task A — extract a replaceable transport seam in src/call_llm.py
1. Add a private function _post(payload: dict) -> str ...
3. _post must be a module-level function (not a closure inside extract), so a test can
   replace it with monkeypatch.
Must not change: the name, signature and return type of extract; the four log fields
input / raw / parsed / error; fail-closed logging.

## 3.3 INV-003 — reject only when spent + amount > budget_limit;
          spent + amount == budget_limit must be accepted
> Use ">", never ">=". This is the single most likely defect in this task.

## 8. Anti-patterns I will reject on sight
| 2 | Decimals tested with round(x, 2) == x | binary floating point makes 0.005 unstable |
| 3 | Whitelist enforced by prompt text | rules must be enforced by code |
```

**Agent output (excerpt).** Its plan, before any code:

```
Task B — src/policy_core.py (new)
- enforce_amount: reject bool, non-number, non-finite (math.isfinite), <= 0,
  Decimal(str(amount)).as_tuple().exponent < -2; returns amount.
- enforce_budget: comparisons via Decimal(str(x)); reject only spent+amount > limit
  (> not >=); raises review=True; returns new total.
Risks needing your input: 1. review.jsonl path 2. two log lines on transport failure?
3. test files — do they need your OK? 4. enforce_amount return type — int or float?
```

**What I caught.**

1. **Its plan did not cover a malformed response envelope.** `_post` was going to do
   `resp.json()["choices"][0]["message"]["content"]`; if the gateway returned HTTP 200 with an
   unexpected body, that raises `KeyError`/`IndexError`, which is neither a policy rejection nor
   a transport error. I required every protocol failure to be converted to `LlmTransportError`.

2. **It chose a test filename that was already reserved.** It proposed
   `test/offline/test_invariants.py`, which is role E's exhaustive boundary suite. I required
   `test_policy_core_smoke.py` and `test_pipeline_seam.py` instead, and required the agent to say
   in `CHANGED FILES` that these are smoke tests only. Two people writing the same file is a
   merge conflict, not a test.

3. **A commit I did not expect — and the ambiguity was mine.** My approval message said
   "Commit A and B separately (one commit per file group), because they must be revertible
   independently". It never named **who** runs the command. The agent executed it, and the
   report showed two commits (`feb5eb2`, `5d540c4`, both 17:49). `AGENTS.md` §8 says the agent
   may not run `git commit` — so the instruction I wrote contradicted the rule the agent was
   bound by. **The agent did the right thing next: it surfaced the contradiction and asked which
   rule wins**, instead of quietly picking one. That is the behaviour I want from it.

**My correction.**

```
CORRECTION ON THE COMMIT POINT (my fault, not yours):
My earlier message said "Commit A and B separately". I did not say who should run the
command, and you reasonably executed it. That was an ambiguous instruction on my side,
not a violation by you. Recorded. From now on the actor is always me: you never run
git commit or git push. Keep those two commits as they are; I will not reset them.

FIX 1 (required). validate_record crashes when the model returns a JSON array or a string:
raw.get(...) raises AttributeError, which is not a PolicyError. Add:
    if not isinstance(raw, dict):
        raise PolicyError(..., code="policy:amount", review=False)
FIX 2 (required). validate_record discards the running total; return it so pipeline can log it.
```

I did **not** rewrite history. The two commits had the right boundaries (one for the seam, one for
the guards), so I kept them, recorded the violation here, and relied on the mechanism that was
already being prepared: role C's `.opencode/permissions.jsonc` sets `"git commit": "deny"`.

**Result.**

- `python -m py_compile` and `import` pass; `pytest test/offline -q` → **34 passed**.
- The acceptance script printed `ALL ACCEPTANCE CHECKS PASSED`, covering `-1`, `0`, `0.005`,
  `100.001`, `"350"`, `None`, `True`, `nan`, `inf`; equality-at-budget accepted; over-budget and
  out-of-vocabulary rejected with `review=True`.
- The live call in the sandbox failed first with `LLM_BASE_URL / LLM_API_KEY missing (.env)` —
  a provisioning gap on my side, not a regression. I copied `.env` into the repository working
  tree (`Test-Path .env` → `True`), confirmed `git status --short` stayed empty and
  `git check-ignore -v .env` reported `.gitignore:1:.env`, then re-ran the call:

  ```
  $ python src/call_llm.py "hotpot last night cost 350"
  [model] CS5351/DeepSeek-V4-Flash
  [input] hotpot last night cost 350
  [parsed] {'amount': 350, 'category': 'food'}
  [log]   logs/llm_calls.jsonl (appended)
  ```

  Behaviour is unchanged after the refactor, and the model's own vocabulary choice (`food`,
  lowercase, inside the whitelist) is now the only thing standing between a plausible answer and
  a stored record — which is exactly the point of `INV-002`.

**Reflection.** I had specified the *code* rules densely (boundaries, anti-patterns, acceptance
commands) and left the *who does what* part implicit. The code rules held; the gap was an
instruction that described an **action without an actor** — and the agent, quite reasonably,
performed that action. The lesson is not "the agent misbehaved", it is: **an instruction that does
not name the actor will be executed by the agent.** From now on every task sheet names the actor
("I commit; you do not"), and the mechanical layer (role C's `.opencode/permissions.jsonc`, which
sets `"git commit": "deny"`) makes the intent enforceable rather than merely stated.

The second lesson is about verification: I checked "who committed" from `git log` and from the
wording of the messages rather than from the agent's summary — and that is what turned a
suspected violation into a diagnosed ambiguity in about two minutes.

### Follow-up in the same session: the three fixes and Task C

**The instruction.** I pasted the FIX text verbatim (the agent had refused to guess, citing
`AGENTS.md` §1.5 "do not guess" — correct behaviour, and it made me state the fixes precisely
instead of relying on "you know what I mean"):

```
FIX 1 (required) — validate_record must reject non-dict input.
FIX 2 (required) — validate_record discards the running total; return it.
FIX 3 (optional) — no log line when configuration is missing.
Then Task C — src/pipeline.py: order extract (RP-004/RP-001) -> validate_record
(RP-003/005/006); PolicyError.review -> one line in logs/review.jsonl, then re-raise;
LlmTransportError propagates, never retried; no silent try/except; no IO outside logs/.
```

**What it delivered.**

- `validate_record` now starts with `if not isinstance(raw, dict): raise PolicyError(...)`, so a
  JSON array or a bare string is a rejection instead of an `AttributeError`.
- It returns `{"amount", "category", "total"}`, and `test_validate_record_returns_normalised_record`
  was updated to assert `total` (so the test would fail if the total disappeared again).
- The missing-configuration path now writes one log line (`error="config: missing base url or
  key"`) before raising, so "exactly one line per call" also holds when credentials are absent.
- `src/pipeline.py`: `process()` calls `extract()` then `validate_record()`; on
  `PolicyError.review is True` it appends one line to `logs/review.jsonl` and **re-raises**; it
  never imports `requests`, never retries, and has no second, silent `try/except`.
- `pytest test/offline -q` → **36 passed**. End-to-end with a stubbed model:
  `{'amount': 350, 'category': 'food', 'total': 350.0}`, and `"Food"` produced
  `{"amount": 350, "category": "Food", "code": "policy:category", ..., "review": true}`.

**What I checked before accepting it.**

1. no second `try/except` that swallows `PolicyError`;
2. no retry loop (RP-001 and RP-002 both forbid retrying);
3. `pipeline.py` does not import `requests`;
4. the review line goes to `logs/`, nowhere else;
5. its `SCOPE SELF-CHECK` matched `git status --short` line for line.

**One more thing the agent did right.** Its report opened with a question about
`transcripts/60915652-LiuWanyang.md` appearing as modified: it noticed the file had a newer
mtime than its session, stated that the change was not its own, and **declined to touch it**
because `AGENTS.md` §2 makes `transcripts/**` read-only to the agent. That change was mine
(18:04). It did not have to be told; it applied the permission matrix on its own. This is the
first time in the session that the governance file *prevented* something rather than being
enforced by me after the fact.

**Correction to my own record.** Earlier in this entry I had written that the agent "ran
`git commit` on its own". It was wrong to leave it at that: on being challenged, the agent
pointed out that my approval message said *"Commit A and B separately"* without naming the actor,
and that this instruction conflicted with `AGENTS.md` §8. It was right, and I corrected this
transcript rather than defend the accusation. Both commits are kept (their boundaries are
correct); from this point every task sheet names the actor explicitly, and role C's
`.opencode/permissions.jsonc` makes `git commit: deny` mechanical.

**Result.** `src/policy_core.py`, `src/call_llm.py`, `src/pipeline.py` and four smoke tests are
in the working tree, green offline, and verified live once `.env` was provisioned. Open items
reported to the verification role rather than fixed here: the review/log paths are relative to
the current working directory, and a failure to write the review line reports
`code="policy:budget"` even when the original rejection was about the category.

---

## 2026-11-09 · Conformance check against role C's specification, and the evidence fix

**Context.** Before asking for review I re-read `docs/architecture/invariants.md` and compared the
implementation against it **field by field** — Condition, Threshold, Exception, On failure,
Boundary, Evidence — instead of trusting that 36 green tests meant conformance. They do not mean
the same thing.

**What the check produced.**

| Field | INV-001 | INV-002 | INV-003 |
|---|---|---|---|
| Condition | conforms | conforms | conforms |
| Threshold | conforms (two decimals via Decimal) | conforms (exact, case-sensitive) | conforms (`>` not `>=`) |
| Exception | conforms (`PolicyError`) | conforms (+ review) | conforms (+ review) |
| Boundary | `-0.01` not tested separately | conforms | conforms |
| **Evidence** | **nothing written at all** | written to the wrong file, wrong field name | same |

So 36 passing tests, and the Evidence column was still not implemented. The tests proved
behaviour; only the spec comparison proved conformance.

**Root cause.** The call line in `logs/llm_calls.jsonl` is written inside `call_llm.extract()`
**before** validation runs, so it cannot carry `error="policy:amount"`. And two of C's own
documents disagree: the Evidence column says the rejection is logged in `llm_calls.jsonl`, while
RP-004 says every call writes **exactly one** line there.

**What I deliberately did not do.** I did not fix it myself, and I did not edit her document:

1. code must be produced through the agent ("no non-agentic modification");
2. the conflict is between two documents owned by role C, so the choice of resolution is hers,
   not mine. Deciding it silently would have been exactly the mistake I had criticised the agent
   for earlier.

**Decision.** I put three options to her: **A** append an extra line to `llm_calls.jsonl` (breaks
RP-004 literally), **B** record every rejection in `logs/review.jsonl` and rename the field
`code` → `error` (keeps RP-004), **C** restructure so the call line is written after validation
(largest change). She chose **B**. The decision and who owns the document edit are recorded in
`OPENCODE_TASK_03.md`.

**My instruction to the agent.** The sheet, then the approval:

```
APPROVED for Option B, with these confirmations.
1. logs/review.jsonl now carries all policy rejections, including INV-001 (review=false). Confirmed.
2. keep the guarded total computation; for INV-001 the raw amount may be non-numeric, so total
   may be null.
3. use the existing test file; assert one line, error == policy:*, review == false/true/true,
   and that pipeline does not write to logs/llm_calls.jsonl.
4. no `if exc.review:` gate; raise after writing; no requests import; report only, no git.
```

**Agent output (excerpt).** It removed the `if exc.review:` gate, changed the record to
`{"error": exc.code, "amount", "category", "spent", "total", "review": exc.review}`, updated the
docstring to state that `llm_calls.jsonl` is untouched, and added a parametrised test over the
three invariants.

**What I checked before accepting.** No `if exc.review:` left; field renamed rather than
duplicated; `review` taken from `exc.review` instead of hard-coded `True`; `policy_core.py`
untouched; `raise` still there; `pytest` → 39 passed.

**Two weaknesses I recorded instead of fixing.** (1) The new assertion
`captured_log == []` proves little, because `call_llm.extract` was stubbed in that test and could
not have written a line anyway — a stronger test stubs `_post` and lets the real `extract` write.
(2) `_append_review` and `logs/review.jsonl` now carry every rejection, not only the review ones;
the names are debt, deferred so the change stays reviewable. Both are written down for the
verification role rather than quietly patched.

**Reflection.** The Evidence field is the first column to rot, because it does not affect
behaviour: every test passes, the demo looks right, and the audit trail is still missing. Twenty
minutes of field-by-field comparison found a defect that 36 green tests could not, and the fix
required a decision from the specification owner, not from me and not from the agent. The division
of labour that finally worked was: **I read the spec and found the gap; the owner chose the
resolution; the agent wrote the code; I verified the diff.**

---

## 2026-11-10 · Reviewing the team's AI use log — what "not modified" actually means

**Context.** Role A opened a PR that rewrote `docs/ai-use-log.yaml` (his own entries, plus a
reformatting of mine). While reviewing it I found that one of my entries listed `src/__init__.py`
under **both** `files_created` and `files_not_modified`.

**What I claimed.** A file cannot be in two states at once, so the three file lists should be
disjoint. I found three overlaps of that shape: `src/__init__.py` in `files_created` and
`files_not_modified`; `src/call_llm.py` in `files_created` and `files_modified`; and `docs/**` in
`files_not_modified` covering `docs/ai-use-log.yaml`, which the same entry put in `files_modified`.

**Where I was unsure.** My own reading had been: "the file was created and afterwards never
modified, so listing it as unmodified is consistent." I could not decide between that reading and
the disjoint-lists reading, so I put the question to the owner instead of editing his PR:

> "src/__init__.py 同时出现在 files_created 和 files_not_modified 这两个字段内容里了…
> 理论上同一文件不能既'创建'又'未修改'… 我之前想的是——创建了之后没修改所以才这么填的，
> 所以应该按哪个逻辑来呢？"

**The owner's answer.** He defined the field, which is the part I could not derive from the data:

> "这个其实严格来说不是报错，是互斥。Git 里，一次提交里的文件状态只能是'新增 (Added)'或
> '修改 (Modified)'或'未变 (Unchanged)'。你建了 `src/__init__.py`，它这次的状态就是'新增'。"
>
> "`files_not_modified` 这个字段，是用来做'安全声明'（比如声明我没动核心代码），它代表的是
> 那些**本来就存在**且这次没碰的文件。"

So `files_not_modified` is not a free-form negative claim: it is a **safety declaration about
pre-existing files**, and something added in the same session has no standing in it. The three lists
describe three Git states of a single commit and are therefore mutually exclusive by construction.

**Outcome.** The owner accepted the correction ("按 agent 来") and asked for the exchange to be
recorded here, which is this entry.

**What I actually learned.** My finding was about a *field's semantics*, not about a fact.
`git status` cannot tell you whether "created and never modified" should count as unmodified — that
is a convention someone has to own. The reviewer's job is to surface the ambiguity with a concrete
example and hand the definition back to the owner; the owner's job is to define it once so the next
ten entries are mechanical. Writing the rule down (three Git states, mutually exclusive) is what
turns a one-off correction into a schema.

**Follow-up recorded for the team.** A CI check asserting that the three lists are pairwise disjoint
after expanding `**`, and that `date` is a quoted string, would turn all four findings into a gate
instead of a habit. Reported to role E as a Phase 2 item.
