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
- **Evidence and logging** — mixed: `code-confirmed` — on this branch the call-log line is written but **not** with the full field set: the configuration-failure path writes only `{input, error="config: missing base url or key"}` (`src/call_llm.py:124`, no `raw`/`parsed`), and the HTTP-attempts failure path writes `{input, error=..., [body]}` (`src/call_llm.py:140-145`, no `raw`/`parsed`). The Phase 2 fields `request_made`, `tokens`, `raw`, `parsed=null` on these paths are **`doc-only (unmerged)`** and **not** emitted on this branch. D-02 (§5) still tracks the unresolved risk that some error text includes raw exception or response details — `code-confirmed` that `str(exc)` is used on this branch (`src/call_llm.py:76,89,96`).
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
2. **Call-log integrity (RP-004).** D writes the call line after the attempt or failure
   is known, before returning a result or raising it. If logging fails, no result is
   usable; the HTTP attempt and response parsing may already have occurred.
3. **Pipeline metadata and storage read.** After `extract` returns, a missing `call_id`
   raises `StorageError` (the valid-nonobject gap under RP-001). If `spent is None`,
   `storage.current_total()` reads persisted amounts and can raise `StorageError`
   (RP-007) before policy validation.
4. **Invariants (RP-003/005/006).** `policy_core` validates before a normal record write.
   A rejection attempts one review line; a review-write failure raises `StorageError`
   instead of returning the pending `PolicyError`.
5. **Storage append (RP-007).** Accepted records are structurally checked and appended.
   A failure raises `StorageError`, never `policy:*`; partial-write rollback is unverified.

After a failure is detected, no later result is accepted or stored. The call log is
written after classification of model-client outcomes, including failure paths.

> **Current-branch reconciliation (Phase 3, `code-confirmed`).** Steps 3 and 5 above, and
> the `StorageError` half of step 4, are `doc-only (unmerged)` — they describe D's unmerged
> branch. On **this branch** (`origin/main`-identical) the real order is:
> (1) RP-002/001 model-client classification inside `extract`; (2) RP-004 call-log write,
> then return/raise; (3) RP-003/005/006 via `policy_core.validate_record`; on `PolicyError`
> a single `logs/review.jsonl` line is attempted. There is **no** storage read or append
> (no `src/storage.py`), **no** `call_id` metadata step, and a review-write failure raises
> `PolicyError(code="policy:budget")` (misclassified — see RP-007), not `StorageError`.

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

> **HISTORICAL / UNMERGED CONTRACT — NOT CURRENT-BRANCH IMPLEMENTATION.**
> Everything in §5 (`call_id` / `request_id` / `session_id`, `tokens` / `usage_source` /
> `request_made`, the ten-key logging schema, the pre-HTTP local-failure lifecycle, the
> storage-failure contract, and the `call_id` evidence joins) describes **D's unmerged
> branch**. **None of these exist on the current branch** (`feat/c-phase3-policy-60339160`,
> `src/`/`test/` byte-identical to `origin/main` `6997cef`): `src/call_llm.py` here logs only
> `{input, raw, parsed}` (success) or `{input, error[, body]}` (failures), and there is no
> `uuid4`/`call_id`/`session_id`, no `tokens`/`usage_source`/`request_made`, and no
> `src/storage.py`. These sections are recorded as the agreed Phase 2 **contract** for D to
> implement; they must not be read as properties the current branch possesses.

> **Scope.** Phase 2 introduces a `call_id` that joins a model call to its downstream
> evidence, optional token accounting, an independent storage-failure error, and the
> Phase 2 evidence-join contract supplementing NFR-006 log traceability. This section
> records the agreed contracts. It does not renumber RP-001..RP-006. RP-001/002 are
> clarified in §2 to match D's implemented
> distinction between invalid model-content JSON, malformed HTTP response envelopes and
> pre-HTTP configuration failure. The pipeline behavior that implements the call-id,
> logging and storage contracts is D's; the NFR-006 log-coverage and Phase 2 join
> measurements are E's. C defines the contracts only.

### Call identifiers
*(historical / unmerged contract — `call_id` is absent on the current branch)*

- **Generation.** `call_id` is generated **inside `src/call_llm.py`** as
  `uuid4().hex` — a 32-hex-character string for each `extract` attempt, including a
  configuration failure before HTTP is attempted. No other format is valid; no caller
  may synthesize or override one.
- **Return channel.** `call_llm` returns the value to its caller through the private
  dictionary key **`__call_id__`** on the returned object.
