# Runtime Policy Catalog (owner: role C)

> Purpose: the deterministic runtime policies that govern *how* the application degrades
> when something goes wrong — a bad model response, a transport failure, a rejected
> record, or an unwritable log. Distinct from `invariants.md`, which defines the business
> rules that must never be violated.
>
> Status: **Phase 1 · C-Security (transcript 60339160); extended in Phase 2 (§5);
> re-structured in Phase 3 (§2, §6).**
> Role C defines the trigger, action and degradation; role D implements; role E verifies.
> Phase 1 policy ids RP-001..RP-006 are retained. Phase 2 clarifies RP-001/002 against
> D's implemented failure classification and adds **RP-007 (storage boundary failure)**
> plus the `call_id`, token, storage-failure and NFR-006 evidence contracts. Phase 3 keeps
> every Phase 1/Phase 2 statement, restates each policy in the same seven-field structure
> (Trigger / Action / Execution order / State-change guarantee / Evidence and logging /
> Implementation seam / Test-evidence status), and tags each field with its provenance.

### Provenance tags (Phase 3)

Every sub-field below carries one of these tags so a reader can tell *how far* a claim is
backed on the current branch:

| Tag | Meaning |
|---|---|
| `code-confirmed` | Verified by reading the code that is **identical to `origin/main`** on this branch (`src/` and `test/` are byte-identical to `origin/main` `6997cef`; `git diff origin/main -- src test` is empty). |
| `doc-only (unmerged)` | Defined here as the contract, but the implementing code lives only on an **unmerged** D branch; it is **not present** on this branch or on `origin/main`. |
| `pending D` | Behaviour the implementation must provide but that C has **not** yet confirmed with D; not asserted as implemented. |

> **Branch reality (read this before RP-007).** This branch and `origin/main` contain only
> `src/call_llm.py`, `src/policy_core.py`, `src/pipeline.py` (plus `src/__init__.py`).
> There is **no `src/storage.py`** on this branch. Any sentence in this catalog that names
> `src/storage.py`, a stored `data/records.jsonl`, `call_id` / `request_id` / `session_id`,
> `tokens` / `usage_source` / `request_made`, or `expected_spent` describes an **unmerged
> design**, not code you can run here. Those sentences are retained for history and are
> tagged `doc-only (unmerged)` or `pending D`; they must not be read as implemented.

---
## 1. Action vocabulary

| Action | Meaning |
|---|---|
| `accept` | record passes all invariants; may affect stored data |
| `reject` | record is discarded; stored data unchanged |
| `REVIEW` | record is rejected but flagged for human inspection (never auto-applied) |
| `retry` | the call may be repeated, bounded; never on an invariant violation |
| `quarantine` | record is set aside for audit but cannot be used to change state |

A rejected record must never partially affect normal business state or storage writes:
validation happens **before** any write to normal business data or storage
(`structural-constraints.md §4`). Writing the raw model-output audit line to
`logs/llm_calls.jsonl` happens **before** policy validation; this is intentional audit
logging and is **not** a business-state mutation, so it is out of scope for this rule.

---

## 2. Policies

> **Structure (Phase 3).** Each policy is listed with the same seven fields. The normative
> Phase 1/Phase 2 text is preserved inside those fields; each field is tagged with its
> provenance (`code-confirmed` / `doc-only (unmerged)` / `pending D`) so branch reality is
> explicit. When a field mixes provenances, the mixed parts are called out inline.

### RP-001 — Model returns invalid JSON

