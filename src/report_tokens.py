"""Token measurement report (NFR-002) — per call, per session, global counters.

Reads logs/llm_calls.jsonl (the LLM log is the only source of truth for token
statistics; the storage schema is untouched).

Source: the gateway response's `usage` object, mapped to
        {"input": usage.prompt_tokens, "output": usage.completion_tokens,
         "total": usage.total_tokens}
Missing data is recorded as null and is never estimated or zero-filled.

Counts (`usage_complete` / `usage_missing` / `usage_partial`) are per actual API
call (log lines whose ``request_made`` is true). A session whose contributing
calls are not all complete has an ``incomplete`` token total; a token value that
is missing is printed as ``-`` and never as 0.

Read-only: this module writes nothing.
"""
from __future__ import annotations

import json
import pathlib
import sys

LOG_PATH = pathlib.Path("logs/llm_calls.jsonl")

MISSING = "-"


def _load_lines(path: pathlib.Path):
    """Return the parsed log lines; a malformed line is skipped, not estimated."""
    if not path.exists():
        return None
    records = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _fmt(value):
    """Render a token value: ints verbatim, None/absent as '-' (never 0)."""
    return value if isinstance(value, int) and not isinstance(value, bool) else MISSING


def _tokens_of(record):
    """Return the three token values (input/output/total) as ints or None."""
    tokens = record.get("tokens")
    if not isinstance(tokens, dict):
        return {"input": None, "output": None, "total": None}
    return {
        "input": tokens.get("input") if isinstance(tokens.get("input"), int) else None,
        "output": tokens.get("output") if isinstance(tokens.get("output"), int) else None,
        "total": tokens.get("total") if isinstance(tokens.get("total"), int) else None,
    }


def _is_complete(tokens):
    return all(isinstance(v, int) and not isinstance(v, bool)
               for v in tokens.values())


def _per_call_rows(records):
    """(A) one row per actual API call (request_made true)."""
    return [r for r in records if r.get("request_made") is True]


def _session_summary(records):
    """(B) aggregate actual calls by session_id."""
    sessions = {}
    for record in records:
        if record.get("request_made") is not True:
            continue
        sid = record.get("session_id")
        bucket = sessions.setdefault(sid, {
            "api_calls": 0, "complete": 0, "missing": 0, "partial": 0,
            "total": 0, "has_total": False, "complete_all": True,
        })
        bucket["api_calls"] += 1
        tokens = _tokens_of(record)
        source = record.get("usage_source")
        if source == "gateway" and _is_complete(tokens):
            bucket["complete"] += 1
        elif source == "partial":
            bucket["partial"] += 1
            bucket["complete_all"] = False
        else:
            bucket["missing"] += 1
            bucket["complete_all"] = False
        if isinstance(tokens["total"], int):
            bucket["total"] += tokens["total"]
            bucket["has_total"] = True
        else:
            bucket["complete_all"] = False
    return sessions


def _print_table(headers, rows):
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    fmt = "  ".join("{:<%d}" % w for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*["-" * w for w in widths]))
    for row in rows:
        print(fmt.format(*[str(c) for c in row]))


def report(records) -> None:
    api_calls = _per_call_rows(records)
    not_called = [r for r in records if r.get("request_made") is False]

    # (A) per actual API call
    print("== Per call (per actual API call) ==")
    rows = []
    for r in api_calls:
        t = _tokens_of(r)
        rows.append([
            r.get("call_id", MISSING),
            r.get("request_id", MISSING),
            r.get("session_id", MISSING),
            _fmt(t["input"]),
            _fmt(t["output"]),
            _fmt(t["total"]),
            r.get("usage_source", MISSING),
        ])
    _print_table(["call_id", "request_id", "session_id", "input", "output",
                  "total", "usage_source"], rows)

    # (B) per session
    print()
    print("== Per session ==")
    sessions = _session_summary(records)
    sess_rows = []
    incomplete_notes = []
    for sid, b in sessions.items():
        status = "complete" if b["complete_all"] else "incomplete"
        total = str(b["total"]) if b["has_total"] else MISSING
        if status == "incomplete":
            total = total + "*"
            gaps = b["missing"] + b["partial"]
            incomplete_notes.append("%s: incomplete: %d call(s) without full usage"
                                    % (sid, gaps))
        sess_rows.append([
            sid, b["api_calls"], b["complete"], b["missing"], b["partial"],
            total, status,
        ])
    _print_table(["session_id", "api_calls", "usage_complete", "usage_missing",
                  "usage_partial", "total_tokens", "session_total_status"],
                 sess_rows)
    if incomplete_notes:
        print()
        print("  * " + "* ".join(incomplete_notes))

    # (C) global counters
    print()
    print("== Global counters ==")
    complete = sum(1 for r in api_calls
                   if r.get("usage_source") == "gateway" and _is_complete(_tokens_of(r)))
    partial = sum(1 for r in api_calls if r.get("usage_source") == "partial")
    missing = sum(1 for r in api_calls
                  if not (r.get("usage_source") == "gateway" and _is_complete(_tokens_of(r)))
                  and r.get("usage_source") != "partial")
    _print_table(["counter", "value"], [
        ["total_api_calls", len(api_calls)],
        ["usage_complete_calls", complete],
        ["usage_missing_calls", missing],
        ["usage_partial_calls", partial],
        ["not_called_calls", len(not_called)],
    ])

    # whole-period total (optional per-owner metric), same completeness label
    period = 0
    period_has = False
    period_complete = True
    for r in api_calls:
        t = _tokens_of(r)
        if isinstance(t["total"], int):
            period += t["total"]
            period_has = True
        else:
            period_complete = False
        if not (r.get("usage_source") == "gateway" and _is_complete(t)):
            period_complete = False
    period_value = str(period) if period_has else MISSING
    period_status = "complete" if period_complete else "incomplete"
    print()
    print("period_total_tokens: %s (%s)" % (period_value, period_status))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    path = pathlib.Path(argv[0]) if argv else LOG_PATH
    records = _load_lines(path)
    if records is None:
        print("no calls recorded")
        return 0
    if not records or not any("request_made" in r for r in records):
        print("no calls recorded")
        return 0
    report(records)
    return 0


if __name__ == "__main__":
    sys.exit(main())