- **Carriage.** The pipeline carries that value along the evidence path so that the
  downstream evidence records for one decision can be joined by the same `call_id`.
- **Boundary.** `__call_id__` is **removed before the payload reaches
  `src/policy_core.py`**. `policy_core` never sees a private key; it judges only the
  business payload.
- **Fail-closed interaction.** Because the id is produced in the same module that writes
  the audit line (RP-004), a call that cannot be logged keeps producing no usable result;
  `call_id` never rescues an unlogged call.

### LLM call logging
*(historical / unmerged contract — the current branch does not emit these fields/schema)*

- **Required fields, unchanged.** `input`, `raw`, `parsed` and `error` keep their names and
  meaning (RP-004). They are never renamed, dropped or reinterpreted.
- **Extra fields.** `call_id` and `tokens` **may** be added as extra fields. They are
  additive: a reader that ignores them still sees the four required fields as before.
- **Token semantics.** `tokens` is `null` when no gateway usage object is available or
  the call fails before usage is processed. When the gateway supplies a usage object on a
  successful parse, `tokens` is an object with the keys `input`, `output` and `total`;
  missing or non-integer values inside that object are `null`. It records gateway-reported
  usage that D recorded, never an estimate. On JSON parsing failure, D logs
  `tokens: null` and `usage_source = missing` even if the HTTP response included usage;
  that usage is not carried into the failure log. `usage_source` is classified as follows:
  - **three integer values** → `usage_source = gateway`;
  - **at least one integer and at least one `null`** → `usage_source = partial`;
  - **`tokens: null` or all three values `null`** → `usage_source = missing`.
  Non-integer values (for example strings or booleans) normalize to `null` before this
  classification when a usage object is present.
- **Never fabricate.** Zero is **never** written as a substitute for a missing token value,
  and token usage is **never** estimated. `tokens: null` means no usage was recorded,
  including when parsing failed; a processed usage object with no valid counts becomes
  `{"input": null, "output": null, "total": null}`. Both have `usage_source = missing`.
  The stored `usage_source` values remain exactly `gateway`, `partial` and `missing`.
- **One line per attempt.** With a writable log, exactly **one** `logs/llm_calls.jsonl`
  record is written per `extract` attempt, including pre-HTTP configuration failure.
  RP-004 is the exception when logging itself fails. Adding `call_id` /
  `tokens` / the approved metadata fields does not add a second line, and policy outcomes
  still go to `logs/review.jsonl`
  (RP-003/RP-005/RP-006), not here.

#### 5.2.1 Approved additional metadata fields
*(historical / unmerged contract — none of `session_id`, `request_id`, `usage_source`,
`request_made`, `call_id`, or `tokens` exist on the current branch)*

The user approved four further logging fields for Phase 2. They are **additive** next to
the required four (`input`, `raw`, `parsed`, `error`) and the additional fields (`call_id`,
`tokens`); nothing above is renamed or removed.

- **`session_id`** — a 32-character `uuid4().hex` generated once when `src/call_llm.py`
  is loaded. Every call in that process shares it, so **per-session aggregation** in D's
  current implementation means grouping by process run. It does not identify a separate
  user session when one process handles multiple users. It is distinct from `call_id`,
  which is generated for each call.
- **`request_id`** — an identifier for **one user request**. One request may trigger
  **multiple** `extract` attempts, so several `llm_calls` records may share one
  `request_id`. `call_id` remains the unique identifier for **one attempt**;
  `request_id` groups attempts, `call_id` identifies one attempt. In D's current
  `pipeline.process`, one `request_id` is created per invocation and only one `extract`
  call is made; multi-attempt grouping requires a caller to pass the same id explicitly
  to multiple `extract` calls and is not yet a pipeline behavior.
- **`usage_source`** — an enum with **exactly** these values: `gateway`, `partial`,
  `missing`. It describes the token counts **recorded in this log line**: `gateway` = all
  three counts present, `partial` = some counts present, `missing` = no counts recorded.
  `missing` does not prove the gateway supplied no usage: D also records it when JSON
  parsing fails before the returned usage is used.
- **`request_made`** — a boolean indicating whether the code **attempted an HTTP call**.
  It is `true` when `call_llm` enters its HTTP path, including connection, DNS and timeout
  failures; it does **not** prove that the request reached the gateway. It is `false` for
  local/configuration failures that stop before the HTTP path (for example missing base URL
  or API key). This is a structured boolean, not inferred from `error` text.