- **Trigger** — `code-confirmed`: the model's content cannot be parsed by `json.loads` (invalid JSON syntax). `src/call_llm.py::extract` calls `json.loads(raw)` at `src/call_llm.py:149`.
- **Action** — `code-confirmed`: surface `JSONDecodeError`; do not retry. `extract` re-raises the `JSONDecodeError` (`src/call_llm.py:148-154`).
- **Execution order** — `code-confirmed`: parse attempt → on failure, append one call-log line → re-raise. No invariant check runs for non-JSON content.
- **State-change guarantee** — `code-confirmed`: no record is produced; no `review.jsonl` line; on this branch nothing is persisted (there is no storage write path).
- **Evidence and logging** — `code-confirmed` (partial): one `logs/llm_calls.jsonl` line `{input, raw, parsed=null, error="not_json"}` is written (`src/call_llm.py:152-153`). This path **does** emit all four required fields. The "four fields on every path" guarantee is a separate RP-004 gap (see RP-004).
- **Implementation seam** — `code-confirmed`: `src/call_llm.py::extract` (`json.loads` block).
- **Test-evidence status** — `code-confirmed`: covered by `test/offline/test_pipeline_seam.py::test_seam_non_json_is_logged_then_reraised` (asserts one line and `error=="not_json"`).

### RP-002 — Model-client configuration / transport / response-protocol failure

- **Trigger** — `code-confirmed`: missing base URL or API key before HTTP (`src/call_llm.py:123`); network error, timeout, auth failure, non-200 status (`src/call_llm.py:75-83`), or an HTTP 200 response whose envelope is not valid JSON, lacks `choices[0].message.content`, or has a non-string `content` (`src/call_llm.py:85-102`).
- **Action** — `code-confirmed`: surface `LlmTransportError`; do not persist anything.
- **Execution order** — `code-confirmed`: configuration check first (before HTTP); otherwise attempt HTTP once, parse the envelope, then classify. No automatic retry for configuration, transport, HTTP-status or response-envelope failure — `extract` makes at most one HTTP attempt per invocation and propagates the failure after writing its call log when that log is writable.
- **State-change guarantee** — `code-confirmed`: distinct from a policy rejection so tests can tell "correctly refused" from "crashed" (`structural-constraints.md §4`). No record is produced.
- **Evidence and logging** — mixed: `code-confirmed` — on this branch the call-log line is written but **not** with the full field set: the configuration-failure path writes only `{input, error="config: missing base url or key"}` (`src/call_llm.py:124`, no `raw`/`parsed`), and the HTTP-attempts failure path writes `{input, error=..., [body]}` (`src/call_llm.py:140-145`, no `raw`/`parsed`). The Phase 2 fields `request_made`, `tokens`, `raw`, `parsed=null` on these paths are **`doc-only (unmerged)`** and **not** emitted on this branch.
- **Implementation seam** — `code-confirmed`: `src/call_llm.py::_post`, `src/call_llm.py::extract`.
- **Test-evidence status** — `code-confirmed`: `test_seam_transport_error_logs_once`, `test_config_error_logs_once`, `test_post_raises_on_malformed_envelope`. (These assert one line and the raised error; they do not assert a full four-field schema.)

### RP-003 — Invariant violation

- **Trigger** — `code-confirmed`: any of `C-INV-001`, `C-INV-002`, `C-INV-003` fails, raised by `src/policy_core.py::validate_record` → `enforce_amount`/`enforce_category`/`enforce_budget`.
- **Action** — `code-confirmed`: `reject`; raise `PolicyError`.
- **Execution order** — `code-confirmed`: `pipeline.process` calls `call_llm.extract` → `policy_core.validate_record` (amount → category → budget); on `PolicyError`, append one `logs/review.jsonl` line, then re-raise (`src/pipeline.py:49-66`).
- **State-change guarantee** — `code-confirmed`: validation runs before any write to normal business data or storage — that is the state this guarantee covers; on this branch there is no storage write, so the record cannot be applied. The raw model-output audit line is written to `logs/llm_calls.jsonl` **before** policy validation by design (in `call_llm.extract`); that audit logging is not a business-state mutation and is not what this guarantee governs. `C-INV-002` and `C-INV-003` flag `REVIEW`; `C-INV-001` does not.
- **Evidence and logging** — `code-confirmed` (partial): one `logs/review.jsonl` line with `{error="policy:<subject>", amount, category, spent, total, review}` (`src/pipeline.py:58-65`). The Phase 2 wording "carrying the relevant `call_id` … and its `request_id`" is **`doc-only (unmerged)`**: this branch's review line has **no** `call_id`/`request_id` (the test asserts the exact key set `{error, amount, category, spent, total, review}`).
- **Implementation seam** — `code-confirmed`: `src/policy_core.py::validate_record`; `src/pipeline.py::process`, `_append_review`.
- **Test-evidence status** — `code-confirmed`: `test_policy_core_smoke.py::test_validate_record_stops_at_first_failure`, `test_validate_record_rejects_non_dict`; `test_pipeline_seam.py::test_policy_rejection_writes_one_review_line` (three invariants). Review-write-failure behaviour is untested (see RP-004/RP-007).

