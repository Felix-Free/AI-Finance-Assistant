"""The System Prompt must name the closed category vocabulary that policy_core enforces.

Rules are enforced by code (INV-002 / policy_core.CATEGORY_WHITELIST); this file
only locks the prompt text to that vocabulary so an added category fails loudly
instead of drifting (the drift that produced "transportation"/"groceries").
"""
from src.call_llm import SYSTEM_PROMPT
from src.policy_core import CATEGORY_WHITELIST


def test_system_prompt_lists_every_whitelisted_category():
    for category in CATEGORY_WHITELIST:
        assert category in SYSTEM_PROMPT, category


def test_system_prompt_forbids_inventing_categories():
    assert "Do not invent new categories" in SYSTEM_PROMPT


def test_system_prompt_keeps_the_not_a_record_branch():
    assert "not_a_record" in SYSTEM_PROMPT


def test_system_prompt_contains_the_exact_constraint_sentence():
    sentence = (
        "The category MUST be strictly chosen from this exact list: "
        "[food, transport, shopping, entertainment, housing, utilities, health, other]. "
        "Do not invent new categories."
    )
    assert sentence in SYSTEM_PROMPT
