"""Which CI lanes a change needs (guide/segment_22A_ci_lanes.md).

Reads the changed paths, one per line, on stdin and prints ``lane=prose``
or ``lane=full``, the line a workflow appends to ``$GITHUB_OUTPUT``.

    git diff --name-only --no-renames HEAD^1 HEAD | python3 tools/ci_lanes.py --event pull_request

A change is ``prose`` only when every path is Markdown in a prose folder
or at the root, or a README outside ``app/`` and ``alembic/``. Anything else, an empty list, any event but
``pull_request``, or any error is ``full``: the classifier fails toward
running everything. ``--prose-tests`` prints what the prose lane runs.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

PROSE_DIRS = (
    "spec/",
    "docs/",
    "guide/",
    "cordware/spec/",
    "residentialapps/docs/",
    "residentialapps/guide/",
)
# A README anywhere is prose, except where it would ship with the app.
README = "README.md"
SHIPPED_DIRS = ("app/", "alembic/")

# What the prose lane runs: every unit test (the doc gates live there), plus
# each test file elsewhere that reads a prose path.
PROSE_TESTS = (
    "tests/unit",
    "tests/integration/test_guide_scaffold.py",
)

# Test files outside the unit tests are scanned for any string literal naming
# a prose path. Each file that matches must be in PROSE_TESTS or here, with
# the reason it reads no prose: a new match forces a decision, never a skip.
TEST_ROOTS = ("tests", "cordware/tests")
NOT_PROSE_READERS = {
    "tests/browser/test_builder_branching.py": "a docstring cites a guide plan",
    "tests/integration/test_guide_screencaps.py": "reads app/web/static/guide, not guide/",
    "tests/integration/test_url_crawl.py": '"guide" is the in-app /guide URL',
}
PROSE_LITERAL = re.compile(
    r"""["'](?:spec|docs|guide|cordware/spec|residentialapps/(?:docs|guide)|residentialapps/README\.md)(?:/[^"'\n]*)?["']"""
    r"""|["'][A-Za-z0-9_-]+\.md["']"""
    r"""|["'](?:[A-Za-z0-9_.-]+/)+README\.md["']"""
)


def is_prose(path: str) -> bool:
    """Whether a changed path is prose: Markdown in a prose folder or at the
    root, or a README outside what ships with the app."""
    if path.rsplit("/", 1)[-1] == README and not path.startswith(SHIPPED_DIRS):
        return True
    if not path.endswith(".md"):
        return False
    if "/" not in path:
        return True
    return path.startswith(PROSE_DIRS)


def lane(paths: list[str], event: str) -> str:
    """``prose`` when a pull request changes only prose, else ``full``."""
    paths = [p.strip() for p in paths if p.strip()]
    if event != "pull_request" or not paths:
        return "full"
    return "prose" if all(is_prose(p) for p in paths) else "full"


def prose_reading_tests(repo: Path = REPO) -> list[str]:
    """Test files outside ``tests/unit/`` with a string literal naming a prose path."""
    found = []
    for root in TEST_ROOTS:
        for path in sorted((repo / root).rglob("*.py")):
            rel = path.relative_to(repo).as_posix()
            if rel.startswith("tests/unit/"):
                continue
            if PROSE_LITERAL.search(path.read_text(encoding="utf-8")):
                found.append(rel)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--event", default="", help="the GitHub event name")
    parser.add_argument("--prose-tests", action="store_true", help="print what the prose lane runs")
    args = parser.parse_args(argv)
    if args.prose_tests:
        print(" ".join(PROSE_TESTS))
        return 0
    try:
        result = lane(sys.stdin.read().splitlines(), args.event)
    except Exception:  # fail toward running everything
        result = "full"
    print(f"lane={result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