### RP-004 — Logging integrity (fail-closed)

- **Trigger** — mixed: `code-confirmed` that the per-call audit line cannot be written (`_append_log` `OSError` → `LlmTransportError`, `src/call_llm.py:45-52`), and that the four required fields (`input`, `raw`, `parsed`, `error`) are **not consistently emitted** (see Evidence). `doc-only (unmerged)`/"would produce zero or more than one line, or the fields are renamed/dropped" — the one-line-per-attempt guarantee and field-name protection are contract statements, not separately enforced here.
- **Action** — `code-confirmed`: the result of a call whose log cannot be written **must not be used** — `_append_log` raises `LlmTransportError` and `extract` propagates it, so the result is never returned. Effectively `reject`.
- **Execution order** — `code-confirmed`: log write happens **before** any return or re-raise on each path (`src/call_llm.py:124, 145, 152, 156`).
- **State-change guarantee** — `code-confirmed`: an unwritable call log prevents the result from being returned; no unlogged result can reach a caller (and there is no storage on this branch).
- **Evidence and logging** — **`code-confirmed` gap (D-dependent):** the three paths do **not** emit the same four fields on this branch:
  - success path writes `{input, raw, parsed}` and **omits `error`** (`src/call_llm.py:156`);
  - configuration-failure path writes `{input, error}` and **omits `raw`, `parsed`** (`src/call_llm.py:124`);
  - transport/HTTP/protocol-failure path writes `{input, error[, body]}` and **omits `raw`, `parsed`** (`src/call_llm.py:140-145`).

  So RP-004's "four required fields on every path" is **not satisfied** by the current code. This is recorded as a **D-dependent implementation gap, not a completed invariant.** The Phase 2 statement that the four fields are "never renamed or removed" and that Phase 2 fields (`call_id`, `tokens`, `session_id`, `request_id`, `usage_source`, `request_made`) are additive is **`doc-only (unmerged)`** — none of those fields exist on this branch.
- **Implementation seam** — `code-confirmed`: `src/call_llm.py::_append_log`; call sites in `extract`.
- **Test-evidence status** — mixed: the fail-closed `OSError`→`LlmTransportError` branch is **not exercised by any test** (`# pragma: no cover`, `src/call_llm.py:51`); the field-schema gap has no test. `test-evidence: none` for both. Do **not** cite the passing smoke suite as proof of fail-closed behaviour.

> Note: `call_llm.py::_append_log` already implements the fail-closed write
> (`AGENTS.md §3`, `structural-constraints.md §5`). RP-004 records it as a policy and
> tells D/E what must stay true when the module is extended.

> **Appended fields (Phase 2).** The original four fields — `input`, `raw`, `parsed`,
> `error` — are never renamed or removed. The Phase 2 fields are **additive**:
> `call_id`, `tokens`, `session_id`, `request_id`, `usage_source`, `request_made`. A
> reader that ignores them still sees the four original fields unchanged.
> *Provenance:* this additive-field contract is `doc-only (unmerged)`; those fields are
> absent on this branch, and even the original four are not consistently emitted (see the
> Evidence field above).

### RP-005 — Budget exceeded (guard for C-INV-003)

