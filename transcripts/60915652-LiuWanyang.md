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

---

## 2026-11-12 · "Missing usage" has two meanings: no request, versus a request with no data

**Context.** Phase 2 asks role D to supply token-usage evidence, and the owner (role B) computes
`usage_missing_calls` as "actual LLM calls that had no usable usage". To satisfy this, the log has
to distinguish two situations that both look like "a log line without token numbers":

- **no HTTP request was made at all** — e.g. the base URL or key is absent, so the client refuses
  before dialling out;
- **a request was made and came back without usable usage** — transport failure, non-200,
  malformed envelope, or a 200 whose body simply has no `usage`.

**What the agent proposed.** Its plan sent every failure path to `usage_source="missing"`. That is
self-consistent code. It is also wrong for the owner's metric: a config failure would be counted as
a call that had no usage, inflating `usage_missing_calls` and `total_api_calls` with calls that
never happened.

**Where the ambiguity sits.** This is not an implementation bug. "Call" is a word with two
readings — *attempted to call* and *actually called out* — and the plan silently picked one. The
data contract (B's counting rule) picked the other. Nothing in the code could reveal the
disagreement, because both readings compile and pass whatever test the author imagined.

**What I did instead of dictating a fix.** I asked for three designs before any code, and gave the
agent the criteria any design had to meet: exactly one log line per attempt, the four original
field names unchanged, storage untouched, "no request" distinguishable from "request without
usage", and no zero-filling or estimation. Three came back:

| Option | Shape | Rejected for |
|---|---|---|
| 1 | `api_call: true\|false` | same as 3 but an abstract name that collides with "business call" |
| 2 | `phase` enum in {config, transport, protocol, response} | "request made" is decided by **set membership**, so a new request-making phase silently vanishes from the totals; also duplicates `error` |
| **3** | **`request_made: true\|false`** | chosen |

**Why option 3.** One new field, names the physical fact a reader actually needs, orthogonal to
`error` and to `tokens`, and the split is a direct read of one boolean:
`usage_missing_calls = request_made ∧ usage_source == "missing"`. Its residual risk — a future
path setting the flag incorrectly — is shared by all three options, so it is a reason to add a test,
not a reason to buy a costlier enum.

**The guard I added.** One consistency test ties the flag to what actually happened: `request_made`
is false if and only if the config path ran; `gateway` implies three ints; `partial` implies at
least one null and one int; `missing` implies `tokens is None`. A future path that forgets the flag
now fails a test instead of quietly corrupting a metric.

**Transcript note on the working relationship.** The agent was not sloppy; it was *consistent with
a definition I never wrote down*. My job here was not to write the field myself and not to hand it a
finished design, but to state the invariant the design must satisfy, ask for alternatives, and pick
one using public criteria. That is also why this entry records the two rejected options: the reason
they lost is the evidence that the choice was made, not guessed.

---

## 2026-11-12 · Phase 2: persistence, a joinable audit trail, and token evidence

**Context.** Phase 2 asked for three things from role D: a persistence layer that only accepts
validated data, a rejection line that can be joined to its call line, and measurement evidence for
NFR-001/NFR-002. Three task sheets were used (v4 storage + debts, v5.1 usage capture, v6 the
memory-design document), each written from the team template and pasted whole.

**What was delivered.** `src/storage.py` (single write entry `append_validated`, duplicates by
`call_id` refused, `StorageError` on any write failure, parent directory created at write time);
`call_id` threaded from `call_llm` through `pipeline` into both logs and the stored record;
`_append_review` renamed to `_append_rejection` with the original rejection code preserved; the
`-0.01` boundary smoke case; two measurement scripts; and `docs/architecture/memory-design.md`.
`pytest test/offline -q` went from 39 → 105 passing.

**Three things I caught in review, in ascending order of importance.**

1. *A ragged log schema.* The failure paths emitted eight keys while the success path emitted ten:
   `raw` and `parsed` were absent rather than `null`. Every consumer would have needed `.get()`,
   and a `pandas.read_json` would have silently filled columns. I required a single `_line()`
   builder that seeds all ten keys, plus one test asserting `set(line) == TEN` on **every** path,
   not `⊆`.

2. *A word with two meanings.* The plan classified every failure as `usage_source="missing"`. That
   is self-consistent code and wrong for the owner's metric: a configuration failure makes **no**
   HTTP request, so counting it as "a call that lacked usage" inflates `missing_usage_calls`. I did
   not hand over a field name; I asked for three designs and fixed the criteria first (one line per
   attempt, four original names untouched, storage untouched, "no request" distinguishable from
   "request without usage", no zero-filling). The chosen design added `request_made`, which the
   contract owner then approved with a written condition: configuration, parameter and local
   pre-check failures must all be `false`.

3. *A numbering leak.* `memory-design.md` came back with sections numbered `3.1–3.6` — inherited
   from §3 of the task sheet. Correct content, wrong self-numbering: a reader opens the document and
   asks where 1 and 2 went. Small, but it is the kind of defect that survives every content review
   because nobody reads headings as a reader would.

**The practice worth keeping.** For that last fix the agent did not simply say "renumbered". It
copied the file to `/tmp`, ran a script whose every replacement was guarded by
`assert text.count(old) == 1`, then ran `diff` and showed that exactly seven lines changed — six
headings and one cross-reference — with everything else byte-identical. That is the difference
between *"I changed it, trust me"* and *"here is the proof that only the intended bytes moved"*.
It is also cheap to demand: one command in the task sheet, and the reviewer stops having to
re-read 152 lines to find the two that were supposed to change.

**What this says about the division of labour.** Every defect above was found by comparing the
output against a written contract, not by reading for style. The agent's code was internally
consistent in all three cases; the gap was always between what the code claimed and what an owner
had actually specified. Two of the three needed an owner's decision, and one needed nothing more
than an `assert` before `replace`. That is the whole job: keep the contract written down, and make
the agent prove its edits.


---

## 2026-11-13 · Two measurement defects, found by running the thing once

**Context.** The first real measurement run produced data for NFR-002 and then died. Both events —
the data and the death — were more useful than a clean run would have been, because each exposed a
defect that no amount of reading the code would have surfaced.

**Defect A — one transport failure destroyed the whole latency sample.** The gateway returned
`Read timed out (read timeout=30)` on a single call. `measure_latency` let `LlmTransportError`
propagate, so the loop ended at that attempt; the samples already written to
`logs/llm_calls.jsonl` survived, the rest were never taken. The log shows it plainly: one
`usage_source="gateway"` row, then one `request_made=true, usage_source="missing"` row, then
nothing.

**Defect B — the token sample had no distribution.** Every successful call returned
`tokens = {input: 91, output: 12, total: 103}`. The probe sentence is byte-identical and
`temperature: 0`, so the prompt, the completion and therefore the token count are identical by
construction. Thirteen rows with one distinct value cannot support a percentile, and the owner of
NFR-002 would be right to ask why every row is the same.

**What I did instead of dictating a fix.** Both defects are design questions with several defensible
answers, so I asked for three designs each, against a criteria list fixed in advance: the ten-key log
schema is untouched, no estimation or zero-filling, the frozen report format is unchanged, latency is
measured on a fixed input while token cost is measured across varied inputs, and the tooling must
stay offline-testable. Six designs came back.

| Design | Verdict | Why |
|---|---|---|
| A1 count the failure and continue | **chosen** | smallest change; prints `(n=…)` on the same line as each percentile, so a reviewer sees the sample size without opening the code |
| A2 circuit breaker after K consecutive failures | rejected | needs a `K` we cannot justify from one data point, and truncates runs that would have succeeded |
| A3 sampler writes every attempt, separate `report_latency.py` | rejected for now | creates a **second evidence schema** for `logs/latency.jsonl`; the contract owner has approved no such schema |
| B1 second script with a built-in corpus | **chosen** | produces a genuine distribution with no new data file and no new owner |
| B2 one script, two modes | rejected | one command carrying two invariants; a reviewer cannot tell which mode produced a row |
| B3 external corpus file | deferred | adds a repository file whose content *is* evidence, and its owner (B or D) is unsettled |

**The four amendments I added.** The chosen designs were sound but incomplete, and three of the four
gaps were things the proposal had not considered at all:

1. exit code **2** when no sample succeeded, so CI can distinguish "ran and produced nothing" from
   "crashed";
2. an explicit `low_confidence` line when `0 < ok < 5` — printing `(n=3)` is honest, but a reader
   skimming will not notice three is nearly nothing;
3. catch **`JSONDecodeError` as well as `LlmTransportError`** — a non-JSON answer is a failed
   sample, not the end of the run;
4. the failure tally records **kind and count only** — never a response body, never a raw exception
   `repr`. This one is not about measurement at all: `str(exc)` for a transport error can contain
   the full request URL, which can contain a credential. We settled "no secrets in logs" in Phase 1,
   and a new summary line is exactly where that rule would have been broken by accident.

**Reflection.** Both defects were invisible in review and obvious in one run. The code was correct
against its own intentions: the loop really did measure latency, the probe really did produce real
`usage` values. What was wrong was the *measurement design* — a tool that dies on the first failure,
and a sample of size twenty drawn from one point. That is a category of defect that tests do not
find, because the tests stub the very thing that misbehaves; it only appears when the tool meets a
flaky network. The fix is not "write more tests" but "run it once for real, and treat the first
failure as data".

Second reflection, about the working relationship: the agent's proposal was genuinely good — it
listed its own risks, named two invalid alternatives unprompted, and recommended the cheapest
option rather than the most impressive one. It still missed the secrets exposure, because that rule
lives in our governance documents rather than in the measurement problem. The division that worked:
it designed, I supplied the constraints it could not know, and the amendments were the part that
belongs to the person who owns the project's rules.


---

## 2026-11-14 · A guard test that contradicted itself, and an agent that stopped

**Context.** The reviewer's second blocking finding was that `report_tokens.LOG_PATH` was still
cwd-relative and that the guard test never checked that file. Four guards were specified: a manifest of
five constants, an absolute-path assertion, a scan for relative path literals, and a drift assertion
that the duplicated `logs/llm_calls.jsonl` string in two modules stays equal. A fifth guard (call it
B5) was added at the last moment: "the five constants must point at five distinct files."

**The contradiction.** B5 as written is false by construction. `report_tokens` is a *reader* of the
call log, so `report_tokens.LOG_PATH == call_llm.LOG_PATH` is the intended state — and the drift
assertion (B4) says exactly that. B5 demanded the opposite: five distinct files. The suite therefore
had one red test no matter how the code was written: `assert 4 == 5`.

**What the agent did.** It stopped, quoted the failing assertion, named the two options that were
actually available, and recommended the one that preserved the intent: scope B5 to the four *owning*
constants (each owner must own a distinct file) and keep the deliberate sharing of the call log
asserted by B4. It also pointed out that dropping B4 instead would leave the string-drift case
unguarded — i.e. it evaluated the consequence of each option rather than listing them.

**Why this is the right failure mode.** A contradictory specification has exactly two honest
resolutions: stop and fix the specification, or silently pick whichever reading makes the suite green.
The second is how a guard test becomes decoration: someone "simplifies" the assertion until it passes,
and the property it was meant to protect is gone while the test count still goes up. The failure here
was mine — I wrote B5 in one sentence without checking it against the guard I had written two
paragraphs earlier.

**What I changed in the brief.** B5 now reads: the four owning constants name four distinct files;
`report_tokens.LOG_PATH` equals `call_llm.LOG_PATH` by design. The guard-removal table was extended so
the two guards are shown to be independent: pointing `report_tokens` at `logs/latency.jsonl` must fail
B4 and leave B5 green; pointing `storage.DATA_PATH` at `logs/review.jsonl` must fail B5 and leave B4
green.

**Reflection.** The most useful thing an agent can do with an inconsistent instruction is refuse to
satisfy it. That only works if the brief says so explicitly — and ours does: "stop and ask, do not
guess" (`AGENTS.md §2`), and the task-sheet template forbids writing code that merely makes the suite
pass. The reviewer will see a test file with one more assertion than the brief originally had; what they
cannot see is that the alternative was a green suite that proved nothing.

**Addendum (2026-11-14 02:00).** When this guard was implemented, the first version of the
relative-literal scan was **vacuous**: the pattern was built with `%r`, so the needles looked like
`pathlib.Path(''logs'` and matched nothing. The test was green and proved nothing. It was caught only
because the task sheet demanded guard-removal evidence: reverting the anchor still left the scan green,
which is impossible if the scan works. The pattern was rebuilt by concatenating literal text, and every
guard-removal row was re-run. Two lessons: a passing test is not evidence until you have seen it fail,
and the cheapest way to make a test fail on demand is to write down, in advance, the mutation that
should break it.
