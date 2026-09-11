"""Navigation busy indicator — Segment 19J.4.

Structural assertions over the template sources, for the same reason
``test_column_visibility_primitive.py`` has them: the failure mode is
silent. Nothing in a Python test suite can click a link, so the four
rules the script's header states are pinned here at the source level,
where a future editor trips over them instead of shipping past them.

The one that matters most is rule 2. Marking a submit button
``disabled`` is the obvious way to suppress a double submit, it looks
harmless, and it silently drops the button's ``name``/``value`` from
the payload — which this app's forms depend on (the Workflow
super-button, the roster bulk actions). A test is the only thing
standing between that edit and a production bug nobody would trace
back to the indicator.
"""
from __future__ import annotations

import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[2] / "app" / "web" / "templates"
BASE = TEMPLATES / "base.html"

BASE_SRC = BASE.read_text(encoding="utf-8")


def _script_source() -> str:
    """The indicator's own IIFE, sliced out of ``base.html`` so the
    assertions below cannot be satisfied by some unrelated script."""
    start = BASE_SRC.index("var ARM_MS")
    end = BASE_SRC.index("</script>", start)
    return BASE_SRC[start:end]


def test_bar_and_status_region_are_in_the_chrome() -> None:
    assert "data-rrw-busy-bar" in BASE_SRC
    assert "data-rrw-busy-status" in BASE_SRC
    # The live region ships in the initial HTML: one created and
    # populated in the same tick is not reliably announced.
    assert 'role="status" data-rrw-busy-status' in BASE_SRC


def test_bar_starts_hidden() -> None:
    bar = re.search(r'<div class="rrw-busy"[^>]*>', BASE_SRC)
    assert bar is not None
    assert "hidden" in bar.group(0)


def test_the_script_never_disables_the_submitter() -> None:
    """Rule 2. A disabled control is not serialized."""
    script = _script_source()
    assert ".disabled" not in script
    assert "disabled" not in script.replace("aria-disabled", "")
    # The busy state is aria-busy, which changes no serialization.
    assert 'setAttribute("aria-busy", "true")' in script


def test_the_script_disarms_on_pageshow() -> None:
    """Rule 3. bfcache restores the DOM with the bar still running."""
    assert 'window.addEventListener("pageshow", clear)' in _script_source()


def test_the_script_skips_download_links() -> None:
    """Rule 4. An attachment never replaces the page, so no load event
    ever arrives to clear the bar."""
    assert 'link.hasAttribute("download")' in _script_source()


def test_the_script_arms_on_a_delay() -> None:
    """Rule 1. A fast page must never flash the bar."""
    script = _script_source()
    assert re.search(r"var ARM_MS = \d+;", script)
    assert "window.setTimeout(show, ARM_MS)" in script


def test_modified_and_cross_origin_clicks_are_excluded() -> None:
    script = _script_source()
    for guard in ("metaKey", "ctrlKey", "shiftKey", "altKey", "event.button !== 0"):
        assert guard in script, guard
    assert "link.origin !== window.location.origin" in script


# --------------------------------------------------------------------- #
# Rule 4's other half: the markup has to carry the signal the script
# reads. A download link added without ``download`` would spin the bar
# until the give-up timer, which is the one bug this feature can ship.
# --------------------------------------------------------------------- #

# Anchors whose href names a file the server returns as an attachment.
_DOWNLOAD_HREF = re.compile(
    r"""href="[^"]*(?:/export/|\.zip|download_url|download_csv_url)[^"]*\"""",
    re.VERBOSE,
)
_ANCHOR = re.compile(r"<a\b[^>]*>", re.DOTALL)


def _download_anchors() -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for path in sorted(TEMPLATES.rglob("*.html")):
        try:
            src = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:  # pragma: no cover - defensive
            continue
        for anchor in _ANCHOR.findall(src):
            if _DOWNLOAD_HREF.search(anchor):
                found.append((path, anchor))
    return found


def test_every_attachment_link_is_marked_download() -> None:
    unmarked = [
        (path.relative_to(TEMPLATES).as_posix(), anchor)
        for path, anchor in _download_anchors()
        if "download" not in anchor.replace("download_url", "").replace(
            "download_csv_url", ""
        )
    ]
    assert unmarked == [], (
        "attachment links missing the `download` attribute — the busy "
        "indicator cannot tell them from a navigation: "
        f"{unmarked}"
    )


def test_the_download_scan_actually_finds_links() -> None:
    """Guards the test above against becoming vacuous: a regex that
    matched nothing would pass it silently."""
    assert len(_download_anchors()) >= 5