- **Trigger** — `code-confirmed`: accepted total + new amount > `budget_limit` (`src/policy_core.py::enforce_budget`, strictly greater; equality allowed).
- **Action** — `code-confirmed`: `reject` + `REVIEW` (`PolicyError(code="policy:budget", review=True)`, `src/policy_core.py:84-87`).
- **Execution order** — `code-confirmed`: after amount/category pass, `enforce_budget` runs; a failure produces one `logs/review.jsonl` line then re-raises.
- **State-change guarantee** — `code-confirmed`: the previous total is authoritative; the new record is never applied (no storage write on this branch).
- **Evidence and logging** — `code-confirmed` (partial): `error="policy:budget"` with amount and running total in `logs/review.jsonl`. The "carrying the relevant `call_id` … `request_id`" wording is **`doc-only (unmerged)`** (no such fields on this branch).
- **Implementation seam** — `code-confirmed`: `src/policy_core.py::enforce_budget`; `src/pipeline.py::process`.
- **Test-evidence status** — `code-confirmed`: `test_policy_core_smoke.py::test_inv003_equality_is_allowed`, `test_inv003_over_budget_rejected_with_review`; `test_policy_rejection_writes_one_review_line[inv003-budget]`.

### RP-006 — Category out of vocabulary (guard for C-INV-002)

- **Trigger** — `code-confirmed`: category not in the closed whitelist (`src/policy_core.py::CATEGORY_WHITELIST`, case-sensitive exact match).
- **Action** — `code-confirmed`: `reject` + `REVIEW` (`PolicyError(code="policy:category", review=True)`).
- **Execution order** — `code-confirmed`: after amount passes, `enforce_category` runs; a failure produces one `logs/review.jsonl` line then re-raises.
- **State-change guarantee** — `code-confirmed`: never coerce, never fuzzy-match, never ask the model to fix it; the record is discarded (no storage write on this branch).
- **Evidence and logging** — `code-confirmed` (partial): `error="policy:category"` with the rejected value in `logs/review.jsonl`. The "carrying the relevant `call_id` … `request_id`" wording is **`doc-only (unmerged)`**.
- **Implementation seam** — `code-confirmed`: `src/policy_core.py::enforce_category`; `src/pipeline.py::process`.
- **Test-evidence status** — `code-confirmed`: `test_inv002_rejects_out_of_vocabulary`, `test_inv002_accepts_every_whitelisted_category`; `test_policy_rejection_writes_one_review_line[inv002-category]`.

### RP-007 — Storage boundary failure

> **`pending D` — no storage module exists on this branch.** This branch and `origin/main`
> contain no `src/storage.py`, no `data/records.jsonl`, and no `call_id`. Every statement
> below that references storage behaviour describes an **unmerged design** and is *not*
> code you can run on this branch. RP-007 remains a **required policy**; its implementation
> is pending D and is not asserted as implemented anywhere here.

- **Trigger** — `doc-only (unmerged)` / `pending D`: storage rejects a new record's shape or duplicate `call_id`, cannot read existing records (including malformed JSON or a nonnumeric stored amount when computing the current total), or cannot write a validated record (I/O error or unwritable path). The uncaught type/serialization cases recorded from D's branch are required to follow RP-007 but (on that branch) do not currently raise `StorageError`.
- **Action** — `pending D`: raise an **independent `StorageError`**. It is an infrastructure failure, not a rule decision.
- **Execution order** — `pending D`: (read current total → validate → append) is the intended order; it is defined only on D's unmerged branch and is **not** present on this branch.
- **State-change guarantee** — **No partial state** is allowed: the previous stored state remains authoritative (the write either completes or the prior state stands). D must implement this boundary, and E must verify it with a failure-injection test. *Reserved prefix:* `policy:*` is reserved **only** for deterministic policy/rule rejection (RP-003/005/006); a storage failure **must not** be rewritten as `policy:*`.
- **Not a policy rejection** — a storage failure must not create a policy review line (`logs/review.jsonl`).
- **Evidence and logging** — `pending D`: the required failure signal is `StorageError` to the caller; a read or validation failure stops before a new record is appended; a write failure has the separate no-partial-state requirement. The exact storage-failure evidence detail is **not defined** (see below) and must not be invented.
- **Implementation seam** — `doc-only (unmerged)`: `src/storage.py` (absent here). `src/pipeline.py::process` on this branch has **no** storage call.
- **Test-evidence status** — `pending D`: no test on this branch; the storage tests and the skipped `test_evidence_join.py` live only on D's unmerged branch. **No test run on this branch proves RP-007.**

