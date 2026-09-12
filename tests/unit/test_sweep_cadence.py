"""The sweep cadence is reset by a corpus sweep, never by a partial one.

`--stale` answers "are we due for a whole-folder sweep?", and that
cadence (8 weeks or 500 merges, Segment 19A Item 2) is defined over
``spec/`` + ``docs/`` **as a corpus**. Until 2026-09-12 ``last_sweep_date``
took ``max()`` over every dated ``guide/sweep_*.md`` with no notion of
what each had read, so the single-file 2026-09-10 sweep — whose own
opening says the folder-scoped cadence is a separate thing — reset the
clock from **230 merges / 7 days to 61 / 2** (measured at ``bb38111f``).

Nothing misfired: neither figure is near 500 / 56. The defect is that the
clock ran from the wrong event, and would have compounded with every
later partial sweep.

The scope cannot be read off the filename. ``sweep_<YYYY-MM-DD>_<scope>``
puts the scope in the name, but the slug is free text — ``spec-docs``
and ``rrw_functional_spec`` are the two live examples — so the document
declares it instead, in the same comment-marker style the repo already
uses for ``doc-impact-waived``, ``cites`` and ``path-ref-ok``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from close_check import dated_sweeps, last_sweep_date  # noqa: E402
from close_check._shared import Unresolvable  # noqa: E402

GUIDE = REPO / "guide"


def test_every_dated_sweep_declares_its_scope() -> None:
    """No live sweep is unmarked, so none is guessed at."""
    sweeps = dated_sweeps()
    assert sweeps, "no dated sweeps found — the filename convention has moved"
    for date, scope, name in sweeps:
        assert scope in ("corpus", "partial"), (date, scope, name)


def test_the_cadence_reads_the_newest_corpus_sweep() -> None:
    """`last_sweep_date` ignores partial sweeps, however recent."""
    sweeps = dated_sweeps()
    corpus = [date for date, scope, _ in sweeps if scope == "corpus"]
    newest_of_any_kind = max(date for date, _, _ in sweeps)

    assert last_sweep_date() == max(corpus)

    # Only meaningful while a partial sweep is the most recent one. That
    # is the live case today (2026-09-10 partial after 2026-09-05 corpus)
    # and precisely the case the old code got wrong; if it stops holding,
    # the assertion above still pins the behaviour.
    if newest_of_any_kind not in corpus:
        assert last_sweep_date() != newest_of_any_kind, (
            "a partial sweep is the newest dated sweep and the cadence is "
            "reading it — this is the 2026-09-12 defect, back again."
        )


def test_an_unmarked_sweep_is_rejected_rather_than_guessed(tmp_path) -> None:
    """A dated sweep with no marker raises, naming the file and the fix.

    Silently defaulting — to either value — is the failure mode this
    whole mechanism exists to remove: one default would re-introduce the
    original bug, the other would suppress a real cadence reset.
    """
    import close_check._shared as shared

    guide = tmp_path / "guide"
    guide.mkdir()
    (guide / "sweep_2026-01-01_marked.md").write_text(
        "# Sweep\n<!-- sweep-scope: corpus -->\n"
    )
    (guide / "sweep_2026-02-02_unmarked.md").write_text("# Sweep\nno marker\n")

    original = shared.REPO
    shared.REPO = tmp_path
    try:
        with pytest.raises(Unresolvable) as excinfo:
            dated_sweeps()
    finally:
        shared.REPO = original

    message = str(excinfo.value)
    assert "sweep_2026-02-02_unmarked.md" in message
    assert "sweep-scope" in message


def test_a_partial_sweep_does_not_move_the_cadence(tmp_path) -> None:
    """Adding a newer *partial* sweep leaves `last_sweep_date` alone.

    The behavioural statement, on a controlled tree rather than on the
    repo's own two files — so it keeps testing something once those
    files change.
    """
    import close_check._shared as shared

    guide = tmp_path / "guide"
    guide.mkdir()
    (guide / "sweep_2026-03-03_spec-docs.md").write_text(
        "<!-- sweep-scope: corpus -->\n"
    )

    original = shared.REPO
    shared.REPO = tmp_path
    try:
        assert last_sweep_date() == "2026-03-03"
        (guide / "sweep_2026-06-06_one_file.md").write_text(
            "<!-- sweep-scope: partial -->\n"
        )
        assert last_sweep_date() == "2026-03-03", (
            "a partial sweep moved the cadence clock"
        )
        (guide / "sweep_2026-09-09_spec-docs.md").write_text(
            "<!-- sweep-scope: corpus -->\n"
        )
        assert last_sweep_date() == "2026-09-09", (
            "a corpus sweep failed to move the cadence clock"
        )
    finally:
        shared.REPO = original


def test_the_template_ships_a_marker_that_must_be_edited() -> None:
    """The template's marker is present but deliberately *not valid*.

    A new sweep starts from the template, so the marker has to be in it
    — but shipping it set to ``corpus`` would make the likeliest mistake
    silent: copy the template for a one-file sweep, don't touch the
    marker, and the cadence clock resets exactly as it did before this
    fix. The placeholder fails the ``(corpus|partial)`` pattern, so
    ``--stale`` refuses to run until the author chooses.

    **The limit this does not reach**, recorded rather than papered
    over: a marker set to ``corpus`` on a sweep that read one file is
    undetectable here. Nothing in the repo can check a declaration
    against what a human actually read — mutating the live 2026-09-10
    sweep's marker to ``corpus`` reproduces the original defect with
    every test in this file still green. What is removed is the
    *accidental* case; the deliberate one stays a matter of authorship.
    """
    from close_check._sweep import SWEEP_SCOPE_MARKER

    template = (GUIDE / "sweep_template.md").read_text()
    assert "<!-- sweep-scope:" in template, "template lost its marker"
    assert SWEEP_SCOPE_MARKER.search(template) is None, (
        "the template's sweep-scope marker is a valid value, so a sweep "
        "copied from it and left unedited would be silently classified "
        "instead of prompting the author to choose"
    )
    assert "corpus" in template and "partial" in template, (
        "the template no longer explains what the two values mean"
    )
