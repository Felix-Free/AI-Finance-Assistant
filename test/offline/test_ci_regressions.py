"""Targeted offline regressions for the GitHub #20 review (owner: role E): Gate 1 must reject a docs-only approval, and the offline budget node must not touch runtime paths."""
from __future__ import annotations

import os
import pathlib
import runpy
import shutil
import subprocess
import sys

import pytest
import yaml

pytestmark = pytest.mark.offline

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CI_CHECKS = REPO_ROOT / ".github" / "ci_checks.py"
CI_YAML = REPO_ROOT / ".github" / "workflows" / "ci.yml"

INVARIANTS_NODE = (
    "test/offline/test_invariants.py::test_inv003_rejects_one_cent_over_budget"
)

# Distinct, explicit UTC author/committer times (fixture only) so the synthetic
# review can be ordered strictly after a commit and before the implementation.
_BASE_TIME = "2026-11-16T00:00:00+00:00"
_TEST_TIME = "2026-11-16T01:00:00+00:00"
_DOCS_TIME = "2026-11-16T02:00:00+00:00"
_IMPL_TIME = "2026-11-16T04:00:00+00:00"
_REVIEW_SUBMITTED = "2026-11-16T03:00:00Z"

_GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "CI Fixture",
    "GIT_AUTHOR_EMAIL": "ci-fixture@example.invalid",
    "GIT_COMMITTER_NAME": "CI Fixture",
    "GIT_COMMITTER_EMAIL": "ci-fixture@example.invalid",
}