> **Storage failure classification.** Storage read, validation, serialization, and write
> failures must surface as an independent `StorageError`. They are infrastructure
> failures, not policy decisions; they must not be rewritten as `policy:*` or create a
> valid policy-review line.

> **Rejection-evidence write failure.** If writing rejection evidence fails, the operation
> must fail closed, raise `StorageError`, leave normal business data unchanged, and never
> treat a partial review record as valid evidence. RP-007 does not prescribe a separate
> storage-failure log format.

---

## 3. Precedence

1. **Model-client failures (RP-002/001).** Check configuration, then attempt HTTP and
   parse its response envelope, then parse the model's JSON content. A failure stops
   before business validation.
2. **Call-log integrity (RP-004).** Record the classified model-call result before
   returning or raising it. If the required log entry cannot be written, fail closed
   and do not use the result.
3. **Metadata and persisted state.** Attach required system metadata and read the
   authoritative persisted state before business validation. Read failures surface as
   `StorageError`.
4. **Invariants (RP-003/005/006).** Validate business invariants before writing a
   normal record. A rejection produces review evidence; if that evidence cannot be
   written, fail closed with `StorageError`.
5. **Storage append (RP-007).** Structurally validate and append accepted records.
   Storage failures surface as `StorageError` and must never be rewritten as
   `policy:*`. The no-partial-state requirement applies to the append.

After a failure is detected, no later result is accepted or stored.

---

## 4. Definition of done for each policy

- [ ] A test in `test/offline/` exercises the trigger (deterministic, no network).
- [ ] The degradation matches the `Action` column.
- [ ] Where a policy defines log evidence (RP-001/002/003/005/006), the documented line
      and `error` code are verified. For RP-004, verify that a logging failure prevents use
      of the result; RP-007 surfaces `StorageError`, while its separate evidence format is
      pending and must not be treated as a required policy-review line. Also verify that a
      rejected record is not persisted when writing its review evidence fails.

---

## 5. Phase 2 additions

> **Scope.** Phase 2 defines shared contracts for model-call identifiers, logging metadata,
> token accounting, storage failures, and evidence linkage. RP-001 through RP-006 retain
> their existing identifiers. C defines these contracts; D implements them; E verifies them.

### 5.1 Call identifiers

- **Generation.** The system generates one `call_id` for each model-call attempt, including
  attempts that stop before HTTP. The identifier is a 32-character hexadecimal value and
  must not be synthesized or overridden by a caller or by model output.
- **Carriage.** The same `call_id` travels with the decision evidence so that records for
  one attempt can be joined across the relevant evidence stores.
- **Boundary.** System metadata is removed before business-rule validation. Business
  validation must inspect only the model payload and approved request data.
- **Fail-closed interaction.** If the required call log cannot be written, the result is
  unusable; an identifier must not make an unlogged result valid.

### 5.2 LLM call logging

- **Base fields.** `input`, `raw`, `parsed`, and `error` retain their names and meanings.
  Additional metadata must not rename or remove these fields.
- **Additional fields.** The log may include `call_id`, `tokens`, `session_id`,
  `request_id`, `usage_source`, and `request_made` as additive fields.
- **One line per attempt.** A writable log contains exactly one `llm_calls.jsonl` record
  for each model-call attempt, including a configuration failure before HTTP. Policy
  outcomes use `review.jsonl` evidence instead of creating a second call-log line.
