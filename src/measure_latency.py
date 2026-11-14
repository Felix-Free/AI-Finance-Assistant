"""Wall-clock latency measurement for actual LLM calls (NFR-001 evidence).

Each iteration performs one real ``call_llm.extract("hotpot last night cost
350")`` and measures wall-clock milliseconds. Each sample is appended as one
JSON line to logs/latency.jsonl, and the summary prints
``attempted / ok / failed / failure_rate``, the failure tally, then
``p50 / p95 / max / model / timestamp`` (UTC ISO-8601).

A failed attempt (``LlmTransportError`` or ``JSONDecodeError``) is counted,
never fatal: the loop always runs all ``n`` attempts and only successful samples
feed the percentiles, each of which prints its own ``(n=ok)``. A failure is not
written to logs/latency.jsonl; its evidence is already in logs/llm_calls.jsonl.
Failure labels are whitelisted (``_failure_kind``) and never carry a response
body, URL or raw exception text.

Percentile method: nearest-rank. For n sorted samples, the p-th percentile is
``sorted(ceil(p/100 * n) - 1)`` (1 <= rank <= n). No interpolation, no
rounding of the underlying samples.

``--dry-run`` performs no network call: it prints the plan and exits 0.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
import time
from datetime import datetime, timezone

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
LATENCY_PATH = _REPO_ROOT / "logs" / "latency.jsonl"
PROBE_TEXT = "hotpot last night cost 350"


def _percentile_nearest_rank(sorted_values, pct):
    """Nearest-rank percentile of an already-sorted list (never interpolates)."""
    if not sorted_values:
        return None
    rank = max(1, math.ceil(pct / 100.0 * len(sorted_values)))
    return sorted_values[rank - 1]


def _append_sample(sample: dict) -> None:
    LATENCY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LATENCY_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(sample, ensure_ascii=False) + "\n")


_TIMEOUT_MARKERS = ("timeout", "timed out")
_RESOLUTION_MARKERS = ("name resolution", "name or service not known",
                       "nodename nor servname", "temporary failure in name")


def _failure_kind(exc) -> str:
    """Whitelisted failure label; never carries a body, URL or raw repr (M4).

    Allowed shapes: ``http <status> (<Class>)``, ``transport: read timeout
    (<Class>)``, ``transport: name resolution (<Class>)``, ``transport: other
    (<Class>)``, ``not_json``.
    """
    name = type(exc).__name__
    if isinstance(exc, json.JSONDecodeError):
        return "not_json"
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int) and not isinstance(status_code, bool):
        return "http %d (%s)" % (status_code, name)
    text = str(exc).lower()
    if any(marker in text for marker in _TIMEOUT_MARKERS):
        return "transport: read timeout (%s)" % name
    if any(marker in text for marker in _RESOLUTION_MARKERS):
        return "transport: name resolution (%s)" % name
    return "transport: other (%s)" % name


def measure(n: int) -> int:
    from src import call_llm

    samples = []
    failed = 0
    tally = {}
    for index in range(1, n + 1):
        start = time.perf_counter()
        try:
            call_llm.extract(PROBE_TEXT)
        except (call_llm.LlmTransportError, json.JSONDecodeError) as exc:
            failed += 1
            kind = _failure_kind(exc)
            tally[kind] = tally.get(kind, 0) + 1
            print("attempt %d/%d: failed (%s)" % (index, n, kind))
            continue
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        samples.append(elapsed_ms)
        _append_sample({
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": call_llm.MODEL,
            "latency_ms": elapsed_ms,
        })

    ok = len(samples)
    failure_rate = (failed / n) if n else 0.0
    print("attempted=%d ok=%d failed=%d failure_rate=%.2f"
          % (n, ok, failed, failure_rate))
    for kind in sorted(tally):
        print("failures: %d x %s" % (tally[kind], kind))

    if ok == 0:
        print("no successful samples; percentiles not reported")
        return 2

    ordered = sorted(samples)
    p50 = _percentile_nearest_rank(ordered, 50)
    p95 = _percentile_nearest_rank(ordered, 95)
    print("p50_ms=%.3f (n=%d)" % (p50, ok))
    print("p95_ms=%.3f (n=%d)" % (p95, ok))
    print("max_ms=%.3f" % max(samples))
    if ok < 5:
        print("low_confidence: only %d successful samples" % ok)
    print("model=%s" % call_llm.MODEL)
    print("timestamp=%s" % datetime.now(timezone.utc).isoformat(timespec="seconds"))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Measure LLM call latency.")
    parser.add_argument("--n", type=int, default=20, help="number of calls (default 20)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan and exit without any network call")
    args = parser.parse_args(argv)

    if args.dry_run:
        print("dry-run: would perform %d call(s) of extract(%r)" % (args.n, PROBE_TEXT))
        print("dry-run: would append %d line(s) to %s" % (args.n, LATENCY_PATH))
        print("dry-run: no network call, nothing written")
        return 0

    return measure(args.n)


if __name__ == "__main__":
    sys.exit(main())
