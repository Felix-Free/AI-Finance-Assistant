# ADR-003 — Atomic Append and Locking for Validated Records

- **Status:** Accepted — role C confirmed the two open questions on 2026-11-19
  (lock-file location acceptable; no silent fallback).
- **Owner after review:** Role C (with B) — `docs/architecture/` is C/B-owned.
- **Date:** Phase 3 (Issue #27), 2026-11-19.
- **Related:** `docs/architecture/runtime-policy-catalog.md` (RP-004 fail-closed logging);
  `docs/architecture/invariants.md` (INV-001/002/003); `src/storage.py::append_validated`;
  `test/offline/test_phase3_concurrency.py`.

> **Reading this document.** Everything below is *(source)* unless marked *(derived — proposed)*.
> The decision has been **implemented** in `src/storage.py`; this ADR records the reasoning for
> C to confirm or reject. Acceptance is not implied by the code existing.

---

## 1. Context

### 1.1 What storage does *(source)*
`src/storage.py` is the only module that writes validated records to disk
(`data/records.jsonl`, append-only). Every write re-runs the `policy_core` guards before a byte
is written; a record that fails validation raises `StorageError`/`PolicyError` and the file is
left unchanged. The earlier atomicity fix wrote a **fixed** same-directory temp file
(`records.jsonl.tmp`) and committed it with `os.replace`.

### 1.2 The failure modes E found *(source)*
E reproduced two defects with the fixed `.tmp` and **no lock**:

- **Lost record:** two concurrent writers share `records.jsonl.tmp`; one writer's `os.replace`
  clobbers the other's, so a record that returned success is missing from the file.
- **Inconsistent outcome:** one writer raises `StorageError` while the other's record is
  nonetheless persisted — the read/duplicate/budget checks ran against stale state because they
  were not serialised with the write.

### 1.3 Why this matters *(source + derived — proposed)*
The product rule is "every accepted record is durable, and no rejected record is persisted"
(INV-001/002/003 re-checked at write time). A fixed temp name plus an unlocked
read-then-write permits both a lost update and a duplicate/budget race — the on-disk state can
diverge from the outcome the caller observed.

---

## 2. Decision

*(derived — proposed; implemented in `src/storage.py`)*

Adopt **two changes together**:

### 2.1 Unique same-directory temp per append
Each append creates its own temp via
`tempfile.mkstemp(dir=DATA_PATH.parent, prefix=DATA_PATH.name + ".", suffix=".tmp")`, writes the
existing bytes + the new line through `os.fdopen(fd, "wb")`, `flush()` + `os.fsync()`, closes,
then commits with `os.replace(tmp, DATA_PATH)`. On any `OSError` the temp is unlinked
(best-effort) and a `StorageError` is raised. No two writers can share a temp path.

### 2.2 A file lock across the whole check-and-write sequence
`storage._locked()` is a context manager over a sidecar lock file
`records.jsonl.lock` (same directory). It takes a **blocking** exclusive lock
(POSIX `fcntl.flock(LOCK_EX)`; Windows `msvcrt.locking(LK_LOCK)`). The lock is held across
**read → duplicate check → budget check → write → replace**. `_existing_call_ids()` and
`current_total()` run inside the lock, so the budget guard uses the value read under the same
lock. When neither OS lock is available the append **fails closed with `StorageError`** before
any temp file is created; there is no silent process-local fallback.

### Commit point

A successful `os.replace(tmp, DATA_PATH)` is the commit point. Failures before it (lock acquisition,
temp creation, copy, write, fsync, replace) surface as `StorageError` and leave the original file
untouched. A failure to release the lock **after** a successful replace is not an append failure: the
record is durable, the caller sees success, the OS releases the lock when the file closes, and the
release error is recorded by the module logger at WARNING with a fixed short message.

---

## 3. Consequences

### Positive
- Concurrent appends in the same process **and** across processes serialise; both records are
  kept (or the loser gets a correct `duplicate`/`budget` rejection), never a lost update.
- Readers are unaffected: they keep failing closed on a partial final line (RP-004), and
  `os.replace` means a reader always sees either the old file or the new one, never a mix.
- A crash while holding the lock is released by the OS when the process exits — no manual
  recovery.

### Negative / costs
- Writers serialise on the lock, so append throughput is limited to one at a time. Acceptable
  for this single-user finance assistant.
- A `records.jsonl.lock` file is created at runtime under `data/`; `data/` is already
  gitignored (`.gitignore` lines 3 and 9), so the lock file is not committed.
- `fsync` on each append adds latency; this is the price of durability.

### Neutral / out of scope
- No change to the record schema, the log schema, or `report_tokens`.
- When no OS lock is available the append fails closed with `StorageError` (no silent
  process-local fallback); such a platform cannot append until an OS lock is provided.

---

## 4. Alternatives rejected

| Alt | Description | Why rejected |
|---|---|---|
| Fixed `.tmp` | One shared temp name (the earlier code). | Collision: concurrent writers clobber each other's temp → lost record (E's reproduction). |
| Write-lock only | Lock around `os.replace` but not the read/check. | Duplicate/budget race remains: two writers both pass checks on stale state. |
| Process-local lock only, silently | `threading.Lock` and nothing else. | No cross-process protection; two processes still lose updates. Rejected **and now removed**: no silent fallback — the append fails closed with `StorageError` when no OS lock exists. |
| `O_EXCL` spin lock | Try to `O_EXCL`-create a lock file, spin on failure. | Stale lock after a crash needs manual cleanup; `flock`/`msvcrt` are released by the OS. |
| No lock | Rely on `os.replace` atomicity alone. | `os.replace` is atomic per-file but does not serialise the read/check/write sequence → lost update. |

---

## 5. Verification

- `test/offline/test_phase3_concurrency.py` — two threads append concurrently; asserts both
  succeed and all three records (`seed`, `a`, `b`) are present, with the seed bytes untouched.
  Passes three consecutive runs.
- E's three-run reproduction of the two failure modes motivated this decision.
- Atomicity (a failed commit leaves the original bytes untouched) is covered by
  `test/offline/test_phase3_hardening.py`.
- **E's two fault points** (fault-injection scenarios): (1) an invalid parent directory (the parent
  path is a regular file) surfaces as `StorageError`, not a raw `FileExistsError`/`OSError`, with the
  original bytes untouched; (2) a lock `_release` that raises `OSError` **after** a successful
  `os.replace` does not fail the append — the record is present and the module logger emits one
  WARNING with the fixed short message.
- `mypy` clean on the default target and on `--python-version 3.9`.

---

## 6. Open questions / pending confirmations

None — both questions were resolved by role C on 2026-11-19:

- **Resolved:** the sidecar lock-file location under `data/` is acceptable.
- **Resolved:** no silent process-local fallback; when neither `fcntl` nor `msvcrt` is available
  the append fails closed with `StorageError`.