- **Derived `not_called` category** — reporting may count `request_made: false` rows as
  `not_called`. This is an operational reporting category, not a fourth `usage_source` value;
  the stored `usage_source` enum remains exactly `gateway`, `partial`, or `missing`.

Preserved requirements (unchanged by these fields):

- `input`, `raw`, `parsed` and `error` keep their names and meaning (RP-004).
- `call_id` remains the unique identifier for one `extract` attempt, even if HTTP was not attempted.
- `tokens` remains additive and is always present: `null` if usage was not recorded,
  otherwise an object with `input`, `output` and `total` (missing counts are `null`).
- Missing token usage is **never** written as zero or fabricated. Both `tokens: null` and
  an object with all three counts `null` have `usage_source = missing`.
- `policy:*` remains reserved for deterministic rule rejection (RP-003/005/006).
- Exactly one `llm_calls` record per `extract` attempt remains the contract when logging
  succeeds; RP-004 prevents use of an attempt whose log write fails.
- `usage_source` must stay consistent with `tokens`: `gateway`/`partial` imply token data
  exists, `missing` implies it does not.

#### 5.2.2 Pre-HTTP local failures (confirmed on D's branch; historical / unmerged here)

A missing base URL or API key stops the call before the HTTP attempt but **still writes
exactly one `llm_calls.jsonl` line**. The record uses the same ten-key schema as a normal
call; missing values are written as `null` and **never omitted**:

- **All ten schema keys are present** (`input`, `raw`, `parsed`, `error`, `call_id`,
  `tokens`, `session_id`, `request_id`, `usage_source`, `request_made`); a missing value is
  `null`, never an absent key.
- **Identifiers:** `call_id`, `session_id` and `request_id` are 32-character `uuid4().hex`.
- **`usage_source`** is `missing`.
- **`tokens`** is `null` because no gateway usage object exists before an HTTP request.
- **`raw`** and **`parsed`** are `null`.
- **`request_made`** is `false`.

This is the **only** `request_made = false` path in D's current implementation: missing
configuration stops before the HTTP attempt. Any path that attempts the call records
`request_made = true`, even if the connection fails before the gateway receives it.

### Storage failure is not a policy rejection
*(historical / unmerged contract — no `src/storage.py` exists on the current branch)*

> This section is the contract rationale; the formal policy entry is **RP-007** (§2).

- **Trigger.** Storage input validation, duplicate-id checking, reading existing records
  or writing a record fails. These include malformed persisted data and I/O errors.
- **Action:** raise an **independent `StorageError`**. It is a transport/infrastructure
  failure, not a rule decision.
- **Reserved prefix.** `policy:*` error codes are reserved **only** for deterministic
  policy/rule rejection (amount, category, budget — RP-003/005/006). A storage failure
  **must not** be rewritten as `policy:*`; doing so would make "correctly refused" and
  "failed to persist" indistinguishable.
- **No partial state (required boundary; implementation verification pending).** A record
  write failure must leave **no partial state change**: the write either completes or the previous
  state stands. No write-then-check, no half-applied record. See RP-007 — the current
  append-mode write raises `StorageError` but does not demonstrate rollback, so this remains
  a C-required boundary rather than a verified property.
- **Evidence:** the failure surfaces as `StorageError` to the caller; it never produces a
  `review.jsonl` policy line.

### Evidence linkage by `call_id`
*(historical / unmerged contract — `call_id` and `data/records.jsonl` are absent on the current branch)*

Main's NFR-006 measures **log coverage**: the percentage of model calls with a
`llm_calls.jsonl` line and policy rejections with a `review.jsonl` line. Its numeric
coverage threshold is `null` in main. D writes one call-log line per `extract` attempt
when the log is writable, including pre-HTTP configuration failures, and one review line
per policy rejection when the review log is writable. If either evidence write fails, the
operation fails closed (RP-004 or `StorageError`) rather than proceeding as a successful
decision. The Phase 2 `call_id` join below is an **additional structural traceability
check**, not a replacement definition or a numeric coverage threshold.

There are three possible evidence locations — the two log files (`llm_calls` and
`review`) plus the storage record in `data/records.jsonl` — but a
decision produces **one applicable pair**, not all three records at once. The check is
path-specific:

- **Accepted decision:** `llm_calls.call_id` equals the accepted record's
  `data/records.jsonl` `call_id`. Evidence shape = the `llm_calls` record **plus** the
  normal storage evidence.
- **Rejected decision:** `llm_calls.call_id` equals the `review.jsonl` line's `call_id`.
  Evidence shape = the `llm_calls` record **plus** the review evidence.