- **Secret-safe errors.** Error values use short, stable codes and must not expose raw
  exception messages, response bodies, URLs, credentials, or other sensitive data.

#### 5.2.1 Token accounting

- `tokens` is `null` when no usage was recorded. Otherwise it contains `input`, `output`,
  and `total`; unavailable or invalid counts are represented as `null`.
- Token usage is never estimated or replaced with zero.
- `usage_source` has exactly three values: `gateway`, `partial`, and `missing`.
  `gateway` means all counts are present, `partial` means some counts are present, and
  `missing` means no usable counts were recorded.
- `usage_source` must remain consistent with `tokens`.

#### 5.2.2 Additional metadata

- **`session_id`.** Identifies the process run that produced the call records.
- **`request_id`.** Groups model-call attempts belonging to one user request.
- **`call_id`.** Identifies one model-call attempt and remains the primary evidence-join key.
- **`request_made`.** Is `true` when the HTTP path was attempted and `false` when a local
  configuration failure stopped processing before HTTP. It must not be inferred from error text.
- A derived `not_called` reporting category may group records with `request_made=false`;
  it is not an additional `usage_source` value.

#### 5.2.3 Pre-HTTP local failures

- A missing base URL or API key must stop processing before HTTP while still producing
  exactly one call-log record when logging is available.
- The record uses the same schema as other call attempts. Missing values are `null`,
  `usage_source` is `missing`, `tokens` is `null`, and `request_made` is `false`.

### 5.3 Storage failure is not a policy rejection

- **Trigger.** Storage input validation, duplicate-ID checks, reading persisted records,
  or writing a record fails.
- **Action.** Raise an independent `StorageError`. A storage failure is an infrastructure
  failure, not a business-rule decision.
- **Reserved prefix.** `policy:*` is reserved for deterministic rule rejection. A storage
  failure must never be rewritten as `policy:*`.
- **No partial state.** A failed write must leave the previous stored state authoritative;
  the write either completes or the prior state remains unchanged. D must implement this
  boundary, and E must verify it with failure-injection testing.
- **Evidence.** A storage failure must not create a valid policy-review line. The policy
  does not prescribe a separate storage-failure log format.

### 5.4 Evidence linkage

- **Accepted decision.** The `llm_calls` record and the accepted storage record share the
  same `call_id`.
- **Rejected decision.** The `llm_calls` record and the review-evidence record share the
  same `call_id`; a rejected decision must not create a normal storage record.
- Each decision uses one applicable evidence shape: accepted storage evidence or rejected
  review evidence. It must not produce both for the same decision.
- If writing required evidence fails, the operation fails closed and no result is accepted
  as successful.

### 5.5 Validation and persisted spend

- Persisted cumulative spend is authoritative.
- `expected_spent` is a validation parameter, not a persisted record field.
- `expected_spent` below persisted cumulative spend raises `StorageError`.
- The accepted record must satisfy `total == expected_spent + amount`.
- Equality at the budget limit is allowed; exceeding the limit raises
  `PolicyError(code="policy:budget", review=True)`.
- Rejection evidence preserves the original `policy:*` error code so that the evidence
  agrees with the routing decision.
---

## 6. Phase 3 C audit summary (branch reality)

> Scope: `feat/c-phase3-policy-60339160`. `src/` and `test/` are byte-identical to
> `origin/main` (`6997cef`); `git diff origin/main -- src test` is empty. This section maps
> each policy to *what the code shows* vs *what tests prove* vs *what is unverified*. It
> does not add new policy ids or invariants; no new RP-### was found necessary because no
> new runtime failure path was identified beyond those already catalogued.

