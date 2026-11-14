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

The live suite needs a real gateway: set `LLM_BASE_URL` and `LLM_API_KEY` (and optionally `LLM_MODEL`, defaulting to `src/call_llm.py::MODEL`).

## CI/CD & Blocking Gates

`.github/workflows/ci.yml` runs six named PR jobs; `branch-ci.yml` runs static checks and offline tests on every push.

- **`test-approval-loop`** — Gate 1: verifies a real human, non-author, member approval on a test-first commit.
- **`static-analysis`** — Gate 2: ruff, mypy, pip check, secret scan, entry-point/API/permission/ADR checks.
- **`schema-validation`** — Gate 3: strict YAML + Draft 2020-12 schema for docs/req/requirements.yaml.
- **`semantic-eval`** — Gate 4: live semantic evaluation; `needs:` Gate 1 and runs only when Gate 1 reports a semantic change. Requires the protected `semantic-eval` environment with `LLM_BASE_URL` (var), `LLM_API_KEY` (secret) and optional `LLM_MODEL`.
- **`offline-regression`** — Gate 5: full offline suite.
- **`ai-use-log`** — Gate 6: append-only AI-use development sessions (a PR-level record, not the runtime `logs/llm_calls.jsonl`).

**Pending:** these checks are not yet set as required branch protection rules, and no failing PR has yet been shown to be blocked by them.
