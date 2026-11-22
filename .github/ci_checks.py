#!/usr/bin/env python3
"""CI merge gates for the AI Finance Assistant (owner: role E).

Six independently invocable checks. The workflow in
``.github/workflows/ci.yml`` owns *orchestration* (checkout depth, offline /
schema / live test runs, model-config checks); this helper owns the *merge
gate logic* only. A non-zero exit blocks the merge.

Subcommands
-----------
  test-approval    Gate 1  - real approval on a test-first commit
  static-analysis  Gate 2  - single model entry point, API shape, permissions, ADR
  secret-scan      credential-like tracked file paths only (never reads a key)
  semantic-scope   flags model / prompt / eval / workflow changes
  ai-use-log       Gate 6  - AI-use log keeps old rows, appends new sessions

Environment (read-only inputs, never echoed verbatim):
  BASE_SHA, PR_HEAD_SHA, GH_TOKEN, PR_NUMBER, PR_AUTHOR,
  GITHUB_API_URL, GITHUB_REPOSITORY, GITHUB_OUTPUT

Design notes
------------
* Network (the reviews API) lives only in ``fetch_reviews`` and is skipped
  when ``GH_TOKEN`` is empty, so unit tests never touch the wire.
* Python 3.9 compatible; only the standard library and PyYAML are used.
* Secrets: only *paths* are reported. File contents are never printed and
  ``.env`` is never opened.
"""
from __future__ import annotations

import ast
import datetime
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is an approved dependency
    yaml = None

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

MODEL_ENTRY = "src/call_llm.py"


TRANSPORT_MODULES = ("requests", "httpx", "aiohttp", "urllib.request", "http.client", "socket")

CRITICAL_FILES = frozenset({
    "src/call_llm.py",
    "src/policy_core.py",
    "src/pipeline.py",
    "src/storage.py",
    ".github/ci_checks.py",
    ".github/workflows/ci.yml",
    ".github/workflows/branch-ci.yml",
})

CRITICAL_PREFIXES = ("docs/architecture/adr/",)

PERMISSION_EDIT_DENY = (
    ".env",
    ".github/",
    ".agent/",
    ".opencode/",
    "docs/req/",
    "logs/",
    "transcripts/",
)

FORBIDDEN_BASH = (
    "git push",
    "git commit",
    "git reset --hard",
    "git clean",
    "rm -rf",
)

CREDENTIAL_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(
        r"(?i)(?:api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{12,}['\"]"
    ),
)

NEVER_READ_NAMES = (".env", "agent.env")

AI_LOG_PATH = "docs/ai-use-log.yaml"
AI_LOG_KEY_FIELDS = ("student_id", "phase", "session")

# Changes that require a new AI-use-log session.
AI_LOG_TRIGGER_PREFIXES = ("src/", "test/", "prompts/", ".github/", "scripts/")
AI_LOG_TRIGGER_FILES = frozenset({"requirements.txt", "Prompt.md", "pytest.ini"})


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _env(name):
    value = os.environ.get(name, "")
    return value.strip() if isinstance(value, str) else ""


def _fail(message):
    print("FAIL: %s" % message)
    return EXIT_FAIL


def _ok(message):
    print("OK: %s" % message)
    return EXIT_OK


def _norm(path):
    return path.replace("\\", "/")


def _is_test_path(path):
    norm = _norm(path)
    parts = norm.split("/")
    name = parts[-1]
    if not name.endswith(".py"):
        return False
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    return any(p in ("test", "tests") for p in parts[:-1])


def _is_python(path):
    return _norm(path).endswith(".py")


def _is_impl_path(path):
    return _is_python(path) and not _is_test_path(path)


# ---------------------------------------------------------------------------
# git helpers (read-only)
# ---------------------------------------------------------------------------
def git(args, cwd=None):
    proc = subprocess.run(
        ["git"] + list(args), cwd=cwd, check=False, capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), proc.stderr.strip()))
    return proc.stdout


def _is_ancestor(ancestor, descendant, cwd=None):
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=cwd, check=False, capture_output=True, text=True,
    )
    return proc.returncode == 0


def _blob(rev, path, cwd=None):
    try:
        return git(["show", "%s:%s" % (rev, path)], cwd)
    except RuntimeError:
        return None


def _diff_files(base, rev, cwd=None):
    out = git(["diff", "--name-only", "--no-renames", base + "..." + rev], cwd)
    return [p for p in out.splitlines() if p.strip()]


