"""Tests for the two measurement scripts (task sheet v5.1 §5, Task C).

Offline and deterministic: report_tokens reads a temp log; measure_latency is
only exercised via --dry-run. No network access, nothing written to logs/.
"""
import io
import json
from contextlib import redirect_stdout

import pytest

from src import measure_latency, report_tokens


def _write_log(tmp_path, records):
    path = tmp_path / "llm_calls.jsonl"
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )
    return path


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = report_tokens.main(argv)
    return code, buf.getvalue()


GATEWAY = {"request_made": True, "usage_source": "gateway",
           "call_id": "c1", "request_id": "r1", "session_id": "s1",
           "tokens": {"input": 10, "output": 5, "total": 15}}
PARTIAL = {"request_made": True, "usage_source": "partial",
           "call_id": "c2", "request_id": "r2", "session_id": "s1",
           "tokens": {"input": 7, "output": None, "total": None}}
MISSING = {"request_made": True, "usage_source": "missing",
           "call_id": "c3", "request_id": "r3", "session_id": "s1",
           "tokens": None}
NOT_CALLED = {"request_made": False, "usage_source": "missing",
              "call_id": "c4", "request_id": "r4", "session_id": "s1",
              "tokens": None}


def test_report_no_file_prints_no_calls_and_exits_zero(tmp_path):
    code, out = _run([str(tmp_path / "absent.jsonl")])
    assert code == 0
    assert "no calls recorded" in out


def test_report_mixed_log_counters_and_incomplete_session(tmp_path):
    path = _write_log(tmp_path, [GATEWAY, PARTIAL, MISSING, NOT_CALLED])
    code, out = _run([str(path)])
    assert code == 0
    assert "total_api_calls" in out
    assert "usage_complete_calls" in out
    assert "usage_partial_calls" in out
    assert "usage_missing_calls" in out
    assert "not_called_calls" in out
    assert "incomplete" in out


def test_report_mixed_session_is_incomplete_and_missing_shown_dash(tmp_path):
    path = _write_log(tmp_path, [GATEWAY, PARTIAL, MISSING, NOT_CALLED])
    _, out = _run([str(path)])
    assert "incomplete" in out
    assert "session_total_status" in out
    # the missing row's token cells are '-' not '0'
    assert "15*" in out
    assert "incomplete: 2 call(s) without full usage" in out


def test_report_all_gateway_session_complete(tmp_path):
    second = dict(GATEWAY, call_id="c9", request_id="r9",
                  tokens={"input": 2, "output": 3, "total": 5})
    path = _write_log(tmp_path, [GATEWAY, second])
    _, out = _run([str(path)])
    assert "complete" in out
    assert "incomplete" not in out
    assert "period_total_tokens: 20 (complete)" in out


def _counter_value(out, name):
    for line in out.splitlines():
        parts = line.split()
        if parts and parts[0] == name:
            return int(parts[-1])
    raise AssertionError("counter %r not found" % (name,))


def test_report_counts_only_request_made_true(tmp_path):
    path = _write_log(tmp_path, [GATEWAY, NOT_CALLED, dict(NOT_CALLED, call_id="c5")])
    _, out = _run([str(path)])
    assert _counter_value(out, "total_api_calls") == 1
    assert _counter_value(out, "not_called_calls") == 2
    assert _counter_value(out, "usage_complete_calls") == 1


def test_measure_latency_dry_run_exits_zero_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(measure_latency, "LATENCY_PATH", tmp_path / "logs" / "latency.jsonl")
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = measure_latency.main(["--dry-run", "--n", "5"])
    assert code == 0
    assert "dry-run" in buf.getvalue()
    assert not (tmp_path / "logs").exists()


def test_percentile_nearest_rank():
    values = list(range(1, 101))
    assert measure_latency._percentile_nearest_rank(values, 50) == 50
    assert measure_latency._percentile_nearest_rank(values, 95) == 95
    assert measure_latency._percentile_nearest_rank([42], 95) == 42
    assert measure_latency._percentile_nearest_rank([], 50) is None