| Policy | Code-confirmed on this branch? | Proven by a test on this branch? | Unverified / pending |
|---|---|---|---|
| RP-001 invalid JSON → log + re-raise, no retry | Yes (`extract`) | Yes (`test_seam_non_json_is_logged_then_reraised`) | — |
| RP-002 config/transport/HTTP/envelope → `LlmTransportError`, no retry | Yes (`_post`, `extract`) | Yes (three seam tests) | Error text uses `str(exc)` (D-02, secret-leak risk) |
| RP-003 invariant violation → `PolicyError` | Yes (`validate_record`) | Yes (smoke + seam) | Review-write-failure classification (below) |
| RP-004 fail-closed call log | Yes, fail-closed on `OSError`→`LlmTransportError`; **field schema incomplete** | **No** (OSError branch `# pragma: no cover`; no schema test) | Full four-field emission on all paths (D gap); fail-closed test |
| RP-005 budget exceeded → reject + REVIEW | Yes (`enforce_budget`) | Yes | `call_id`/`request_id` on review line are doc-only |
| RP-006 category out of vocab → reject + REVIEW | Yes (`enforce_category`) | Yes | `call_id`/`request_id` on review line are doc-only |
| RP-007 storage boundary → `StorageError` | **No** (no `src/storage.py` on this branch) | **No** | Entire policy pending D |

**Findings recorded for D (not fixed here, `pending D`):**

1. **Logging-schema gap (RP-004).** Success / config-failure / transport-failure paths do
   not all emit the four required fields `input`, `raw`, `parsed`, `error`
   (`src/call_llm.py:124, 140-145, 156`). Four-field coverage is a requirement, not a met
   invariant. This is a D-dependent implementation gap.
2. **Review-write misclassification (RP-003/RP-007).** `pipeline._append_review` maps a
   review-write `OSError` to `PolicyError(code="policy:budget", review=True)`
   (`src/pipeline.py:27-31`) instead of an independent infrastructure error. An evidence
   write failure must not be reported as a business-rule rejection.
3. **Relative evidence paths.** `LOG_PATH`/`REVIEW_PATH` are working-directory-relative
   (`src/call_llm.py:22`, `src/pipeline.py:18`); not repository-root anchored on this branch.
4. **Valid-JSON-not-object classification (RP-001).** On this branch a JSON array/string/
   number reaches `validate_record` and is rejected as `policy:amount`; the unmerged design
   would raise `StorageError` earlier. Either way it must not become a valid record; the
   classification is left to D to confirm.

**Security principles preserved (explicit):** **No model output may affect normal business
data or storage before passing through `policy_core`; audit logging of raw model output
occurs before policy validation by design.** Prompts are never the enforcement mechanism;
no hidden retry, unsafe default, fuzzy match or silent coercion is introduced by this
catalog; system-generated audit metadata (`call_id`) must never be trusted from model output
(doc-only, since `call_id` is absent on this branch); unlogged/unvalidated/partially written
results fail closed.

---

## 7. Phase 3 D design confirmation — design-confirmed, implementation-unmerged

> **Banner — read first.**
> This section records **D's confirmed target design** from D's reply. It is
> **design-confirmed but implementation-unmerged**. **`src/storage.py` is absent on the current
> C branch** (`feat/c-phase3-policy-60339160`; `src/`/`test/` byte-identical to `origin/main`
> `6997cef`). **None of the behaviour below is `code-confirmed` on this branch.** It must not
> be promoted to code-confirmed here, and the current branch still contains the known
> review-write misclassification (see §6 finding 2 and RP-007) that **this documentation
> update does not fix**.
>
> **D-reported references (not independently verified):** branch `feat/D-phase3-hardening`;
> interim implementation commit `1332483`; log commit `4281ea3`. Labelled
> *D-reported / interim / not independently verified*. The final commit after the concurrency
> fix and ADR-003 is still pending; E's regression results are still pending.

The existing **§6 branch-reality table is preserved unchanged and still governs what the
current branch actually does.** This §7 is the confirmed *target*; §6 is *current reality*.
Where they differ (e.g. review-write failure, logging schema), §6 wins for this branch.

### 7.1 Process path and model boundary (design-confirmed)

