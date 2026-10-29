"""Which CI lanes a change needs (guide/archive/segment_22A_ci_lanes.md;
the ``residential`` lane is Residential segment 1A's).

Reads the changed paths, one per line, on stdin and prints ``lane=prose``,
``lane=residential`` or ``lane=full``, the line a workflow appends to
``$GITHUB_OUTPUT``.

    git diff --name-only --no-renames HEAD^1 HEAD | python3 tools/ci_lanes.py --event pull_request

A change is ``prose`` only when every path is Markdown in a prose folder
or at the root, or a README outside the shipped folders. It is
``residential`` when every path is prose or under ``residentialapps/``.
Anything else, an empty list, any event but ``pull_request``, or any error
is ``full``: the classifier fails toward running everything.
``--prose-tests`` and ``--residential-tests`` print what those lanes run.
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
    "residentialapps/spec/",
)
# A README anywhere is prose, except in what ships to the host: the deploy
# artefact and Cordware's import carry these folders. Their prose folders
# (``cordware/spec/``, Residential's ``docs/``, ``guide/`` and ``spec/``) stay prose.
README = "README.md"
PROSE_FILES = frozenset({"residentialapps/README.md"})
SHIPPED_DIRS = ("app/", "alembic/", "cordware/", "residentialapps/")

# What the prose lane runs: every unit test (the doc gates live there), plus
# each test file elsewhere that reads a prose path.
PROSE_TESTS = (
    "tests/unit",
    "tests/integration/test_guide_scaffold.py",
)

# What the residential lane runs beside the prose lane's tests: Residential's
# own tests and the host's, which hold the import boundaries and mount it.
# RRW's suite and the Postgres round-trip are skipped. RRW never imports
# Residential (the boundary test), but its tests that import `cordware.main`
# build every registered factory; Residential's tests build them the same
# way, so a factory that fails to import or build fails here too. A side
# effect beyond that, such as a database hook once Residential has one
# (segment 1B), shows first on `main`, where every push runs everything.
RESIDENTIAL = "residentialapps/"
RESIDENTIAL_TESTS = ("residentialapps/tests", "cordware/tests")

# Test files outside the unit tests are scanned for any string literal naming
# a prose path. Each file that matches must be in PROSE_TESTS or here, with
# the reason it reads no prose: a new match forces a decision, never a skip.
TEST_ROOTS = ("tests", "cordware/tests", "residentialapps/tests")
NOT_PROSE_READERS = {
    "tests/browser/test_builder_branching.py": "a docstring cites a guide plan",
    "tests/integration/test_guide_screencaps.py": "reads app/web/static/guide, not guide/",
    "tests/integration/test_url_crawl.py": '"guide" is the in-app /guide URL',
    "residentialapps/tests/test_sample_data.py": "reads the mock CSVs, not prose; the residential lane runs it",
    "residentialapps/tests/test_supportlogs.py": "reads the Staff roster mock CSV, not prose; the residential lane runs it",
    "residentialapps/tests/test_supportlogs_overview.py": "reads the assignments mock CSV, not prose; the residential lane runs it",
    "residentialapps/tests/test_supportlogs_sys_admin.py": "reads the Staff roster mock CSV, not prose; the residential lane runs it",
}
PROSE_LITERAL = re.compile(
    r"""["'](?:spec|docs|guide|cordware/spec|residentialapps/(?:docs|guide|spec)|residentialapps/README\.md)(?:/[^"'\n]*)?["']"""
    r"""|["'][A-Za-z0-9_-]+\.md["']"""
    r"""|["'](?:[A-Za-z0-9_.-]+/)+README\.md["']"""
)


def is_prose(path: str) -> bool:
    """Whether a changed path is prose: Markdown in a prose folder or at the
    root, or a README outside what ships with the app."""
    if path in PROSE_FILES:
        return True
    if path.rsplit("/", 1)[-1] == README and not path.startswith(SHIPPED_DIRS):
        return True
    if not path.endswith(".md"):
        return False
    if "/" not in path:
        return True
    return path.startswith(PROSE_DIRS)


def lane(paths: list[str], event: str) -> str:
    """``prose`` when a pull request changes only prose, ``residential``
    when it changes only prose and Residential, else ``full``."""
    paths = [p.strip() for p in paths if p.strip()]
    if event != "pull_request" or not paths:
        return "full"
    if all(is_prose(p) for p in paths):
        return "prose"
    if all(is_prose(p) or p.startswith(RESIDENTIAL) for p in paths):
        return "residential"
    return "full"


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
    parser.add_argument(
        "--residential-tests", action="store_true", help="print what the residential lane runs"
    )
    args = parser.parse_args(argv)
    if args.prose_tests:
        print(" ".join(PROSE_TESTS))
        return 0
    if args.residential_tests:
        print(" ".join(RESIDENTIAL_TESTS + PROSE_TESTS))
        return 0
    try:
        result = lane(sys.stdin.read().splitlines(), args.event)
    except Exception:  # fail toward running everything
        result = "full"
    print(f"lane={result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
