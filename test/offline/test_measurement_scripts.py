"""Tests for the two measurement scripts (task sheet v5.1 §5, Task C).

Offline and deterministic: report_tokens reads a temp log; measure_latency is
only exercised via --dry-run. No network access, nothing written to logs/.
"""
import io
import json
import os
import pathlib
import subprocess
import sys
from contextlib import redirect_stdout

import pytest

from src import (call_llm, measure_latency, measure_tokens, pipeline,
                 report_tokens, storage)


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


def _request_row(out, request_id):
    """Return the split cells of the per-request row for request_id."""
    in_block = False
    for line in out.splitlines():
        if line.startswith("== Per request"):
            in_block = True
            continue
        if in_block and line.startswith("=="):
            break
        parts = line.split()
        if in_block and parts and parts[0] == request_id:
            return parts
    raise AssertionError("no per-request row for %r in:\n%s" % (request_id, out))


def test_request_block_one_request_three_calls(tmp_path):
    base = dict(GATEWAY, request_id="rq1", session_id="s1")
    path = _write_log(tmp_path, [
        dict(base, call_id="a", tokens={"input": 10, "output": 5, "total": 15}),
        dict(base, call_id="b", tokens={"input": 20, "output": 6, "total": 26}),
        dict(base, call_id="c", tokens={"input": 1, "output": 2, "total": 3}),
    ])
    _, out = _run([str(path)])
    row = _request_row(out, "rq1")
    assert row[1] == "3"
    assert row[2] == "31" and row[3] == "13" and row[4] == "44"
    assert row[5] == "gateway" and row[6] == "x3"
    assert row[-1] == "complete"


def test_request_block_two_requests_interleaved(tmp_path):
    a = dict(GATEWAY, request_id="rq1", session_id="s1")
    b = dict(GATEWAY, request_id="rq2", session_id="s1")
    path = _write_log(tmp_path, [
        dict(a, call_id="a1", tokens={"input": 10, "output": 5, "total": 15}),
        dict(b, call_id="b1", tokens={"input": 100, "output": 50, "total": 150}),
        dict(a, call_id="a2", tokens={"input": 2, "output": 3, "total": 5}),
    ])
    _, out = _run([str(path)])
    row1 = _request_row(out, "rq1")
    row2 = _request_row(out, "rq2")
    assert row1[1] == "2" and row1[2] == "12" and row1[4] == "20"
    assert row2[1] == "1" and row2[2] == "100" and row2[4] == "150"


def test_request_block_missing_line_is_incomplete_and_footnoted(tmp_path):
    base = dict(GATEWAY, request_id="rq1", session_id="s1")
    path = _write_log(tmp_path, [
        dict(base, call_id="a", tokens={"input": 10, "output": 5, "total": 15}),
        dict(MISSING, call_id="b", request_id="rq1"),
    ])
    _, out = _run([str(path)])
    row = _request_row(out, "rq1")
    assert row[1] == "2"
    assert row[2] == "10" and row[3] == "5" and row[4] == "15"
    assert row[-1] == "incomplete*"
    assert "rq1: incomplete: 1 call(s) without full usage" in out


def test_request_block_no_known_values_prints_dash_not_zero(tmp_path):
    path = _write_log(tmp_path, [dict(MISSING, call_id="a", request_id="rq1")])
    _, out = _run([str(path)])
    row = _request_row(out, "rq1")
    assert row[2:5] == ["-", "-", "-"]
    assert "0" not in "".join(row[2:5])


def test_request_block_excludes_not_called_lines(tmp_path):
    path = _write_log(tmp_path, [
        dict(GATEWAY, call_id="a", request_id="rq1"),
        dict(NOT_CALLED, call_id="b", request_id="rq1"),
        dict(NOT_CALLED, call_id="c", request_id="rq2"),
    ])
    _, out = _run([str(path)])
    assert _request_row(out, "rq1")[1] == "1"
    with pytest.raises(AssertionError):
        _request_row(out, "rq2")


def test_request_block_single_call_request(tmp_path):
    path = _write_log(tmp_path, [dict(GATEWAY, call_id="a", request_id="rq1")])
    _, out = _run([str(path)])
    assert _request_row(out, "rq1")[1] == "1"