def _parse_time(value):
    """Parse an ISO-8601 time (git %cI or GitHub ``...Z``) to an aware datetime."""
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _commit_time(rev, cwd=None):
    return _parse_time(git(["show", "-s", "--format=%cI", rev], cwd).strip())


def _parents(rev, cwd=None):
    return git(["rev-list", "--parents", "-n", "1", rev], cwd).split()[1:]


def _topo_commits(base, head, cwd=None):
    """Commits in base..head, in topological order (parents before children)."""
    out = git(["rev-list", "--topo-order", "--reverse", base + ".." + head], cwd)
    return [line for line in out.splitlines() if line.strip()]


def _commit_diff_paths(commit, cwd=None):
    """Paths ``commit`` changes vs its single parent, or merge ``--cc`` paths."""
    parents = _parents(commit, cwd)
    if len(parents) > 1:
        out = git(
            ["diff-tree", "--no-commit-id", "--name-only", "-r", "--cc", commit],
            cwd,
        )
    else:
        diff_base = parents[0] if parents else "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        out = git(["diff", "--name-only", "--no-renames", diff_base, commit], cwd)
    return sorted({p.split("\t")[-1] for p in out.splitlines() if p.strip()})


def _test_defs_in(text):
    """Map (kind, name) -> AST dump of each real pytest definition in a blob.

    Only ``test_*.py`` / ``*_test.py`` sources are parsed (caller filters).
    A ``Test*`` class with no ``test*`` methods contributes nothing.
    """
    if not text:
        return {}
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    found = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test"):
            found[("function", node.name)] = ast.dump(node)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name.startswith("test"):
                    found[("method", node.name + "." + child.name)] = ast.dump(child)
    return found


def _test_file(path):
    """True only for files pytest would collect: test_*.py or *_test.py."""
    name = _norm(path).split("/")[-1]
    return name.endswith(".py") and (
        name.startswith("test_") or name.endswith("_test.py")
    )


def _approved_test_defs(parent, commit, path, cwd):
    """Definitions added or body-changed in ``path``; deletions excluded."""
    after = _test_defs_in(_blob(commit, path, cwd))
    before = _test_defs_in(_blob(parent, path, cwd)) if parent else {}
    result = set()
    for key, dump in after.items():
        if key not in before or before[key] != dump:
            result.add(key)
    return result


def _test_changes_at(commit, cwd=None):
    """Path -> approved definitions for a single-parent test-only commit."""
    parents = _parents(commit, cwd)
    parent = parents[0] if parents else ""
    diff_base = parent or "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    changes = {}
    for path in _diff_files(diff_base, commit, cwd):
        if not _test_file(path) or _is_impl_path(path):
            continue
        approved = _approved_test_defs(parent, commit, path, cwd)
        if approved:
            changes[path] = approved
    return changes


def _changed_paths(parent, commit, cwd):
    out = git(
        ["diff", "--name-only", "-z", "--no-renames", parent, commit],
        cwd,
    )
    return [p for p in out.split("\x00") if p]


def _test_tree_entry(rev, path, cwd):
    return git(
        ["--literal-pathspecs", "ls-tree", "-z", rev, "--", path],
        cwd,
    )


def _post_approval_test_problem(sha, head, base, cwd=None):
    chain = git(["rev-list", "--first-parent", head], cwd).split()
    if sha not in chain:
        return ("<approval outside first-parent history>", head)
    for commit in chain:
        if commit == sha:
            break
        parents = _parents(commit, cwd)
        tests = [p for p in _changed_paths(parents[0], commit, cwd) if _is_test_path(p)]
        if not tests:
            continue
        if len(parents) != 2 or not _is_ancestor(parents[1], base, cwd):
            return (tests[0], commit)
        bases = git(["merge-base", "--all", parents[0], parents[1]], cwd).split()
        if len(bases) != 1:
            return (tests[0], commit)
        for path in tests:
            if _test_tree_entry(parents[0], path, cwd) != _test_tree_entry(bases[0], path, cwd):
                return (path, commit)
            if _test_tree_entry(commit, path, cwd) != _test_tree_entry(parents[1], path, cwd):
                return (path, commit)
    return None


# ---------------------------------------------------------------------------
# reviews / approvals
# ---------------------------------------------------------------------------
def _login(review):
    user = review.get("user") or {}
    return (user.get("login") if isinstance(user, dict) else "") or ""


MEMBER_ASSOCIATIONS = ("OWNER", "MEMBER", "COLLABORATOR")


