# AI-Finance-Assistant
An AI-powered personal finance assistant that helps users track spending, understand their budgets, and receive actionable financial guidance — with a hard safety boundary between what the model *says* and what may ever be *persisted*.

## Architecture & Safety Boundary

The system is intentionally split into two halves:

- **Advisory layer** — the LLM. It may produce suggestions, classifications, and natural language advice. It is treated as untrusted input.
- **Deterministic Safety Boundary** — `src/policy_core.py`. Every AI output must pass through this module **before** it is written to disk. No advisory result may reach storage without it.

`src/policy_core.py` runs rule-based checks (budget invariants, schema/total-spend limits, and related constraints) written as code, not as prompt text. The model is never asked to enforce a rule; enforcement lives in the deterministic layer.

The boundary follows a **fail-closed** principle:

- If a check fails, the output is rejected.
- If the call cannot be logged, the result must not be used.
- If validation is ambiguous or errors out, the safe default is *deny*, never *allow*.

All model access is funnelled through `src/call_llm.py`, and each call appends exactly one line to `logs/llm_calls.jsonl` with the fields `input`, `raw`, `parsed`, `error`.

## Project Structure

```text
src/            Application code, including the LLM gateway (call_llm.py)
                and the deterministic safety layer (policy_core.py).
test/           Test suites.
  offline/      Deterministic tests; must not require network access.
  live/         Tests that call the model gateway.
docs/           Requirements, architecture, and code-governance documentation.
.github/        CI/CD workflows and blocking quality gates.
```

## How to Run Tests

```bash
# Offline (deterministic, no network)
pytest test/offline

# Live (calls the model gateway)
pytest test/live

# Full suite
pytest
```

## CI/CD & Blocking Gates

Merges are guarded by mandatory, blocking gates. A failure in any gate blocks the change.

- **Offline tests** — deterministic suite must pass.
- **Schema Gate** — structured AI output must conform to its declared schema.
- **AI-use log gate** — every model call must be logged with the required fields.
- **...plus the remaining required gates** (type/style checks, secret scanning, and the deterministic-boundary check).

**Phasing:** Phase 1 establishes the project skeleton and the core modules. Phase 2 finalizes all **six** required gates, wiring each one as a blocking check before merge.
