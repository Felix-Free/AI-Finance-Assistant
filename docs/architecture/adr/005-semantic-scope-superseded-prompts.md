# ADR-005 — Gate 4 replays only the prompts that can still run

- **Status:** Proposed (pending team review)
- **Owner:** role E (CI gates) · reviewed by B (prompts) and C (security boundary)
- **Date:** 2026-11-22
- **Related:** `.github/ci_checks.py::classify_semantic_paths`; `test/live/test_live_model.py`;
  `test/offline/test_ci_regressions.py::test_semantic_scope_replays_only_current_prompts`;
  `prompts/prompt_v1.0.yaml`, `prompts/prompt_v1.1.yaml`; D9 in the project brief.

> **Reading this document.** The decision is implemented in the same pull request that adds this
> file. Acceptance is not implied by the code existing.

---

## 1. Context

Gate 4 replays every `*.yaml` under `prompts/` through `test/live/test_live_model.py`. The live
fixture reads the **top-level** `system_prompt` of each file and runs the same five cases
(four spending sentences plus one non-expense sentence) against the real gateway.

D9 of the brief requires the repository to carry versioned runtime prompts, which in practice means
at least `prompts/prompt_v1.0.yaml` and `prompts/prompt_v1.1.yaml`. The two requirements collide:

- v1.0 has no `{"error": "not_a_record"}` rule, because that convention was introduced in v1.1.
- Replaying v1.0 therefore fails the non-expense case.
- The gate would block every pull request that adds the archived v1.0 file, for a prompt that
  production no longer sends.

The archive was temporarily kept outside `prompts/` (in `docs/architecture/prompt-history/`) to
avoid this. That keeps the gate honest but leaves the repository structure short of the D9 tree.

## 2. Decision

A prompt file is replayed **unless it declares `status: superseded`**.

- The check lives in `.github/ci_checks.py::_is_replayable_prompt` and is applied where the
  runtime-prompt list is built, so the semantic-scope job and Gate 4 agree on the same list.
- Only an explicit, lowercase-insensitive `superseded` opts a file out. A file with no `status`
  key, a non-string `status`, an unparseable file or a missing blob stays **replayable**, so a
  malformed prompt still fails loudly instead of silently disappearing from the evaluation.
- `status: superseded` is documentation, not enforcement: the prompt files remain readable and
  the archive is still part of the repository.

With the rule in place, `prompts/prompt_v1.0.yaml` can live at the D9 location, marked
`status: superseded`, and the archived copy under `docs/` is deleted.

## 3. Consequences

- Gate 4 evaluates exactly what production can send today, which is what the gate is for.
- Adding a new candidate prompt requires no marker at all: the default is "replay it".
- Retiring a prompt becomes a one-line change that is visible in review (`status: superseded`).
- Risk: someone could mark a *bad* current prompt as `superseded` to bypass the gate. Mitigation:
  the marker is reviewable, appears in the diff, and the prompt history file that names the current
  version must change in the same pull request; a superseded prompt still has to exist in history.
- The live test still fails closed on a prompt file with no top-level `system_prompt` — the shape
  bug found in PR #28 stays caught.

## 4. Alternatives considered

- **Keep the archive outside `prompts/` (status quo).** Rejected: it departs from the required
  repository structure for a reason that only exists because of an implementation detail of the
  gate.
- **Teach the live test to read a `prompts:` history list instead.** Rejected: it moves the
  decision into the test, so the gate's scope and the test's behaviour can drift apart again.
- **Replay only the newest file by filename.** Rejected: filenames are not a contract; a candidate
  prompt with a different name would silently stop being evaluated.
- **Skip any prompt that is not the production `SYSTEM_PROMPT`.** Rejected: candidates would never
  be evaluated before they are promoted, which is the opposite of the intent.

## 5. Re-evaluation triggers

Revisit this decision if any of the following holds:

- A prompt is superseded while still being the production prompt.
- The live evaluation gains per-prompt cases (the current five cases are prompt-set agnostic).
- `prompts/` starts holding non-prompt YAML files.
- The semantic-scope job and Gate 4 stop consuming the same list.