- `pipeline.process()` is the **only** business entry point.
- `call_llm.extract()` returns **unvalidated** parsed output and only adds system metadata
  (e.g. `call_id`); it never trusts model content.
- `src/call_llm.py` is the **only** model-network entry point.
- Normal business-data and storage writes happen **only after** `policy_core` validation.

### 7.2 PolicyError vs StorageError boundary (design-confirmed)

- **Storage performs defense-in-depth validation.** Direct storage invariant failures for
  amount / category / budget remain **`PolicyError(policy:*)`**, *not* `StorageError`, so an
  illegal record cannot enter via a future direct caller.
- **Storage I/O, record shape, duplicate `call_id`, arithmetic-consistency, and persistence
  failures raise an independent `StorageError`.**
- `policy:*` stays reserved for deterministic rule rejection; a storage failure must never be
  rewritten as `policy:*`, and an invariant failure must never be reported as `StorageError`.

### 7.3 Review evidence: direct storage vs pipeline (design-confirmed)

- **Direct storage calls do not write review evidence.**
- **Pipeline-originated policy rejection** attempts exactly **one** `logs/review.jsonl`
  line; if that write fails, raise **`StorageError`** and produce no normal data.
- This supersedes the current branch's misclassification (`pipeline._append_review` raising
  `PolicyError(code="policy:budget")`, `src/pipeline.py:27-31`), which remains unfixed pending
  D's implementation.

### 7.4 Persisted spend authority and `expected_spent` (design-confirmed)

- **Persisted storage cumulative spend is authoritative.**
- **`expected_spent` is a validation parameter, not a persisted field.**
- `expected_spent` **below** persisted cumulative spend → **`StorageError`**; a **higher**
  value is allowed and stricter (`total == expected_spent + amount` must hold).
- **Equality at the budget limit is allowed**; **over-budget** raises
  `PolicyError(code="policy:budget", review=True)`.

### 7.5 Fail-closed, no hidden retry (design-confirmed)

- **Hidden retry is forbidden.**
- **No catch-all conversion** may collapse distinct failure classes (config/transport/HTTP/
  envelope vs policy vs storage).

### 7.6 `call_id` semantics (design-confirmed; unverified here)

- `call_id` is **system-generated**, cannot be overridden by model output, and is **removed
  before `policy_core`**.
- `request_id` = one user request; `call_id` = one model call; `session_id` = one process run.
- Evidence joins: accepted `llm_calls.call_id == storage.call_id`; rejected
  `llm_calls.call_id == review.call_id`.
- These are **design-confirmed but remain unverified on the current C branch** (no `call_id`
  here).

### 7.7 Atomicity target (design-confirmed; not implemented/verified)

- Target: **unique temporary file + a file lock** around read/check/write/replace, replacing
  append-mode, so no partial state is ever visible. **Concurrency implementation, the
  concurrency regression, ADR-003, and E's regression evidence remain pending.**

### 7.8 Privacy / redaction (pending, not approved)

- **Unredacted `input` / `raw` logging is NOT approved as the final design.** The four-field
  logging schema is not an approval of unredacted content. `input`/`raw` may contain personal
  financial data.
- Two candidate paths for a later decision: (a) **minimization/redaction before persistence**,
  or (b) an **enforceable synthetic-data-only runtime constraint**.
- `StorageError` messages and evidence logs **must not** contain raw exception strings, URLs,
  HTTP bodies, credentials, or sensitive data; a **safe short policy code** may be retained
  separately if needed.

### 7.9 Whitelist finality (pending B/C)

- The **eight current categories are unchanged**. Final whitelist ownership/finality remains
  **pending B/C confirmation**; **D must not change the whitelist independently.**

### 7.10 What stays pending

Concurrency implementation + regression, ADR-003, final commit, final merge, E's reproducible
regression results, storage atomicity/no-partial-state proof, `call_id` joins, fail-closed
tests, no-bypass tests, complete logging-schema tests, privacy/redaction policy, and final
whitelist confirmation. **No item here is code-confirmed on the current branch.**

---
