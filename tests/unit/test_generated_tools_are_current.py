"""The generated theme pages match the sources they are generated from.

Segment 19K Item 7. `tools/theme_preview.html` and
`tools/theme_customizer.html` are generated from `app/web/templates/
base.html` plus their own `.gen.py`, and both are committed. Nothing
checked that the committed file matched what the generator produces, so
a palette change that reached `base.html` and the app could leave the
tools describing a palette that no longer ships — silently, since a
stale page renders perfectly.

That is not hypothetical: 19K.7 collapsed four light text tokens onto a
deeper tier, regenerated the customizer, and left the preview stale for
a day. A review bot found it, not the suite. This is the suite catching
it next time.

**It regenerates into a temp copy and compares**, rather than running
the generator in place: a test must not modify the working tree, and a
test that "fixes" the drift it is meant to report would never fail
twice.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

#: Each generated page and the script that writes it.
GENERATED = {
    "tools/theme_preview.html": "tools/theme_preview.gen.py",
    "tools/theme_customizer.html": "tools/theme_customizer.gen.py",
}


@pytest.mark.parametrize(("page", "generator"), sorted(GENERATED.items()))
def test_the_generated_page_matches_its_generator(page: str, generator: str) -> None:
    committed = (REPO / page).read_bytes()
    assert committed, f"{page} is empty"

    with tempfile.TemporaryDirectory() as tmp:
        # The generators resolve their paths from __file__ upwards, so
        # they need the tree shape, not just the two files. A symlinked
        # skeleton is enough and costs nothing to build.
        work = Path(tmp) / "repo"
        (work / "tools").mkdir(parents=True)
        (work / "app/web/templates").mkdir(parents=True)
        for src in ("app/web/templates/base.html",):
            shutil.copy2(REPO / src, work / src)
        for src in REPO.glob("tools/*.py"):
            shutil.copy2(src, work / "tools" / src.name)

        result = subprocess.run(  # noqa: S603
            [sys.executable, str(work / generator)],
            capture_output=True,
            text=True,
            cwd=work,
            env={**os.environ, "PYTHONPATH": str(work / "tools")},
        )
        assert result.returncode == 0, f"{generator} failed:\n{result.stderr}"
        regenerated = (work / page).read_bytes()

    assert regenerated == committed, (
        f"{page} is stale — it does not match what {generator} produces "
        f"from the current base.html ({len(committed)} bytes committed, "
        f"{len(regenerated)} regenerated). Run `python3 {generator}` and "
        "commit the result."
    )


def test_every_generator_in_tools_is_covered() -> None:
    """A new `*.gen.py` joins this check rather than slipping past it.

    The failure mode this file exists for is a generated artefact nobody
    re-runs; a generator absent from `GENERATED` reproduces it exactly.
    `theme_variants.gen.py` is the deliberate exception — its `VARIANTS`
    list is empty, so it writes no file (see `tools/README.md`).
    """
    generators = {
        f"tools/{p.name}" for p in (REPO / "tools").glob("*.gen.py")
    } - {"tools/theme_variants.gen.py"}

    assert generators == set(GENERATED.values()), (
        "generators not covered by this check: "
        f"{sorted(generators - set(GENERATED.values()))}"
    )
