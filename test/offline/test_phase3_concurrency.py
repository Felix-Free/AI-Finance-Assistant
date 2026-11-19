"""Concurrency regression test for issue #27 (task sheet v20).

One offline, deterministic test proving that two concurrent
``storage.append_validated`` calls must both be persisted. Written against the
approved test commit ``0962595``; it must:

* fail IMMEDIATELY on ``0962595`` (direct ``"a"`` append, no ``os.replace``) with
  "append did not reach os.replace: this implementation is not atomic";
* fail on a fixed-``.tmp``/no-lock build with a lost record (one thread ok, the
  other errors, or its line missing);
* pass once the writer uses a unique temp file + a file lock covering
  read -> duplicate check -> budget check -> write -> replace.

Synchronisation lives ENTIRELY OUTSIDE the lock: the two ``os.replace`` wrappers
park each thread at the commit step and are released by the main thread. After
the lock is added, thread B simply blocks on the lock until A finishes, then runs
— no thread waits (while holding the lock) for another thread that needs that
same lock, so there is no deadlock. Timeouts are anti-hang guards only; the
verdict comes from ``outcomes``, ``iter_records()`` and the seed bytes.

Offline and deterministic: no network, no real model call. All files live under
``tmp_path``.
"""
import os
import threading

import pytest

from src import storage


def _record(call_id="abc123", **overrides):
    rec = {
        "call_id": call_id,
        "amount": 350,
        "category": "food",
        "total": 350.0,
        "budget_limit": 1000.0,
        "decided_at": "2026-11-12T00:00:00Z",
    }
    rec.update(overrides)
    return rec


@pytest.fixture
def data_path(monkeypatch, tmp_path):
    path = tmp_path / "data" / "records.jsonl"
    monkeypatch.setattr(storage, "DATA_PATH", path)
    return path


def test_concurrent_appends_keep_both_records(data_path, monkeypatch):
    storage.append_validated(_record(call_id="seed", amount=350, total=350))
    seed_bytes = data_path.read_bytes()
    assert storage.current_total() == 350.0

    a_at_replace = threading.Event()
    b_at_replace = threading.Event()
    release_a = threading.Event()
    release_b = threading.Event()
    b_lock_attempt = threading.Event()

    real_replace = os.replace

    def _wrapped_replace(src, dst):
        name = threading.current_thread().name
        if name == "A":
            a_at_replace.set()
            release_a.wait(2.0)
        elif name == "B":
            b_at_replace.set()
            release_b.wait(2.0)
        return real_replace(src, dst)

    # Point the wrapper at the exact object the writer will call. On the fixed
    # writer that is ``storage.os.replace``; on a build that has not imported
    # ``os`` yet, install a reference under ``storage`` for the duration of the
    # test (monkeypatch restores the namespace afterwards).
    if hasattr(storage, "os"):
        monkeypatch.setattr(storage.os, "replace", _wrapped_replace)
    else:
        monkeypatch.setattr(storage, "os", os, raising=False)
        monkeypatch.setattr(os, "replace", _wrapped_replace)

    # Optional lock probe: only if the implementation exposes a lock context
    # manager named ``_locked``. Absent on the current build; not required.
    locked = getattr(storage, "_locked", None)
    if locked is not None:
        def _probe(*args, **kwargs):
            if threading.current_thread().name == "B":
                b_lock_attempt.set()
            return locked(*args, **kwargs)

        monkeypatch.setattr(storage, "_locked", _probe)

    outcomes = {}

    def _worker(call_id, expected_spent=None):
        try:
            storage.append_validated(
                _record(call_id=call_id), expected_spent=expected_spent
            )
            outcomes[call_id] = "ok"
        except Exception as exc:  # noqa: BLE001 - record the class for the verdict
            outcomes[call_id] = type(exc).__name__

    # B needs expected_spent=400 so it reaches os.replace on BOTH the no-lock
    # build (persisted 350 -> 400 >= 350 allowed) and the locked build (persisted
    # 400 -> 400 == 400). total=420 == 400 + 20 in both.
    thread_a = threading.Thread(target=_worker, args=("a",), name="A")
    thread_b = threading.Thread(target=_worker, args=("b", 400), name="B")

    try:
        thread_a.start()
        assert a_at_replace.wait(1.0), (
            "append did not reach os.replace: this implementation is not atomic"
        )
        thread_b.start()
        # Wait for B to either reach the replace wrapper (no-lock path) or block
        # on the lock (locked path). Anti-hang timeout only.
        for _ in range(200):
            if b_at_replace.wait(0.005) or b_lock_attempt.wait(0.005):
                break
        release_a.set()
        thread_a.join(2.0)
        if not b_at_replace.is_set():
            b_at_replace.wait(2.0)
        release_b.set()
        thread_b.join(2.0)
    finally:
        release_a.set()
        release_b.set()
        if thread_a.ident is not None:
            thread_a.join(2.0)
        if thread_b.ident is not None:
            thread_b.join(2.0)

    assert outcomes == {"a": "ok", "b": "ok"}, outcomes
    ids = [r["call_id"] for r in storage.iter_records()]
    assert sorted(ids) == sorted(["seed", "a", "b"]), ids
    assert seed_bytes == data_path.read_bytes()[:len(seed_bytes)]