- **A rejected decision must not create a normal storage record.** Rejection means the
  stored data is unchanged (RP-003/005/006); the review line is the second evidence record
  instead, and no normal storage record exists to join.
- **Conditional, one shape per decision.** A decision has exactly one of the two shapes; it
  never has both a storage record and a review line for the same decision.

A decision is **not** required to produce all three records. The join rule does not require
"three relevant `call_id` locations" and does not set NFR-006's numeric log-coverage
threshold.

### 5.5 Approved D decisions (recorded here for the shared boundary)

- **`call_id` format:** `uuid4().hex`. Fixed 32-hex-character form; see the Call identifiers section.
- **`request_id` format and role:** also `uuid4().hex`, generated per **user request**. It is
  an **additive grouping** field: one request may span several calls, so several
  `llm_calls` records share one `request_id`. `call_id` remains the **primary evidence-join
  key**; `request_id` groups calls belonging to one user request.
- **`_append_rejection` preserves the original rejection code.** The rejection writer is
  `src/pipeline.py::_append_rejection`. It writes the **original** `PolicyError.code` (for
  example `policy:category`) as the line's `error`, rather than replacing or re-coding it,
  so the review line and the routing decision agree. Each rejection line carries both
  `call_id` (join key) and `request_id` (grouping).

#### Validated storage spend — implemented on D's branch, not merged

- **Approved boundary:**
  `append_validated(record, expected_spent=None)` with
  - `total == expected_spent + amount`, and
  - `expected_spent >= already persisted cumulative spend`.

  `expected_spent` would be a **numeric validation parameter, not a persisted record
  field**. Its purpose is to prevent **under-reporting prior spending**, which would
  otherwise let a record slip past the budget guard (`C-INV-003` / `RP-005`).
- **D-branch implementation (verified at `df729a9`, not merged):**
  `src/storage.py::append_validated(record, expected_spent=None)` validates the
  numeric parameter, rejects an `expected_spent` below persisted cumulative spend,
  re-runs the policy guards, and checks `total == expected_spent + amount` before
  appending. `src/pipeline.py::process` passes its effective `spent` value into this
  parameter. The implementation and its offline tests exist on D's branch only.
- **Main-branch status:** The current `main` snapshot still has the older
  `append_validated(record)` boundary, so the budget-bypass gap remains open on `main`
  until D's branch is merged. The D implementation must not be described as present on
  `main` before that merge.

#### Repository-root anchoring of evidence paths (verified per module)

Evidence paths are anchored to the repository root via
`pathlib.Path(__file__).resolve().parents[1]`, so they follow the module rather than the
process working directory. This is **confirmed** in:

- `src/call_llm.py` — `LOG_PATH` (`logs/llm_calls.jsonl`)
- `src/pipeline.py` — `REVIEW_PATH` (`logs/review.jsonl`)
- `src/storage.py` — `DATA_PATH` (`data/records.jsonl`)
- `scripts/measure_latency.py` — `LATENCY_PATH` (`logs/latency.jsonl`)

It is **not** used everywhere: `src/report_tokens.py` still defaults to a **relative**
`LOG_PATH = pathlib.Path("logs/llm_calls.jsonl")` (working-directory dependent, overridable
by an argument), and `scripts/measure_tokens.py` defines no path of its own. The anchoring
claim applies only to the four modules listed above.

> **Branch caveat (Phase 3).** Only `src/call_llm.py` and `src/pipeline.py` exist on this
> branch, and **neither** anchors its path: `LOG_PATH = pathlib.Path("logs/llm_calls.jsonl")`
> (`src/call_llm.py:22`) and `REVIEW_PATH = pathlib.Path("logs/review.jsonl")`
> (`src/pipeline.py:18`) are **relative** and therefore working-directory dependent. The
> `parents[1]` anchoring and the `src/storage.py` / `scripts/measure_latency.py` /
> `scripts/measure_tokens.py` / D-branch modules named above are `doc-only (unmerged)`.

#### D-02 — error logging short-code rule (unresolved implementation debt)

Short, **secret-safe** error information in logs is a **security requirement** (Phase 1,
`structural-constraints.md §5`): the `error` field is a short code, and a raw exception
string must not be able to leak a URL, query parameter or credential into the log. D's
current `src/call_llm.py::extract` constructs `error` using full `str(exc)` for transport
and protocol failures; `_append_log` then writes that record. This is an **unresolved D
implementation debt (D-02)**: the security requirement stands and the implementation
has not yet been brought into line with it.

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