def valid_approvals(reviews, pr_author):
    """Effective APPROVED reviews per reviewer, kept across SHAs.

    Only OWNER/MEMBER/COLLABORATOR, non-author reviewers count. Reviews are
    ordered by GitHub review ``id`` (falling back to submission time). Each
    APPROVED review with a non-empty commit SHA is retained even after later
    COMMENTED or APPROVED reviews; a later CHANGES_REQUESTED or DISMISSED
    review invalidates that reviewer's earlier approvals.
    """
    def _order(review):
        review_id = review.get("id")
        if isinstance(review_id, int):
            return (0, review_id)
        stamped = _parse_time(review.get("submitted_at") or "")
        if stamped is not None:
            return (0, stamped.timestamp())
        return (1, 0)

    ordered = sorted(
        (r for r in reviews if isinstance(r, dict)),
        key=_order,
    )
    approvals = {}
    for review in ordered:
        login = _login(review).lower()
        if not login:
            continue
        if pr_author and login == pr_author.lower():
            continue
        if review.get("author_association") not in MEMBER_ASSOCIATIONS:
            continue
        state = review.get("state")
        if state == "APPROVED":
            if review.get("dismissed") in (True, "true"):
                continue
            if not (review.get("commit_id") or "").strip():
                continue
            approvals.setdefault(login, []).append(review)
        elif state in ("CHANGES_REQUESTED", "DISMISSED"):
            approvals.pop(login, None)
    result = []
    for rows in approvals.values():
        result.extend(rows)
    return result


