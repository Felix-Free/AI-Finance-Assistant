"""Live model tests (role E): the production extract against the real gateway.

This is a live extraction semantic score with test-specific category aliases: the
expected categories below are accepted string sets, not the strict production
whitelist. Each test calls ``src.call_llm.extract`` directly and stops before
production validation and storage; it does not exercise ``policy_core``, whose
strict category check independently applies in the production pipeline. Nothing is
persisted. ``SEMANTIC_PROMPT_FILES`` is a JSON array of runtime prompt YAML paths:
absent/empty runs the built-in prompt, a non-empty array replays each file via
``system_prompt`` and records its SHA-256.
Missing config, bad JSON/YAML/field or a failed call is ``pytest.fail`` (never a
skip). Raw replies, values and exception text are never printed.
"""
from __future__ import annotations

import hashlib
import json
import os

import pytest

from src import call_llm

pytestmark = pytest.mark.live

PROMPT_FILES_ENV = "SEMANTIC_PROMPT_FILES"

SPENDING_CASES = [
    ("I paid 35.50 for lunch.", 35.50, ("food",)),
    ("My bus fare cost 12.", 12, ("transport", "transportation")),
    ("I spent 90 on groceries.", 90, ("food", "groceries")),
    ("The electricity bill was 280.", 280, ("utilities",)),
]

NON_EXPENSE_INPUT = "Please remind me to take an umbrella tomorrow."
PRIVATE_KEY = "__call_id__"


def pytest_generate_tests(metafunc):
    """Drive the prompt selection from SEMANTIC_PROMPT_FILES."""
    if "runtime_prompt" not in metafunc.fixturenames:
        return
    try:
        paths = json.loads(os.environ.get(PROMPT_FILES_ENV, "[]") or "[]")
    except ValueError:
        pytest.fail("%s is not valid JSON" % PROMPT_FILES_ENV)
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        pytest.fail("%s must be a JSON array of paths" % PROMPT_FILES_ENV)
    metafunc.parametrize("runtime_prompt", paths or [None], indirect=True)


@pytest.fixture
def runtime_prompt(request, tmp_path, monkeypatch):
    """Isolate the call log, apply the selected prompt and return the extractor."""
    if not call_llm.BASE_URL or not call_llm.API_KEY:
        pytest.fail("LLM_BASE_URL / LLM_API_KEY are not configured")
    monkeypatch.setattr(call_llm, "LOG_PATH", tmp_path / "llm_calls.jsonl")

    path = request.param
    if path is not None:
        monkeypatch.setattr(call_llm, "SYSTEM_PROMPT", _system_prompt(path, tmp_path))

    def _extract(text):
        try:
            return call_llm.extract(text)
        except (call_llm.LlmTransportError, ValueError) as exc:
            pytest.fail("extract failed (%s)" % type(exc).__name__)
    return _extract


def _system_prompt(path, evidence_dir):
    """Read a runtime prompt YAML, print its SHA-256, return ``system_prompt``."""
    pyyaml = pytest.importorskip("yaml")
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        pytest.fail("prompt file is not readable")
    digest = hashlib.sha256(data).hexdigest()
    print("runtime prompt sha256=%s" % digest)
    try:
        document = pyyaml.safe_load(data)
    except pyyaml.YAMLError:
        pytest.fail("prompt file is not valid YAML")
    if not isinstance(document, dict):
        pytest.fail("prompt file must be a YAML mapping")
    prompt = document.get("system_prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        pytest.fail("prompt file has no non-empty system_prompt")
    return prompt


def _business(result):
    assert isinstance(result, dict), "extract must return a JSON object"
    return {k: v for k, v in result.items() if k != PRIVATE_KEY}


def _check_spending(amount, allowed_categories, result):
    payload = _business(result)
    assert set(payload) == {"amount", "category"}, "expected amount and category only"
    got = payload["amount"]
    assert isinstance(got, (int, float)) and not isinstance(got, bool), "amount must be a number"
    assert got == amount, "amount mismatch"
    assert payload["category"] in allowed_categories, "category mismatch"


@pytest.mark.parametrize("text,amount,allowed_categories", SPENDING_CASES)
def test_spending_amount_and_category(runtime_prompt, text, amount, allowed_categories):
    """Four fixed spending inputs: exact amount and an accepted category per prompt set."""
    _check_spending(amount, allowed_categories, runtime_prompt(text))


def test_non_expense_is_not_a_record(runtime_prompt):
    """A non-spending sentence yields not_a_record, not a spending record."""
    payload = _business(runtime_prompt(NON_EXPENSE_INPUT))
    assert "amount" not in payload and "category" not in payload, "must not be a record"
    assert payload == {"error": "not_a_record"}, "expected not_a_record"
