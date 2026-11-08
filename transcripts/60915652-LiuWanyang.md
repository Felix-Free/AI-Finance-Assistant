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
