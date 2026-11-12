"""Wall-clock latency measurement for actual LLM calls (NFR-002 evidence).

Each iteration performs one real ``call_llm.extract("hotpot last night cost
350")`` and measures wall-clock milliseconds. Each sample is appended as one
JSON line to logs/latency.jsonl, and the summary prints
``p50 / p95 / max / n / model / timestamp`` (UTC ISO-8601).

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

LATENCY_PATH = pathlib.Path("logs/latency.jsonl")
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


def measure(n: int) -> int:
    from src import call_llm

    samples = []
    for _ in range(n):
        start = time.perf_counter()
        call_llm.extract(PROBE_TEXT)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        samples.append(elapsed_ms)
        _append_sample({
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": call_llm.MODEL,
            "latency_ms": elapsed_ms,
        })

    ordered = sorted(samples)
    p50 = _percentile_nearest_rank(ordered, 50)
    p95 = _percentile_nearest_rank(ordered, 95)
    print("p50_ms=%.3f" % p50)
    print("p95_ms=%.3f" % p95)
    print("max_ms=%.3f" % max(samples))
    print("n=%d" % len(samples))
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