def fetch_reviews(api_url, repo, pr_number, token):
    """Fetch *all* PR reviews across pages; [] when unauthenticated."""
    if not token or not api_url or not repo or not pr_number:
        return []
    base = "%s/repos/%s/pulls/%s/reviews" % (
        api_url.rstrip("/"), repo.strip("/"), str(pr_number).strip(),
    )
    reviews = []
    page = 1
    while True:
        query = urllib.parse.urlencode({"per_page": 100, "page": page})
        request = urllib.request.Request(
            "%s?%s" % (base, query),
            headers={
                "Authorization": "token %s" % token,
                "Accept": "application/vnd.github+json",
                "User-Agent": "ci-checks",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            raise RuntimeError("reviews API HTTP %s" % exc.code) from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network
            raise RuntimeError("reviews API unreachable: %s" % exc.reason) from exc
        if not isinstance(payload, list) or not payload:
            break
        reviews.extend(payload)
        if len(payload) < 100:
            break
        page += 1
    return reviews


# ---------------------------------------------------------------------------
# Gate 1: test-approval
# ---------------------------------------------------------------------------
def gate_test_approval(env, *, reviews=None, git_cwd=None):
    base = env.get("BASE_SHA", "").strip()
    head = env.get("PR_HEAD_SHA", "").strip()
    pr_author = env.get("PR_AUTHOR", "").strip()
    if not base:
        return _fail("BASE_SHA is empty")
    if not head:
        return _fail("PR_HEAD_SHA is empty")

    commits = _topo_commits(base, head, git_cwd)
    impl_commits = [c for c in commits
                    if any(_is_impl_path(p) for p in _commit_diff_paths(c, git_cwd))]
    if not impl_commits:
        return _ok("no implementation changes; test-approval not triggered")

    if reviews is None:
        reviews = fetch_reviews(
            env.get("GITHUB_API_URL", ""), env.get("GITHUB_REPOSITORY", ""),
            env.get("PR_NUMBER", ""), env.get("GH_TOKEN", ""),
        )
    if not env.get("GH_TOKEN", "").strip() and not reviews:
        return _fail("no GH_TOKEN and no reviews supplied (real approvals required)")

    approvals = valid_approvals(reviews, pr_author)
    if not approvals:
        return _fail("no valid non-author, member approval")

    first_impl_time = min(_commit_time(c, git_cwd) for c in impl_commits)
    commit_set = set(commits)
    timing_reason = ""

    for review in approvals:
        sha = (review.get("commit_id") or "").strip()
        submitted = _parse_time(review.get("submitted_at") or "")
        if sha not in commit_set or submitted is None:
            continue
        if len(_parents(sha, git_cwd)) != 1:
            continue
        if not _test_changes_at(sha, git_cwd):
            continue
        if any(_is_impl_path(p) for p in _commit_diff_paths(sha, git_cwd)):
            continue
        if not all(_is_ancestor(sha, c, git_cwd) for c in impl_commits):
            continue
        if not _commit_time(sha, git_cwd) <= submitted < first_impl_time:
            reason = (
                "late review on %s submitted %s but must be before first "
                "implementation %s"
                % (sha[:12], submitted.isoformat(), first_impl_time.isoformat())
            )
            timing_reason = timing_reason or reason
            continue
        problem = _post_approval_test_problem(sha, head, base, git_cwd)
        if problem is not None:
            path, commit = problem
            reason = (
                "test path changed after approved commit %s: %s in %s"
                % (sha[:12], path, commit[:12])
            )
            timing_reason = timing_reason or reason
            continue
        return _ok("test-first approval verified at %s" % sha[:12])

    if timing_reason:
        return _fail(timing_reason)
    return _fail(
        "no approval on a qualified test-first commit (approved %s, "
        "a test path changed or approval timing/ancestry failed)"
        % (sorted(a.get("commit_id", "")[:12] for a in approvals) or "none")
    )


# ---------------------------------------------------------------------------
# Gate 2: static-analysis
# ---------------------------------------------------------------------------
def _toplevel_imports(text):
    """Top-level and in-function import module names."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.add(module)
            for alias in node.names:
                names.add(module + "." + alias.name if module else alias.name)
    return names


def _imports_transport(names):
    for name in names:
        for module in TRANSPORT_MODULES:
            if name == module or name.startswith(module + "."):
                return module
    return ""


def _signature(text, func):
    """Return (positional_names, keyword_names, required_count, required_kwonly)
    of a top-level ``def func``.

    Positional-only params (``/``) are excluded from ``keyword_names`` so a
    caller cannot pass them by keyword. ``required_count`` is the number of
    mandatory positional parameters (total positionals minus those with
    defaults); ``required_kwonly`` lists keyword-only parameters that have no
    default. Returns ``None`` when not found. The first two tuple items are kept
    unchanged for existing callers.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == func:
            args = node.args
            all_positional = args.posonlyargs + args.args
            positional = [a.arg for a in all_positional]
            keyword = [a.arg for a in args.args + args.kwonlyargs]
            required_count = len(all_positional) - len(args.defaults)
            required_kwonly = [
                a.arg
                for a, default in zip(args.kwonlyargs, args.kw_defaults)
                if default is None
            ]
            return positional, keyword, required_count, required_kwonly
    return None


def _check_required(text, module, func, required, problems, *, expected_limit=1):
    sig = _signature(text, func) if text is not None else None
    if sig is None:
        problems.append("missing required %s.%s" % (module, func))
        return None
    positional, _keyword, required_count, required_kwonly = sig
    if list(positional[: len(required)]) != list(required):
        problems.append(
            "%s.%s must accept positional parameters %r in order, found prefix %r"
            % (module, func, list(required), positional[: len(required)])
        )
    if required_count > expected_limit:
        problems.append(
            "%s.%s must accept at most %d required positional arguments, found %d"
            % (module, func, expected_limit, required_count)
        )
    if required_kwonly:
        problems.append(
            "%s.%s must not require keyword-only arguments %r"
            % (module, func, required_kwonly)
        )
    return sig


def _check_keyword(sig, module, func, keyword, problems):
    if sig is None:
        return
    if keyword not in sig[1]:
        problems.append(
            "%s.%s cannot be called with keyword %r" % (module, func, keyword)
        )


def _call_llm_calls(tree):
    """Yield Call nodes of ``call_llm.extract(...)`` in ``tree``."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "extract":
            continue
        value = func.value
        if isinstance(value, ast.Name) and value.id == "call_llm":
            yield node


def _storage_calls(tree):
    """Yield append_validated Call nodes whose receiver is ``storage``."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "append_validated":
            continue
        value = func.value
        if isinstance(value, ast.Name) and value.id == "storage":
            yield node


def _named_or_present(call, keyword, positional_index=None):
    for kw in call.keywords:
        if kw.arg == keyword:
            return True
    if positional_index is not None and len(call.args) > positional_index:
        return True
    return False


def _check_pipeline_calls(pipeline_text, problems):
    """Require pipeline.process to pass request_id and expected_spent."""
    try:
        tree = ast.parse(pipeline_text)
    except SyntaxError:
        return
    for node in tree.body:
        if not (isinstance(node, ast.FunctionDef) and node.name == "process"):
            continue
        extract_calls = list(_call_llm_calls(node))
        if not extract_calls:
            problems.append("pipeline.process does not call call_llm.extract")
        else:
            for call in extract_calls:
                if not _named_or_present(call, "request_id"):
                    problems.append(
                        "pipeline.process calls call_llm.extract without 'request_id'"
                    )
        append_calls = list(_storage_calls(node))
        if not append_calls:
            problems.append("pipeline.process does not call storage.append_validated")
        else:
            for call in append_calls:
                if not _named_or_present(call, "expected_spent"):
                    problems.append(
                        "pipeline.process calls storage.append_validated without 'expected_spent'"
                    )

def check_call_api(pipeline_text, callllm_text, policy_text, storage_text):
    """Verify the frozen base API across Phase 1 (no storage) and Phase 2."""
    problems = []

    if pipeline_text is None:
        problems.append("missing pipeline module")
    if callllm_text is None:
        problems.append("missing call_llm module")

    sig_process = _check_required(
        pipeline_text,
        "pipeline",
        "process",
        ("text", "spent", "budget_limit"),
        problems,
        expected_limit=3 if storage_text is None else 1,
    )
    if sig_process is not None and "text" not in sig_process[0]:
        problems.append("pipeline.process missing first positional 'text'")

    sig_extract = _check_required(callllm_text, "call_llm", "extract", ("text",), problems)

    has_validate = _check_required(
        policy_text,
        "policy_core",
        "validate_record",
        ("raw", "spent", "budget_limit"),
        problems,
        expected_limit=3,
    )
    if not _has_exception(policy_text, "PolicyError"):
        problems.append("policy_core.PolicyError is missing")
    if not _has_exception(callllm_text, "LlmTransportError"):
        problems.append("call_llm.LlmTransportError is missing")

    if storage_text is not None:
        if not _has_exception(storage_text, "StorageError"):
            problems.append("storage.StorageError is missing")
        sig_append = _check_required(
            storage_text, "storage", "append_validated", ("record",), problems
        )
        _check_keyword(sig_append, "storage", "append_validated", "expected_spent", problems)
        _check_keyword(sig_extract, "call_llm", "extract", "request_id", problems)
        if pipeline_text is not None:
            _check_pipeline_calls(pipeline_text, problems)
    return problems


def _has_exception(text, name):
    if text is None:
        return False
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return True
    return False


def _scan_transport(root):
    problems = []
    for sub in ("src", "scripts"):
        base = os.path.join(root, sub)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirs, files in os.walk(base):
            for name in sorted(files):
                if not name.endswith(".py"):
                    continue
                full = os.path.join(dirpath, name)
                rel = _norm(os.path.relpath(full, root))
                if rel == MODEL_ENTRY:
                    continue
                with open(full, encoding="utf-8") as handle:
                    text = handle.read()
                hit = _imports_transport(_toplevel_imports(text))
                if hit:
                    problems.append("%s: direct transport import %r" % (rel, hit))
    return problems


def _imports_transport(names):
    """Return a transport module matched in ``names`` (any dotted import)."""
    for name in names:
        for module in TRANSPORT_MODULES:
            if name == module or name.startswith(module + "."):
                return module
    return ""


def _strip_jsonc(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(^|\s)//[^\n]*", r"\1", text)
    return text


def _load_permissions(root):
    path = os.path.join(root, ".opencode", "permissions.jsonc")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        raw = _strip_jsonc(handle.read())
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return "invalid"


def _path_permission_ok(section, pattern):
    """Deny is honoured unless an exact allow overrides it."""
    for key, value in section.items():
        if key == pattern and value == "allow":
            return False
        if key.startswith(pattern) and not key.endswith(".example") and value == "allow":
            if pattern.endswith("/") and key.startswith(pattern):
                return False
    return True


def check_permissions(perms):
    problems = []
    if not isinstance(perms, dict):
        return ["permissions.jsonc missing or invalid"]
    if perms.get("*") != "deny":
        problems.append("root default is not deny")
    read = perms.get("read")
    edit = perms.get("edit")
    if not isinstance(read, dict):
        problems.append("read section missing or not a dict")
        read = {}
    if not isinstance(edit, dict):
        problems.append("edit section missing or not a dict")
        edit = {}
    if read.get(".env") != "deny":
        problems.append(".env read must be deny")
    if edit.get(".env") != "deny":
        problems.append(".env edit must be deny")
    for pattern in PERMISSION_EDIT_DENY:
        if pattern == ".env":
            continue
        rule = pattern + "**"
        if edit.get(rule) != "deny":
            problems.append("edit %r must be deny" % rule)
        if not _path_permission_ok(edit, pattern):
            problems.append("edit allow leaks protected path %s" % pattern)
    bash = perms.get("bash")
    if not isinstance(bash, dict):
        problems.append("bash section missing or not a dict")
        bash = {}
    star = bash.get("*")
    if star not in ("ask", "deny"):
        problems.append("bash '*' must stay ask/deny")
    for command in FORBIDDEN_BASH:
        if bash.get(command) != "deny":
            problems.append("bash %r must stay deny" % command)
    return problems


def _has_adr_in_pr(changed, base, head, cwd=None):
    for path in changed:
        norm = _norm(path)
        if not (norm.startswith(CRITICAL_PREFIXES) and norm.endswith(".md")):
            continue
        if _blob(head, norm, cwd) is not None:
            return True
    return False


def _security_paths_touched(changed):
    touched = []
    for path in changed:
        norm = _norm(path)
        if norm in CRITICAL_FILES or norm == "src/call_llm.py":
            touched.append(norm)
        elif norm.startswith(".github/workflows/"):
            touched.append(norm)
        elif norm.startswith(".opencode/") or norm.startswith(".agent/"):
            touched.append(norm)
    return touched


def _base_has_file(base, path, cwd=None):
    """True if ``path`` exists in the BASE_SHA commit tree."""
    try:
        proc = subprocess.run(
            ["git", "cat-file", "-e", "%s:%s" % (base, path)],
            cwd=cwd, check=False, capture_output=True, text=True,
        )
    except (OSError, ValueError):
        return False
    return proc.returncode == 0


def check_merge_tree(base, head, cwd=None):
    """Simulated merge of BASE_SHA onto HEAD must equal the result tree."""
    try:
        git(["cat-file", "-e", base + "^{commit}"], cwd)
    except RuntimeError:
        return []
    proc = subprocess.run(
        ["git", "merge-tree", "--write-tree", head, base],
        cwd=cwd, check=False, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        output = (proc.stdout or "") + (proc.stderr or "")
        low = output.lower()
        if "conflict" in low or "both modified" in low:
            return ["merge of base into head conflicts"]
        return []
    return []


def gate_static_analysis(env, root="."):
    problems = []
    problems.extend(_scan_transport(root))

    pipeline_text = _read(root, "src/pipeline.py")
    callllm_text = _read(root, "src/call_llm.py")
    policy_text = _read(root, "src/policy_core.py")
    storage_text = _read(root, "src/storage.py")
    if storage_text is not None:
        problems.extend(
            check_call_api(pipeline_text, callllm_text, policy_text, storage_text)
        )
    else:
        problems.extend(
            check_call_api(pipeline_text, callllm_text, policy_text, None)
        )
        base_sha = (env.get("BASE_SHA", "") or "").strip()
        if base_sha and _base_has_file(base_sha, "src/storage.py", root):
            problems.append(
                "src/storage.py missing from checkout but present in BASE_SHA"
            )

    problems.extend(check_permissions(_load_permissions(root)))

    base = env.get("BASE_SHA", "").strip()
    head = env.get("PR_HEAD_SHA", "").strip() or "HEAD"
    if base:
        merge_base = git(["merge-base", base, head], root).strip()
        changed = _diff_files(merge_base, head, root)
        if _security_paths_touched(changed):
            if not _has_adr_in_pr(changed, merge_base, head, root):
                problems.append(
                    "security-critical change without a matching ADR in this PR"
                )
        problems.extend(check_merge_tree(base, head, root))

    if problems:
        for problem in problems:
            print("FAIL: %s" % problem)
        return EXIT_FAIL
    return _ok("entry point, API shape, permissions and ADR intact")


def _read(root, path):
    full = os.path.join(root, path)
    if not os.path.isfile(full):
        return None
    with open(full, encoding="utf-8") as handle:
        return handle.read()


# ---------------------------------------------------------------------------
# secret-scan: report paths only
# ---------------------------------------------------------------------------
def _scannable(path):
    name = _norm(path).split("/")[-1]
    if name in NEVER_READ_NAMES:
        return False
    if name.endswith(".env.example"):
        return True
    if name.startswith(".env"):
        return False
    return True


def scan_credentials(path, text):
    if not _scannable(path):
        return False
    return any(pattern.search(text) for pattern in CREDENTIAL_PATTERNS)


def gate_secret_scan(cwd="."):
    suspicious = []
    for path in git(["ls-files"], cwd).splitlines():
        if not path.strip() or not _scannable(path):
            continue
        try:
            with open(os.path.join(cwd, path), encoding="utf-8", errors="strict") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        if scan_credentials(path, text):
            suspicious.append(path)
    if suspicious:
        for path in suspicious:
            print("FAIL: credential-like content in tracked file: %s" % path)
        return EXIT_FAIL
    return _ok("no credential-like content in tracked files")


# ---------------------------------------------------------------------------
# semantic-scope: flag model / prompt / eval / workflow changes
# ---------------------------------------------------------------------------
PROMPT_PREFIX = "prompts/"
EVAL_PREFIXES = ("evals/", "eval/")
EVAL_FILE_HINT = re.compile(r"(?i)eval")
PROMPT_FILE_RE = re.compile(r"^.*\.ya?ml$")

SEMANTIC_TRIGGER_FILES = frozenset({
    "src/call_llm.py",
    "Prompt.md",
    ".env.example",
    "test/live/test_live_model.py",
})


def _is_prompt_yaml(path):
    return _norm(path).startswith(PROMPT_PREFIX) and bool(PROMPT_FILE_RE.match(_norm(path)))


def _is_critical_workflow(path):
    norm = _norm(path)
    return norm.startswith(".github/") and (
        norm.endswith(".yml") or norm.endswith(".yaml") or norm.endswith("ci_checks.py")
    )


def _is_eval_path(path):
    norm = _norm(path)
    if any(norm.startswith(p) for p in EVAL_PREFIXES):
        return True
    return _is_python(norm) and bool(EVAL_FILE_HINT.search(norm.split("/")[-1]))


def _model_registry_changed(base, head, cwd=None):
    base_text = _blob(base, "docs/req/requirements.yaml", cwd)
    head_text = _blob(head, "docs/req/requirements.yaml", cwd)
    if base_text is None or head_text is None:
        return False
    return _model_block(base_text) != _model_block(head_text)


def _model_block(text):
    if yaml is None or text is None:
        return None
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if isinstance(doc, dict):
        meta = doc.get("project_metadata") or {}
        return (meta.get("model") if isinstance(meta, dict) else None)
    return None


def _is_replayable_prompt(rev, path, cwd=None):
    """True unless the prompt file says ``status: superseded``.

    A superseded prompt records what used to run; replaying it against the live
    model would evaluate text that production no longer sends. Only an explicit
    marker opts a file out. A missing or non-string ``status`` stays replayable,
    and a file that cannot be parsed raises: silently replaying it hides a broken
    artefact behind five confusing live-test failures.
    """
    text = _blob(rev, path, cwd)
    if text is None or yaml is None:
        return True
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError:
        raise RuntimeError("prompt file is not valid YAML: %s" % _norm(path))
    if not isinstance(document, dict):
        return True
    status = document.get("status")
    if not isinstance(status, str):
        return True
    return status.strip().lower() != "superseded"


def classify_semantic_paths(base, head, changed, cwd=None):
    runtime_prompts = []
    required = False
    prompt_touched = False
    for path in changed:
        norm = _norm(path)
        if norm in SEMANTIC_TRIGGER_FILES:
            required = True
        if _is_prompt_yaml(norm):
            if _blob(head, norm, cwd) is not None:
                runtime_prompts.append(norm)
        elif _is_eval_path(norm):
            required = True
        elif _is_critical_workflow(norm):
            required = True
        if norm.startswith(PROMPT_PREFIX):
            prompt_touched = True
    if prompt_touched:
        required = True
        runtime_prompts = [
            p for p in git(["ls-tree", "-r", "--name-only", head, "--", PROMPT_PREFIX], cwd).splitlines()
            if p.strip() and _is_prompt_yaml(p) and _blob(head, p, cwd) is not None
            and _is_replayable_prompt(head, p, cwd)
        ]
    if _model_registry_changed(base, head, cwd):
        required = True
    return required, sorted(set(runtime_prompts))


def gate_semantic_scope(env):
    base = env.get("BASE_SHA", "").strip()
    head = env.get("PR_HEAD_SHA", "").strip()
    if not base or not head:
        return _fail("BASE_SHA and PR_HEAD_SHA are required")
    merge_base = git(["merge-base", base, head]).strip()
    changed = _diff_files(merge_base, head)
    required, runtime_prompts = classify_semantic_paths(merge_base, head, changed)
    outputs = {
        "semantic_required": "true" if required else "false",
        "runtime_prompts": json.dumps(runtime_prompts),
    }
    _write_github_output(env, outputs)
    print("semantic_required=%s" % outputs["semantic_required"])
    print("runtime_prompts=%s" % outputs["runtime_prompts"])
    return EXIT_OK


def _write_github_output(env, values):
    target = env.get("GITHUB_OUTPUT", "").strip()
    if not target:
        return
    with open(target, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write("%s=%s\n" % (key, value))


# ---------------------------------------------------------------------------
# ai-use-log: keep old rows, append new sessions
# ---------------------------------------------------------------------------
def parse_ai_log(text):
    if text is None:
        return None
    if yaml is None:
        raise RuntimeError("PyYAML is required for the ai-use-log check")
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if not isinstance(doc, list):
        return None
    rows = []
    for entry in doc:
        if not isinstance(entry, dict):
            return None
        for field in AI_LOG_KEY_FIELDS:
            if field not in entry or entry[field] is None:
                return None
            if not str(entry[field]).strip():
                return None
        rows.append(entry)
    return rows


def _row_key(entry):
    return tuple(_scalar(entry[field]) for field in AI_LOG_KEY_FIELDS)


def _scalar(value):
    return value


def _needs_log_entry(changed):
    for path in changed:
        norm = _norm(path)
        if norm in AI_LOG_TRIGGER_FILES:
            return True
        if any(norm.startswith(prefix) for prefix in AI_LOG_TRIGGER_PREFIXES):
            return True
    return False


def check_ai_log(base_text, head_text, changed=None):
    problems = []
    head_rows = parse_ai_log(head_text)
    if head_rows is None:
        return ["HEAD %s missing or not a valid list of keyed rows" % AI_LOG_PATH]
    if not head_rows:
        return ["HEAD %s is empty" % AI_LOG_PATH]

    head_index = {}
    for row in head_rows:
        key = _row_key(row)
        if key in head_index:
            return ["duplicate session key on HEAD: %s" % (key,)]
        head_index[key] = row

    base_rows = parse_ai_log(base_text) or []
    for base_row in base_rows:
        key = _row_key(base_row)
        if key not in head_index:
            problems.append("old session row removed: %s" % (key,))
            continue
        if not _same_row(base_row, head_index[key]):
            problems.append("old session row altered: %s" % (key,))

    if changed is not None and _needs_log_entry(changed):
        base_keys = {_row_key(row) for row in base_rows}
        if not (set(head_index) - base_keys):
            problems.append("log trigger changed but no new session appended")
    return problems


def _same_row(left, right):
    if set(left) != set(right):
        return False
    return all(left[key] == right[key] for key in left)


def gate_ai_use_log(env):
    base = env.get("BASE_SHA", "").strip()
    head = env.get("PR_HEAD_SHA", "").strip() or "HEAD"
    if not base:
        return _fail("BASE_SHA is empty")
    merge_base = git(["merge-base", base, head]).strip()
    base_text = _blob(merge_base, AI_LOG_PATH)
    head_text = _blob(head, AI_LOG_PATH)
    changed = _diff_files(merge_base, head)
    problems = check_ai_log(base_text, head_text, changed)
    if problems:
        for problem in problems:
            print("FAIL: %s" % problem)
        return EXIT_FAIL
    return _ok("AI-use log keeps old sessions and appends new ones")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv):
    if len(argv) != 2:
        print(
            "usage: ci_checks.py "
            "{test-approval|static-analysis|secret-scan|semantic-scope|ai-use-log}"
        )
        return EXIT_USAGE
    command = argv[1]
    env = {
        "BASE_SHA": _env("BASE_SHA"),
        "PR_HEAD_SHA": _env("PR_HEAD_SHA"),
        "GH_TOKEN": _env("GH_TOKEN"),
        "PR_NUMBER": _env("PR_NUMBER"),
        "PR_AUTHOR": _env("PR_AUTHOR"),
        "GITHUB_API_URL": _env("GITHUB_API_URL"),
        "GITHUB_REPOSITORY": _env("GITHUB_REPOSITORY"),
        "GITHUB_OUTPUT": _env("GITHUB_OUTPUT"),
    }
    try:
        if command == "test-approval":
            return gate_test_approval(env)
        if command == "static-analysis":
            return gate_static_analysis(env)
        if command == "secret-scan":
            return gate_secret_scan()
        if command == "semantic-scope":
            return gate_semantic_scope(env)
        if command == "ai-use-log":
            return gate_ai_use_log(env)
    except RuntimeError as exc:
        return _fail(str(exc))
    print("unknown command: %s" % command)
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main(sys.argv))