def test_existing_blocks_unchanged(tmp_path):
    path = _write_log(tmp_path, [GATEWAY, PARTIAL, MISSING, NOT_CALLED])
    _, out = _run([str(path)])
    assert out.count("== Per call (per actual API call) ==") == 1
    assert out.count("== Per session ==") == 1
    for name in ("total_api_calls", "usage_complete_calls", "usage_missing_calls",
                 "usage_partial_calls", "not_called_calls"):
        assert out.count(name) == 1, name


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


def _stub_extract(monkeypatch, outcomes):
    """Replace call_llm.extract with a scripted sequence of results."""
    from src import call_llm

    calls = []
    sequence = list(outcomes)

    def fake_extract(text, request_id=None):
        calls.append(text)
        outcome = sequence.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return {"amount": 1, "category": "food"}

    monkeypatch.setattr(call_llm, "extract", fake_extract)
    return calls


def _run_latency(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = measure_latency.main(argv)
    return code, buf.getvalue()


def test_latency_failures_do_not_end_the_run(tmp_path, monkeypatch):
    from src import call_llm

    monkeypatch.setattr(measure_latency, "LATENCY_PATH", tmp_path / "latency.jsonl")
    err = call_llm.LlmTransportError("transport: read timed out (read timeout=30)")
    _stub_extract(monkeypatch, [err, err, {}, {}, {}, {}])
    code, out = _run_latency(["--n", "6"])
    assert code == 0
    assert "attempted=6 ok=4 failed=2 failure_rate=0.33" in out
    assert "failures: 2 x transport: read timeout (LlmTransportError)" in out


def test_latency_counts_json_decode_error_as_failure(tmp_path, monkeypatch):
    err = json.JSONDecodeError("bad", "not json", 0)
    monkeypatch.setattr(measure_latency, "LATENCY_PATH", tmp_path / "latency.jsonl")
    _stub_extract(monkeypatch, [err, {}, {}, {}, {}, {}])
    _, out = _run_latency(["--n", "6"])
    assert "failed=1" in out
    assert "failures: 1 x not_json" in out


def test_latency_percentiles_use_successes_only(tmp_path, monkeypatch):
    from src import call_llm

    monkeypatch.setattr(measure_latency, "LATENCY_PATH", tmp_path / "latency.jsonl")
    err = call_llm.LlmTransportError("transport: read timed out")
    _stub_extract(monkeypatch, [{}, {}, err, {}, err])
    _, out = _run_latency(["--n", "5"])
    assert "p50_ms=" in out and "(n=3)" in out
    assert "p95_ms=" in out and "(n=3)" in out
    assert "(n=5)" not in out


def test_latency_exits_2_when_nothing_succeeded(tmp_path, monkeypatch):
    from src import call_llm

    monkeypatch.setattr(measure_latency, "LATENCY_PATH", tmp_path / "latency.jsonl")
    err = call_llm.LlmTransportError("transport: read timed out")
    _stub_extract(monkeypatch, [err, err, err])
    code, out = _run_latency(["--n", "3"])
    assert code == 2
    assert "no successful samples; percentiles not reported" in out
    assert "p50_ms" not in out
    assert not (tmp_path / "latency.jsonl").exists()


def test_latency_low_confidence_line(tmp_path, monkeypatch):
    monkeypatch.setattr(measure_latency, "LATENCY_PATH", tmp_path / "latency.jsonl")
    _stub_extract(monkeypatch, [{}, {}, {}])
    _, out = _run_latency(["--n", "3"])
    assert "low_confidence: only 3 successful samples" in out


def test_latency_no_low_confidence_when_five_or_more(tmp_path, monkeypatch):
    monkeypatch.setattr(measure_latency, "LATENCY_PATH", tmp_path / "latency.jsonl")
    _stub_extract(monkeypatch, [{}, {}, {}, {}, {}, {}])
    _, out = _run_latency(["--n", "6"])
    assert "low_confidence" not in out


def test_latency_failure_tally_carries_no_secrets(tmp_path, monkeypatch):
    from src import call_llm

    monkeypatch.setattr(measure_latency, "LATENCY_PATH", tmp_path / "latency.jsonl")
    err = call_llm.LlmTransportError(
        "transport: read timed out connecting to https://gw.example/v1?key=sk-secret"
    )
    _stub_extract(monkeypatch, [err])
    _, out = _run_latency(["--n", "1"])
    assert "sk-secret" not in out
    assert "https://" not in out
    assert "failures: 1 x transport: read timeout (LlmTransportError)" in out


def test_failure_kind_whitelist_shapes():
    from src import call_llm

    http = call_llm.LlmTransportError("http 503: secret body", status_code=503,
                                      body="sk-secret and https://host/x")
    assert measure_latency._failure_kind(http) == "http 503 (LlmTransportError)"
    refused = call_llm.LlmTransportError("transport: refused https://h/sk-secret")
    assert measure_latency._failure_kind(refused) == "transport: other (LlmTransportError)"
    resolved = call_llm.LlmTransportError(
        "transport: temporary failure in name resolution"
    )
    assert measure_latency._failure_kind(resolved) == \
        "transport: name resolution (LlmTransportError)"
    not_json = json.JSONDecodeError("x", "sk-secret", 0)
    assert measure_latency._failure_kind(not_json) == "not_json"


def test_latency_dry_run_does_not_call_extract(tmp_path, monkeypatch):
    monkeypatch.setattr(measure_latency, "LATENCY_PATH", tmp_path / "logs" / "latency.jsonl")
    called = _stub_extract(monkeypatch, [{} for _ in range(5)])
    code, out = _run_latency(["--dry-run", "--n", "5"])
    assert code == 0
    assert called == []
    assert not (tmp_path / "logs").exists()


def _run_tokens(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = measure_tokens.main(argv)
    return code, buf.getvalue()


def test_token_corpus_has_at_least_twenty_sentences():
    assert len(measure_tokens.CORPUS) >= 20


def test_token_corpus_has_at_least_eight_distinct_lengths():
    assert len({len(s) for s in measure_tokens.CORPUS}) >= 8


def test_token_dry_run_does_not_call_extract(monkeypatch, capsys):
    called = _stub_extract(monkeypatch, [{} for _ in range(5)])
    code, out = _run_tokens(["--dry-run"])
    assert code == 0
    assert "dry-run" in out
    assert str(len(measure_tokens.CORPUS)) in out
    assert called == []


def test_token_mixed_run_counts_failures_and_does_not_stop(monkeypatch):
    from src import call_llm

    err = call_llm.LlmTransportError("transport: read timed out (read timeout=30)")
    called = _stub_extract(monkeypatch, [err, {}, {}, err, {}])
    code, out = _run_tokens(["--n", "5"])
    assert code == 0
    assert len(called) == 5
    assert "attempted=5 ok=3 failed=2 failure_rate=0.40" in out
    assert "failures: 2 x transport: read timeout (LlmTransportError)" in out
    assert "next: run `python -m src.report_tokens`" in out


def test_token_all_fail_run_returns_two(monkeypatch):
    from src import call_llm

    err = call_llm.LlmTransportError("transport: read timed out")
    _stub_extract(monkeypatch, [err, err, err])
    code, out = _run_tokens(["--n", "3"])
    assert code == 2
    assert "ok=0" in out
    assert "no successful samples" in out
    assert "next: run `python -m src.report_tokens`" not in out


def test_token_file_corpus_cycles_when_n_exceeds_size(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus.txt"
    corpus.write_text("alpha 1\nbeta 2.5\ngamma 3\n", encoding="utf-8")
    called = _stub_extract(monkeypatch, [{} for _ in range(6)])
    code, out = _run_tokens(["--file", str(corpus), "--n", "6"])
    assert code == 0
    assert called == ["alpha 1", "beta 2.5", "gamma 3",
                      "alpha 1", "beta 2.5", "gamma 3"]
    assert "attempted=6 ok=6 failed=0 failure_rate=0.00" in out


def test_token_dry_run_reads_file_corpus_without_calling(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus.txt"
    corpus.write_text("alpha 1\nbeta 2\n", encoding="utf-8")
    called = _stub_extract(monkeypatch, [{}])
    code, out = _run_tokens(["--file", str(corpus), "--dry-run"])
    assert code == 0
    assert "2 sentence(s)" in out
    assert called == []


def test_failure_kind_label_never_carries_secrets():
    from src import call_llm

    err = call_llm.LlmTransportError(
        "transport: read timed out to https://gw.example/v1?key=sk-secret"
    )
    label = measure_tokens._failure_kind(err)
    assert label == "transport: read timeout (LlmTransportError)"
    assert "sk-secret" not in label
    assert "https://" not in label
    assert label == measure_latency._failure_kind(err)


def _evidence_paths():
    return {
        "call_llm.LOG_PATH": call_llm.LOG_PATH,
        "pipeline.REVIEW_PATH": pipeline.REVIEW_PATH,
        "storage.DATA_PATH": storage.DATA_PATH,
        "measure_latency.LATENCY_PATH": measure_latency.LATENCY_PATH,
        "report_tokens.LOG_PATH": report_tokens.LOG_PATH,
    }


def test_evidence_path_constants_point_at_distinct_files():
    """Distinct owners name distinct files; report_tokens shares llm_calls.jsonl.

    The filter below assumes keys are "<module>.<CONST>"; the premise is
    asserted so a future key rename cannot silently degrade the scoped count.
    """
    paths = _evidence_paths()
    assert len(paths) == 5 and all("." in k for k in paths)
    owners = {k: v for k, v in paths.items()
              if not k.startswith("report_tokens.")}
    assert len(owners) == 4
    assert len({str(p) for p in owners.values()}) == 4


def test_evidence_paths_are_absolute_and_inside_repo():
    repo = pathlib.Path(__file__).resolve().parents[2]
    for name, path in _evidence_paths().items():
        assert path.is_absolute(), "%s is not absolute: %r" % (name, path)
        assert str(path).startswith(str(repo)), "%s escapes repo: %r" % (name, path)


def test_evidence_paths_follow_the_module_not_the_cwd(tmp_path):
    repo = pathlib.Path(__file__).resolve().parents[2]
    code = (
        "from src import call_llm, pipeline, storage, measure_latency, report_tokens;"
        "print(call_llm.LOG_PATH); print(pipeline.REVIEW_PATH);"
        "print(storage.DATA_PATH); print(measure_latency.LATENCY_PATH);"
        "print(report_tokens.LOG_PATH)"
    )
    env = dict(os.environ, PYTHONPATH=str(repo))
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=str(tmp_path),
        capture_output=True, text=True, env=env, check=True,
    )
    printed = out.stdout.split()
    assert len(printed) == 5, out.stdout
    for line in printed:
        assert line.startswith(str(repo)), "%r does not follow the module" % (line,)
        assert not line.startswith(str(tmp_path)), "%r follows the cwd" % (line,)


_RELATIVE_EVIDENCE_LITERALS = tuple(
    ctor + "(" + quote + prefix
    for ctor in ("pathlib.Path", "Path")
    for quote in ('"', "'")
    for prefix in ("logs", "data")
)


def test_no_relative_evidence_path_literal_in_src():
    """No src module may build an evidence path from a cwd-relative literal.

    Every owning module is anchored (_REPO_ROOT / ...), so a relative literal is
    illegal everywhere and there is no allow-list. Scope, honestly: this catches
    relative literals for "logs"/"data" only; a future Path("prompts/...") would
    not be caught — adding such a prefix here is a deliberate test change.
    """
    src = pathlib.Path(__file__).resolve().parents[2] / "src"
    offenders = []
    for path in sorted(src.glob("*.py")):
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if any(literal in line for literal in _RELATIVE_EVIDENCE_LITERALS):
                offenders.append("%s:%d: relative evidence path literal"
                                 % (path.name, lineno))
    assert not offenders, "\n".join(offenders)


def test_report_tokens_log_path_matches_call_llm():
    assert report_tokens.LOG_PATH == call_llm.LOG_PATH
