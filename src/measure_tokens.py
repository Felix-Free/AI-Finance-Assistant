"""Token-cost sampling over a varied corpus (NFR-002 evidence).

Pure sampler: the only thing it does is call ``call_llm.extract`` once per
attempt with a sentence from a varied corpus. It reads no file under logs/,
writes no log line and prints no token values. The call log written by
``call_llm`` is the only token evidence; ``src.report_tokens`` interprets it
(per-row tokens, per-session totals, the five counters).

A failed attempt (``LlmTransportError`` or ``JSONDecodeError``) is counted and
never fatal: all ``n`` sentences are attempted, so the failure rate is knowable.
Failure labels are whitelisted by ``measure_latency._failure_kind`` and never
carry a response body, URL or raw exception text.

Corpus choice (invariant this module serves): token cost must be measured across
varied inputs so a distribution exists, while latency is measured against a
fixed probe. This module never varies the latency probe and never measures
latency.

``--dry-run`` performs no network call: it prints the plan and the corpus size
and exits 0.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from src.measure_latency import _failure_kind

CORPUS = (
    "coffee 12",
    "lunch 45.5",
    "hotpot last night cost 350",
    "bought a new laptop for 8999 at the apple store",
    "taxi from the airport to the hotel, 320 HKD",
    "monthly gym membership 480, charged on the first of each month",
    "dinner with three colleagues, total 1280, split evenly",
    "买了一杯奶茶 18 块",
    "a 65-inch television, on sale, 4999",
    "annual software subscription 1299 paid by card",
    "two movie tickets and popcorn, 260",
    "electricity bill for November, 780.5",
    "pharmacy: two boxes of painkillers and one thermometer, 143.8",
    "rent for the month transferred to the landlord, 12500",
    "昨天打车回家花了 76 港币",
    "weekly grocery run at the market, vegetables and fruit, 238",
    "concert ticket, front row, 1580",
    "replaced the phone screen, 850",
    "set menu lunch with the client at a hotel restaurant, 688",
    "monthly internet and mobile bundle, 399",
)


def _load_corpus(path) -> list:
    """Load one sentence per line; blank lines are skipped, not invented."""
    lines = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
    sentences = [line.strip() for line in lines if line.strip()]
    return sentences


def measure(sentences, n: int) -> int:
    """INV: only successful attempts are counted as ok; failures never end the run."""
    from src import call_llm

    if not sentences:
        print("no sentences in corpus")
        return 2

    ok = 0
    failed = 0
    tally = {}
    for index in range(1, n + 1):
        sentence = sentences[(index - 1) % len(sentences)]
        try:
            call_llm.extract(sentence)
        except (call_llm.LlmTransportError, json.JSONDecodeError) as exc:
            failed += 1
            kind = _failure_kind(exc)
            tally[kind] = tally.get(kind, 0) + 1
            print("attempt %d/%d: failed (%s)" % (index, n, kind))
            continue
        ok += 1

    failure_rate = (failed / n) if n else 0.0
    print("attempted=%d ok=%d failed=%d failure_rate=%.2f"
          % (n, ok, failed, failure_rate))
    for kind in sorted(tally):
        print("failures: %d x %s" % (tally[kind], kind))

    if ok == 0:
        print("no successful samples")
        return 2

    print("next: run `python -m src.report_tokens`"
          "   (per-row tokens, per-session totals, five counters)")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Sample token cost over a varied corpus.")
    parser.add_argument("--n", type=int, default=None,
                        help="number of calls (default: size of the corpus)")
    parser.add_argument("--file", default=None,
                        help="one sentence per line; replaces the built-in corpus")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan and exit without any network call")
    args = parser.parse_args(argv)

    if args.file is not None:
        sentences = _load_corpus(args.file)
    else:
        sentences = list(CORPUS)

    n = len(sentences) if args.n is None else args.n

    if args.dry_run:
        print("dry-run: would perform %d call(s) over %d sentence(s)"
              % (n, len(sentences)))
        print("dry-run: sentence source=%s"
              % (args.file if args.file is not None else "built-in CORPUS"))
        print("dry-run: no network call, nothing written")
        return 0

    return measure(sentences, n)


if __name__ == "__main__":
    sys.exit(main())