def _git(repo, args, when):
    """Run one git command with an explicit identity and UTC date."""
    env = dict(os.environ)
    env.update(_GIT_IDENTITY)
    env["GIT_AUTHOR_DATE"] = when
    env["GIT_COMMITTER_DATE"] = when
    result = subprocess.run(
        ["git"] + list(args),
        cwd=str(repo),
        env=env,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def _write(repo, relpath, text):
    target = repo / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _commit(repo, message, when):
    _git(repo, ["add", "-A"], when)
    _git(repo, ["commit", "-q", "-m", message], when)
    return _git(repo, ["rev-parse", "HEAD"], when)


@pytest.fixture
def git_history(tmp_path):
    """A real linear repo: base -> test-only -> docs-only -> implementation."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, ["init", "-q"], _BASE_TIME)

    _write(repo, "README.md", "fixture\n")
    base = _commit(repo, "base", _BASE_TIME)

    _write(
        repo,
        "test/test_feature.py",
        "def test_new_behaviour():\n    assert True\n",
    )
    test_only = _commit(repo, "test only", _TEST_TIME)

    _write(repo, "docs/notes.md", "# notes\n")
    docs_only = _commit(repo, "docs only", _DOCS_TIME)

    _write(repo, "src/widget.py", "VALUE = 1\n")
    impl = _commit(repo, "implementation", _IMPL_TIME)

    return {
        "repo": repo,
        "base": base,
        "docs_only": docs_only,
        "test_only": test_only,
        "impl": impl,
    }


def _run_gate(history, target_sha, base=None, head=None, submitted_at=None):
    module = runpy.run_path(str(CI_CHECKS))
    gate = module["gate_test_approval"]
    env = {
        "BASE_SHA": base if base is not None else history["base"],
        "PR_HEAD_SHA": head if head is not None else history["impl"],
        "PR_AUTHOR": "original-author",
        "GH_TOKEN": "",
    }
    reviews = [
        {
            "id": 1,
            "user": {"login": "reviewer-member"},
            "author_association": "MEMBER",
            "state": "APPROVED",
            "commit_id": target_sha,
            "submitted_at": submitted_at or _REVIEW_SUBMITTED,
        }
    ]
    return gate(env, reviews=reviews, git_cwd=str(history["repo"]))


@pytest.mark.parametrize(
    "target_key,expected",
    [
        ("docs_only", 1),  # BUG-01: docs-only approval must be rejected
        ("test_only", 0),  # companion: same shape on a real test commit passes
    ],
    ids=["docs-only-rejected", "test-only-accepted"],
)
def test_gate1_rejects_docs_only_approval(git_history, target_key, expected):
    """Gate 1 accepts only a real test-first commit, never a docs-only one (BUG-01)."""
    result = _run_gate(git_history, git_history[target_key])
    assert result == expected


# ---------------------------------------------------------------------------
# BUG-02: the offline budget node must not touch runtime paths
# ---------------------------------------------------------------------------

_SENTINELS = {
    "logs/llm_calls.jsonl": '{"input": "seed", "parsed": null}\n',
    "logs/review.jsonl": '{"error": "policy:budget", "review": true}\n',
    "data/records.jsonl": '{"call_id": "seed0001", "amount": 990}\n',
}

_SITECUSTOMIZE = '''\
import socket


def _blocked(*args, **kwargs):
    raise OSError("network access is blocked in this offline regression")


socket.getaddrinfo = _blocked
socket.create_connection = _blocked
socket.socket.connect = _blocked
socket.socket.connect_ex = _blocked
'''


def _snapshot(*roots):
    """Map relative path -> bytes for every file under the given roots."""
    snap = {}
    for root in roots:
        base = pathlib.Path(root)
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                snap[path.relative_to(base.parent).as_posix()] = path.read_bytes()
    return snap


def _build_mini_checkout(dest):
    """Copy the tracked src tree, the invariants node and pytest.ini into dest."""
    src_src = REPO_ROOT / "src"
    src_dest = dest / "src"
    for path in sorted(src_src.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(src_src)
        target = src_dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(path), str(target))

    inv_dest = dest / "test" / "offline" / "test_invariants.py"
    inv_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        str(REPO_ROOT / "test" / "offline" / "test_invariants.py"),
        str(inv_dest),
    )

    shutil.copyfile(str(REPO_ROOT / "pytest.ini"), str(dest / "pytest.ini"))

    (dest / "sitecustomize.py").write_text(_SITECUSTOMIZE, encoding="utf-8")


def test_budget_regression_leaves_runtime_paths_unchanged(tmp_path):
    """The offline budget node runs offline in a copy and mutates no runtime file (BUG-02)."""
    copy = tmp_path / "mini"
    copy.mkdir()
    _build_mini_checkout(copy)

    for relpath, content in _SENTINELS.items():
        target = copy / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    runtime_roots = [copy / "logs", copy / "data"]
    before = _snapshot(*runtime_roots)

    env = dict(os.environ)
    env["PYTHONPATH"] = str(copy) + os.pathsep + env.get("PYTHONPATH", "")
    env.pop("LLM_API_KEY", None)
    env.pop("LLM_BASE_URL", None)
    env.pop("LLM_MODEL", None)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", INVARIANTS_NODE, "-q", "-p", "no:cacheprovider"],
        cwd=str(copy),
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    combined = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, combined
    assert "1 passed" in combined, combined

    after = _snapshot(*runtime_roots)
    assert after == before
    assert set(after) == set(_SENTINELS)


def test_gate1_pr20_waiver(tmp_path):
    """PR #20 waiver: pinned ci.yml expression + real step shell (no expression engine emulation)."""
    step = next(
        step
        for step in yaml.safe_load(CI_YAML.read_text(encoding="utf-8"))["jobs"][
            "test-approval-loop"
        ]["steps"]
        if step.get("id") == "gate"
    )
    expression = step["env"]["FIRST_ROLLOUT_WAIVER"]
    expected_expression = (
        "${{ github.repository == 'Felix-Free/AI-Finance-Assistant' "
        "&& github.event.pull_request.number == 20 "
        "&& contains(github.event.pull_request.labels.*.name, 'skip-test-gate') }}"
    )
    assert " ".join(expression.split()) == " ".join(expected_expression.split())

    if os.name == "nt":
        exec_path = subprocess.run(
            ["git", "--exec-path"], check=True, capture_output=True, text=True
        ).stdout.strip()
        bash = str(pathlib.Path(exec_path).parents[2] / "bin" / "bash.exe")
    else:
        bash = shutil.which("bash")
    assert bash and pathlib.Path(bash).is_file(), "bash not found (WORKFLOWS REQUIRE A UNIX SHELL)"

    waived = "Gate 1: Waived (one-time first rollout of PR #20)"
    stub = "python() { printf '%s\\n' 'normal approval invoked'; return 7; }\n"
    for flag, code, line in [("true", 0, waived), ("false", 7, "normal approval invoked")]:
        summary = tmp_path / ("summary-" + flag)
        summary.write_text("", encoding="utf-8")
        env = dict(os.environ, BASH_ENV="", FIRST_ROLLOUT_WAIVER=flag,
                   GITHUB_STEP_SUMMARY=summary.as_posix())
        result = subprocess.run(
            [bash, "--noprofile", "--norc", "-s"],
            input=stub + step["run"] + "\n",
            env=env,
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        diagnostic = (result.stdout or "") + (result.stderr or "")
        assert result.returncode == code, diagnostic
        assert (result.stdout or "").strip() == line, diagnostic
        assert summary.read_text(encoding="utf-8").strip() == (
            waived if flag == "true" else ""
        )


# ---------------------------------------------------------------------------
# Gate 1: upstream-sync and post-approval test-edit histories (real repos)
# ---------------------------------------------------------------------------

_SYNC_TIME = "2026-11-16T05:00:00+00:00"
_MERGE_TIME = "2026-11-16T06:00:00+00:00"
_WEAKEN_TIME = "2026-11-16T07:00:00+00:00"
_LATE_REVIEW = "2026-11-16T08:00:00+00:00"


@pytest.mark.parametrize(
    "path,expected",
    [
        ("test/test_upstream.py", 0),  # clean sync adds a different test file
        ("test/test_feature.py", 1),  # add/add conflict resolved to upstream
    ],
    ids=["clean-sync-accepted", "conflict-rejected"],
)
def test_gate1_upstream_sync(git_history, path, expected):
    """Upstream sync of only tests: a clean add passes, a conflict drop fails."""
    repo = git_history["repo"]
    _git(repo, ["branch", "feature", git_history["impl"]], _SYNC_TIME)
    _git(repo, ["checkout", "-q", "-b", "upstream", git_history["base"]], _SYNC_TIME)
    _write(repo, path, "def test_upstream_only():\n    assert True\n")
    up = _commit(repo, "upstream tests", _SYNC_TIME)
    _git(repo, ["checkout", "-q", "feature"], _MERGE_TIME)

    if path == "test/test_feature.py":
        with pytest.raises(subprocess.CalledProcessError) as exc:
            _git(repo, ["merge", "--no-ff", "--no-commit", "upstream"], _MERGE_TIME)
        assert exc.value.returncode == 1
        unmerged = _git(repo, ["diff", "--name-only", "--diff-filter=U"], _MERGE_TIME)
        assert path in unmerged
        _git(repo, ["checkout", "--theirs", path], _MERGE_TIME)
        merge_head = _commit(repo, "resolve conflict", _MERGE_TIME)
    else:
        _git(repo, ["merge", "-q", "--no-ff", "--no-edit", "upstream"], _MERGE_TIME)
        merge_head = _git(repo, ["rev-parse", "HEAD"], _MERGE_TIME)

    result = _run_gate(
        git_history, git_history["test_only"], base=up, head=merge_head
    )
    assert result == expected


def test_gate1_post_approval_test_edit_rejected(git_history, capsys):
    """Editing the approved assertion after implementation is rejected."""
    repo = git_history["repo"]
    _write(repo, "test/test_feature.py",
           "def test_new_behaviour():\n    pass\n")
    head = _commit(repo, "weaken approved test", _WEAKEN_TIME)

    assert _run_gate(git_history, git_history["test_only"], head=head) == 1
    out = capsys.readouterr().out
    assert "test/test_feature.py" in out


def test_gate1_review_after_implementation_rejected(git_history, capsys):
    """An approval submitted after the implementation commit is too late."""
    assert _run_gate(
        git_history,
        git_history["test_only"],
        submitted_at=_LATE_REVIEW,
    ) != 0
    text = capsys.readouterr().out.lower()
    assert any(word in text for word in ("late", "before", "after", "timing")), text


def test_gate1_no_approval_rejected(git_history, capsys):
    """No valid reviewer approval is rejected with a no-review message."""
    module = runpy.run_path(str(CI_CHECKS))
    env = {
        "BASE_SHA": git_history["base"],
        "PR_HEAD_SHA": git_history["impl"],
        "PR_AUTHOR": "original-author",
        "GH_TOKEN": "fixture-only",
    }
    result = module["gate_test_approval"](
        env, reviews=[], git_cwd=str(git_history["repo"])
    )
    assert result != 0
    assert "no valid" in capsys.readouterr().out.lower()
